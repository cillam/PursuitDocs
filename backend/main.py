"""
main.py

FastAPI backend for PursuitDocs.

Wraps the LangGraph pipeline as an API endpoint.
Accepts RFP submissions via file upload or URL and returns
the final letter, change log, and status.

Designed to run on AWS Lambda via Mangum adapter.

Uses an async job pattern to avoid API Gateway's 30-second timeout:
  POST /api/submit          → validates input, fires async worker Lambda,
                              returns {job_id} immediately
  GET  /api/status/{job_id} → polls DynamoDB for result
"""

import json
import os
import tempfile
import time
import uuid
from typing import Optional

import requests as http_requests
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from mangum import Mangum

# ---------------------------------------------------------------------------
# Environment detection
# ---------------------------------------------------------------------------

ENVIRONMENT = os.getenv("ENVIRONMENT", "local")

if ENVIRONMENT == "local":
    from dotenv import load_dotenv
    load_dotenv('../../secrets/pursuitdocs/backend/.env')

# Import after env is loaded
from graph import build_graph

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:5173").split(",")
RECAPTCHA_SECRET_KEY = os.getenv("RECAPTCHA_SECRET_KEY", "")
RECAPTCHA_THRESHOLD = float(os.getenv("RECAPTCHA_THRESHOLD", "0.5"))

ALLOWED_DOMAINS = [".gov", ".edu", ".org", ".us"]
MAX_FILE_SIZE_MB = 10
RATE_LIMIT_WINDOW = 3600  # 1 hour
RATE_LIMIT_MAX = 10  # requests per window per IP


# ---------------------------------------------------------------------------
# Cold start: S3 downloads (production only)
# ---------------------------------------------------------------------------

def download_chroma_from_s3():
    """Download Chroma DB from S3 to /tmp on Lambda cold start."""
    import boto3

    if os.path.exists("/tmp/chroma_db"):
        return  # Already downloaded from a previous invocation

    s3 = boto3.client("s3")
    bucket = os.getenv("CHROMA_S3_BUCKET")
    prefix = "chroma_db/"

    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            local_path = os.path.join("/tmp", key)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            s3.download_file(bucket, key, local_path)


def download_firm_profile_from_s3() -> str:
    """Download the firm profile JSON from S3 to /tmp on Lambda cold start.

    The specific profile is selected via the FIRM_PROFILE_S3_KEY env var
    (e.g. 'firm-profiles/acme-cpa/profile.json'), making it easy to switch
    firms by updating only the Lambda environment variable.

    Returns the local path to the downloaded file.
    """
    import boto3

    local_path = "/tmp/firm_profile.json"
    if os.path.exists(local_path):
        return local_path  # Already downloaded from a previous invocation

    s3 = boto3.client("s3")
    bucket = os.getenv("CHROMA_S3_BUCKET")
    key = os.getenv("FIRM_PROFILE_S3_KEY")  # e.g. "firm-profiles/acme-cpa/profile.json"
    s3.download_file(bucket, key, local_path)
    return local_path


if ENVIRONMENT == "local":
    FIRM_PROFILE_PATH = os.getenv("FIRM_PROFILE_PATH", "../data/firm_profile.json")
else:
    download_chroma_from_s3()
    FIRM_PROFILE_PATH = download_firm_profile_from_s3()


# ---------------------------------------------------------------------------
# Rate limiting + production AWS clients
# ---------------------------------------------------------------------------

if ENVIRONMENT == "local":
    # Simple in-memory rate limiter (resets on restart)
    rate_limit_store = {}

    def check_rate_limit(ip: str) -> bool:
        """In-memory rate limiter. Returns True if allowed."""
        now = time.time()

        # Clean expired entries
        expired = [k for k, v in rate_limit_store.items() if now - v["window_start"] > RATE_LIMIT_WINDOW]
        for k in expired:
            del rate_limit_store[k]

        if ip not in rate_limit_store:
            rate_limit_store[ip] = {"count": 1, "window_start": now}
            return True

        entry = rate_limit_store[ip]
        if now - entry["window_start"] > RATE_LIMIT_WINDOW:
            rate_limit_store[ip] = {"count": 1, "window_start": now}
            return True

        if entry["count"] >= RATE_LIMIT_MAX:
            return False

        entry["count"] += 1
        return True

