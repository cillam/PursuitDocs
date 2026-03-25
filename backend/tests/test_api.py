"""
API endpoint tests for PursuitDocs.

All tests run with ENVIRONMENT=local, which uses:
  - In-memory rate limiting (reset between tests by conftest)
  - Synchronous pipeline execution via the mocked graph
  - In-memory job store (local_jobs dict)

The reCAPTCHA secret key is unset in tests, so verify_recaptcha() always
returns True — it's tested separately in test_validation.py.
"""

import pytest

VALID_URL = "https://example.gov/rfp-audit-services.pdf"

VALID_FORM = {
    "name": "Jane Smith",
    "email": "jane@testfirm.com",
    "purpose": "Evaluating the tool for our firm",
    "recaptcha_token": "test-token",
    "rfp_url": VALID_URL,
    "company_website": "",  # honeypot — must be empty for valid submissions
}

# Minimal valid PDF (passes the b"%PDF-" magic byte check)
MINIMAL_PDF = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
    b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
)


# ── /api/health ───────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self, client):
        assert client.get("/api/health").status_code == 200

    def test_response_shape(self, client):
        data = client.get("/api/health").json()
        assert data["status"] == "ok"
        assert data["service"] == "pursuitdocs"


# ── /api/submit — URL input ───────────────────────────────────────────────────

class TestSubmitUrl:
    def test_valid_gov_url_returns_job_id(self, client):
        r = client.post("/api/submit", data=VALID_FORM)
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_valid_org_url_accepted(self, client):
        data = {**VALID_FORM, "rfp_url": "https://nonprofit.org/rfp.pdf"}
        assert client.post("/api/submit", data=data).status_code == 200

    def test_valid_edu_url_accepted(self, client):
        data = {**VALID_FORM, "rfp_url": "https://university.edu/rfp.pdf"}
        assert client.post("/api/submit", data=data).status_code == 200

    def test_valid_us_url_accepted(self, client):
        data = {**VALID_FORM, "rfp_url": "https://state.agency.us/rfp.pdf"}
        assert client.post("/api/submit", data=data).status_code == 200

    def test_com_url_rejected(self, client):
        data = {**VALID_FORM, "rfp_url": "https://example.com/rfp.pdf"}
        r = client.post("/api/submit", data=data)
        assert r.status_code == 400
        assert "approved domains" in r.json()["detail"]

    def test_net_url_rejected(self, client):
        data = {**VALID_FORM, "rfp_url": "https://example.net/rfp.pdf"}
        assert client.post("/api/submit", data=data).status_code == 400

    def test_ftp_url_rejected(self, client):
        data = {**VALID_FORM, "rfp_url": "ftp://example.gov/rfp.pdf"}
        assert client.post("/api/submit", data=data).status_code == 400

    def test_http_url_accepted(self, client):
        data = {**VALID_FORM, "rfp_url": "http://example.gov/rfp.pdf"}
        assert client.post("/api/submit", data=data).status_code == 200

    def test_subdomain_gov_accepted(self, client):
        data = {**VALID_FORM, "rfp_url": "https://www.cityoftest.gov/rfp.pdf"}
        assert client.post("/api/submit", data=data).status_code == 200

    def test_local_mode_returns_complete_status(self, client):
        r = client.post("/api/submit", data=VALID_FORM)
        assert r.json()["status"] == "complete"

    def test_neither_url_nor_file_rejected(self, client):
        data = {k: v for k, v in VALID_FORM.items() if k != "rfp_url"}
        r = client.post("/api/submit", data=data)
        assert r.status_code == 400

    def test_both_url_and_file_rejected(self, client):
        r = client.post(
            "/api/submit",
            data=VALID_FORM,
            files={"rfp_file": ("test.pdf", MINIMAL_PDF, "application/pdf")},
        )
        assert r.status_code == 400


# ── /api/submit — file input ──────────────────────────────────────────────────

FILE_FORM = {
    "name": "Jane Smith",
    "email": "jane@testfirm.com",
    "purpose": "Evaluating the tool",
    "recaptcha_token": "test-token",
}