else:
    import boto3

    dynamodb = boto3.resource("dynamodb")
    rate_table = dynamodb.Table(os.getenv("DYNAMODB_TABLE"))
    jobs_table = dynamodb.Table(os.getenv("JOBS_TABLE"))
    lambda_client = boto3.client("lambda")
    s3_client = boto3.client("s3")
    TEMP_UPLOADS_BUCKET = os.getenv("CHROMA_S3_BUCKET")
    WORKER_LAMBDA_ARN = os.getenv("WORKER_LAMBDA_ARN")

    def check_rate_limit(ip: str) -> bool:
        """DynamoDB-backed rate limiter. Returns True if allowed."""
        now = int(time.time())
        window_start = now - RATE_LIMIT_WINDOW

        response = rate_table.get_item(Key={"ip": ip})
        item = response.get("Item")

        if not item or item.get("window_start", 0) < window_start:
            rate_table.put_item(Item={
                "ip": ip,
                "count": 1,
                "window_start": now,
                "expires_at": now + RATE_LIMIT_WINDOW + 3600,
            })
            return True

        if item.get("count", 0) >= RATE_LIMIT_MAX:
            return False

        rate_table.update_item(
            Key={"ip": ip},
            UpdateExpression="SET #c = #c + :inc",
            ExpressionAttributeNames={"#c": "count"},
            ExpressionAttributeValues={":inc": 1},
        )
        return True


# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="PursuitDocs API",
    description="AI-powered audit proposal letter generation",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load firm profile once at startup
with open(FIRM_PROFILE_PATH) as f:
    FIRM_PROFILE = json.load(f)

# Build graph once at startup
GRAPH = build_graph()

# Local dev job store — mirrors DynamoDB jobs_table for production
if ENVIRONMENT == "local":
    local_jobs: dict = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def verify_recaptcha(token: str) -> bool:
    """Verify reCAPTCHA v3 token with Google."""
    if not RECAPTCHA_SECRET_KEY:
        # Skip verification in development
        return True

    try:
        response = http_requests.post(
            "https://www.google.com/recaptcha/api/siteverify",
            data={
                "secret": RECAPTCHA_SECRET_KEY,
                "response": token,
            },
            timeout=10,
        )
        result = response.json()
        return result.get("success", False) and result.get("score", 0) >= RECAPTCHA_THRESHOLD
    except Exception:
        return False


def validate_url(url: str) -> str:
    """Validate and return the URL, or raise HTTPException."""
    if not url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="Only http and https URLs are allowed.")

    from urllib.parse import urlparse
    parsed = urlparse(url)
    hostname = parsed.hostname.lower() if parsed.hostname else ""

    if not any(hostname.endswith(domain) for domain in ALLOWED_DOMAINS):
        raise HTTPException(
            status_code=400,
            detail=f"Only URLs from approved domains are accepted ({', '.join(ALLOWED_DOMAINS)})."
        )

    return url


def _run_pipeline(rfp_source: str) -> dict:
    """Run the LangGraph pipeline and return a serializable result dict."""
    result = GRAPH.invoke({
        "rfp_source": rfp_source,
        "firm_profile": FIRM_PROFILE,
        "parsed_rfp": {},
        "current_draft": "",
        "review_result": {},
        "change_log": [],
        "iteration": 0,
        "status": "in_progress",
    })
    return {
        "status": result["status"],
        "iterations": result["iteration"],
        "final_letter": result["current_draft"],
        "change_log": result["change_log"],
        "parsed_rfp": result["parsed_rfp"],
    }


# ---------------------------------------------------------------------------
# Worker handler (production: invoked async by submit endpoint)
# ---------------------------------------------------------------------------

def _worker_handler(event: dict, _context) -> dict:
    """
    Runs the pipeline for a given job.
    Invoked directly by Lambda (not via API Gateway) with InvocationType='Event',
    so it is not subject to the 30-second API Gateway timeout.
    """
    job_id = event["job_id"]
    rfp_source = event["rfp_source"]
    tmp_path = None

    jobs_table.update_item(
        Key={"job_id": job_id},
        UpdateExpression="SET #s = :s",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":s": "processing"},
    )

    try:
        # File uploads are stashed in S3 by the submit endpoint — download now
        if rfp_source.startswith("s3-upload:"):
            s3_key = rfp_source[len("s3-upload:"):]
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.close()
            tmp_path = tmp.name
            s3_client.download_file(TEMP_UPLOADS_BUCKET, s3_key, tmp_path)
            rfp_source = tmp_path

        result = _run_pipeline(rfp_source)

        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #s = :s, #r = :r",
            ExpressionAttributeNames={"#s": "status", "#r": "result"},
            ExpressionAttributeValues={":s": "complete", ":r": result},
        )

    except Exception as e:
        jobs_table.update_item(
            Key={"job_id": job_id},
            UpdateExpression="SET #s = :s, #e = :e",
            ExpressionAttributeNames={"#s": "status", "#e": "error"},
            ExpressionAttributeValues={":s": "error", ":e": str(e)},
        )

    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
        # Clean up the temp S3 upload regardless of success/failure
        if event["rfp_source"].startswith("s3-upload:"):
            s3_key = event["rfp_source"][len("s3-upload:"):]
            try:
                s3_client.delete_object(Bucket=TEMP_UPLOADS_BUCKET, Key=s3_key)
            except Exception:
                pass

    return {"job_id": job_id}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/health")
def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "pursuitdocs"}


@app.post("/api/submit")
async def submit_rfp(
    request: Request,
    name: str = Form(...),
    email: str = Form(...),
    purpose: str = Form(...),
    recaptcha_token: str = Form(...),
    rfp_url: Optional[str] = Form(None),
    rfp_file: Optional[UploadFile] = File(None),
):
    """
    Submit an RFP for processing.

    Validates the request and fires an async worker Lambda (production) or runs
    synchronously (local dev). Returns {job_id} immediately — poll
    GET /api/status/{job_id} for the result.
    """

    # Rate limiting
    client_ip = request.client.host
    if not check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Please try again later."
        )

    # reCAPTCHA verification
    if not verify_recaptcha(recaptcha_token):
        raise HTTPException(status_code=403, detail="reCAPTCHA verification failed.")

    # Validate input — need either a URL or a file, not both
    if not rfp_url and not rfp_file:
        raise HTTPException(status_code=400, detail="Please provide an RFP URL or upload a PDF file.")

    if rfp_url and rfp_file:
        raise HTTPException(status_code=400, detail="Please provide either a URL or a file, not both.")

    job_id = str(uuid.uuid4())

    # Determine rfp_source
    if rfp_url:
        rfp_source = validate_url(rfp_url)
    else:
        if rfp_file.content_type != "application/pdf":
            raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

        content = await rfp_file.read()
        size_mb = len(content) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise HTTPException(
                status_code=400,
                detail=f"File size ({size_mb:.1f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit."
            )

        if not content[:5] == b"%PDF-":
            raise HTTPException(status_code=400, detail="File does not appear to be a valid PDF.")

        if ENVIRONMENT == "local":
            # Save to /tmp — worker runs in the same process
            tmp = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
            tmp.write(content)
            tmp.close()
            rfp_source = tmp.name
        else:
            # Upload to S3 so the async worker Lambda invocation can read it
            import io
            s3_key = f"temp-uploads/{job_id}.pdf"
            s3_client.upload_fileobj(io.BytesIO(content), TEMP_UPLOADS_BUCKET, s3_key)
            rfp_source = f"s3-upload:{s3_key}"

    # --- Local dev: run synchronously, store result in memory ---
    if ENVIRONMENT == "local":
        try:
            result = _run_pipeline(rfp_source)
            local_jobs[job_id] = {"status": "complete", "result": result}
        except Exception as e:
            local_jobs[job_id] = {"status": "error", "error": str(e)}
        finally:
            if rfp_source and rfp_source.startswith("/tmp/") and os.path.exists(rfp_source):
                os.unlink(rfp_source)
        return {"job_id": job_id, "status": local_jobs[job_id]["status"]}

    # --- Production: write pending job, fire async worker ---
    now = int(time.time())
    jobs_table.put_item(Item={
        "job_id": job_id,
        "status": "pending",
        "created_at": now,
        "expires_at": now + 86400,  # 24-hour TTL
    })

    lambda_client.invoke(
        FunctionName=WORKER_LAMBDA_ARN,
        InvocationType="Event",  # fire-and-forget — not subject to API GW timeout
        Payload=json.dumps({"job_id": job_id, "rfp_source": rfp_source}).encode(),
    )

    return {"job_id": job_id, "status": "pending"}


@app.get("/api/status/{job_id}")
def get_job_status(job_id: str):
    """Poll for the status and result of a submitted job."""
    if ENVIRONMENT == "local":
        item = local_jobs.get(job_id)
        if not item:
            raise HTTPException(status_code=404, detail="Job not found.")
        return {"job_id": job_id, **item}

    response = jobs_table.get_item(Key={"job_id": job_id})
    item = response.get("Item")
    if not item:
        raise HTTPException(status_code=404, detail="Job not found.")

    return {
        "job_id": job_id,
        "status": item["status"],           # pending | processing | complete | error
        "result": item.get("result"),       # present when complete
        "error": item.get("error"),         # present when error
    }


@app.post("/api/export-docx")
async def export_docx(
    request: Request,
    letter_text: str = Form(...),
):
    """Export a letter as a Word document."""
    from fastapi.responses import Response
    from graph.utils.export import letter_to_docx

    try:
        docx_bytes = letter_to_docx(letter_text)
        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": "attachment; filename=proposal_letter.docx"
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Export error: {str(e)}")


# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

_mangum_handler = Mangum(app, lifespan="off")


def handler(event, context):
    """
    Lambda entry point.

    Routes direct worker invocations (fired by the submit endpoint) to
    _worker_handler. All other events (HTTP traffic from API Gateway) go
    through FastAPI via Mangum as normal.
    """
    if "job_id" in event and "requestContext" not in event and "httpMethod" not in event:
        return _worker_handler(event, context)
    return _mangum_handler(event, context)