class TestSubmitFile:
    def test_valid_pdf_accepted(self, client):
        r = client.post(
            "/api/submit",
            data=FILE_FORM,
            files={"rfp_file": ("rfp.pdf", MINIMAL_PDF, "application/pdf")},
        )
        assert r.status_code == 200
        assert "job_id" in r.json()

    def test_non_pdf_content_type_rejected(self, client):
        r = client.post(
            "/api/submit",
            data=FILE_FORM,
            files={"rfp_file": ("doc.docx", b"fake content", "application/msword")},
        )
        assert r.status_code == 400
        assert "PDF" in r.json()["detail"]

    def test_oversized_file_rejected(self, client):
        # Build a file whose content starts with PDF magic bytes but is >10 MB
        large = b"%PDF-" + b"x" * (11 * 1024 * 1024)
        r = client.post(
            "/api/submit",
            data=FILE_FORM,
            files={"rfp_file": ("large.pdf", large, "application/pdf")},
        )
        assert r.status_code == 400
        assert "size" in r.json()["detail"].lower()

    def test_invalid_pdf_magic_bytes_rejected(self, client):
        r = client.post(
            "/api/submit",
            data=FILE_FORM,
            files={"rfp_file": ("fake.pdf", b"not a real pdf", "application/pdf")},
        )
        assert r.status_code == 400
        assert "valid PDF" in r.json()["detail"]


# ── /api/submit — security guards ────────────────────────────────────────────

class TestSubmitGuards:
    def test_honeypot_rejected(self, client):
        data = {**VALID_FORM, "company_website": "https://spam.com"}
        assert client.post("/api/submit", data=data).status_code == 400

    def test_rate_limit_enforced(self, client):
        import main
        for _ in range(main.RATE_LIMIT_MAX):
            client.post("/api/submit", data=VALID_FORM)
        r = client.post("/api/submit", data=VALID_FORM)
        assert r.status_code == 429
        assert "Rate limit" in r.json()["detail"]

    def test_missing_required_fields_returns_422(self, client):
        # FastAPI form validation (missing name/email/purpose/recaptcha_token)
        r = client.post("/api/submit", data={"rfp_url": VALID_URL})
        assert r.status_code == 422


# ── /api/status/{job_id} ─────────────────────────────────────────────────────

class TestStatus:
    def test_unknown_job_returns_404(self, client):
        assert client.get("/api/status/does-not-exist").status_code == 404

    def test_completed_job_returns_result(self, client):
        job_id = client.post("/api/submit", data=VALID_FORM).json()["job_id"]
        r = client.get(f"/api/status/{job_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "complete"

    def test_result_contains_expected_fields(self, client):
        job_id = client.post("/api/submit", data=VALID_FORM).json()["job_id"]
        result = client.get(f"/api/status/{job_id}").json()["result"]
        assert "status" in result
        assert "final_letter" in result
        assert "change_log" in result
        assert "parsed_rfp" in result
        assert "iterations" in result

    def test_pipeline_error_stored_in_job(self, client, mock_graph):
        mock_graph.invoke.side_effect = RuntimeError("LLM unavailable")
        try:
            job_id = client.post("/api/submit", data=VALID_FORM).json()["job_id"]
            r = client.get(f"/api/status/{job_id}").json()
            assert r["status"] == "error"
            assert "LLM unavailable" in r["error"]
        finally:
            mock_graph.invoke.side_effect = None
            mock_graph.invoke.return_value = {
                "status": "ready_for_review",
                "current_draft": "Dear Selection Committee,...",
                "change_log": [],
                "parsed_rfp": {},
                "iteration": 1,
            }

    def test_job_id_present_in_status_response(self, client):
        job_id = client.post("/api/submit", data=VALID_FORM).json()["job_id"]
        r = client.get(f"/api/status/{job_id}").json()
        assert r["job_id"] == job_id


# ── /api/export-docx ─────────────────────────────────────────────────────────

class TestExportDocx:
    LETTER = "Dear Selection Committee,\n\nWe are pleased to submit this proposal.\n\nSincerely,\nTest Firm"

    def test_returns_200(self, client):
        assert client.post("/api/export-docx", data={"letter_text": self.LETTER}).status_code == 200

    def test_returns_docx_content_type(self, client):
        r = client.post("/api/export-docx", data={"letter_text": self.LETTER})
        assert "wordprocessingml" in r.headers["content-type"]

    def test_returns_non_empty_bytes(self, client):
        r = client.post("/api/export-docx", data={"letter_text": self.LETTER})
        assert len(r.content) > 0

    def test_content_disposition_attachment(self, client):
        r = client.post("/api/export-docx", data={"letter_text": self.LETTER})
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert ".docx" in cd

    def test_missing_letter_text_returns_422(self, client):
        assert client.post("/api/export-docx", data={}).status_code == 422
