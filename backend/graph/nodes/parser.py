"""
parser.py

Extracts structured data from RFPs for the drafter agent.

Accepts three input types:
    - HTML URL: fetches and extracts main content
    - PDF URL: downloads and extracts text (first 30 pages)
    - PDF file path: extracts text (first 30 pages)

Outputs:
    {
        "proposal_instructions": "...",
        "purpose_and_services": "...",
        "entity_background": "...",
        "addressee": {
            "name": "...",
            "title": "...",
            "organization": "...",
            "address": "...",
            "phone": "...",
            "email": "..."
        },
        "summary": "..."
    }

Usage (run from backend/):
    python -m graph.nodes.parser <url_or_filepath>
    python -m graph.nodes.parser https://example.gov/rfp-audit-services.pdf
    python -m graph.nodes.parser ../data/test_rfps/some_rfp.pdf
"""

import argparse
import json
import os
import re
import tempfile

import pdfplumber
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from langdetect import detect

ENV_LOC = '../../secrets/pursuitdocs/backend/.env'
MODEL = "claude-sonnet-4-20250514"
MAX_PDF_PAGES = 30
MAX_FILE_SIZE_MB = 10
MIN_TEXT_LENGTH = 500
REQUIRED_KEYWORDS = ["request for proposal", "audit", "financial statements"]


# ---------------------------------------------------------------------------
# Input detection
# ---------------------------------------------------------------------------

def detect_input_type(source: str) -> str:
    """Detect whether the source is an HTML URL, PDF URL, or local PDF file.
    
    Returns: 'html_url', 'pdf_url', or 'pdf_file'
    """
    if os.path.isfile(source):
        return "pdf_file"
    
    if source.startswith("http://") or source.startswith("https://"):
        if source.lower().endswith(".pdf"):
            return "pdf_url"
        return "html_url"
    
    raise ValueError(f"Cannot determine input type for: {source}")


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_from_pdf(filepath: str, max_pages: int = MAX_PDF_PAGES) -> str:
    """Extract text from a PDF file using pdfplumber.
    
    Extracts up to max_pages pages.
    """
    pages_text = []
    with pdfplumber.open(filepath) as pdf:
        for i, page in enumerate(pdf.pages):
            if i >= max_pages:
                break
            text = page.extract_text()
            if text:
                pages_text.append(text)
    
    return "\n\n".join(pages_text)


def extract_from_pdf_url(url: str, max_pages: int = MAX_PDF_PAGES) -> str:
    """Download a PDF from a URL and extract text."""
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    # Check downloaded file size
    size_mb = len(response.content) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(
            f"Downloaded PDF ({size_mb:.1f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit."
        )
    
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(response.content)
        tmp_path = tmp.name
    
    try:
        text = extract_from_pdf(tmp_path, max_pages)
    finally:
        os.unlink(tmp_path)
    
    return text


def extract_from_html(url: str) -> str:
    """Fetch an HTML page and extract the main content.
    
    Tries to isolate the main content area by looking for common
    content containers. Falls back to full page text.
    """
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    
    soup = BeautifulSoup(response.text, "html.parser")
    
    # Remove obvious non-content elements
    for tag in soup.find_all(["nav", "header", "footer", "script", "style", "noscript"]):
        tag.decompose()
    
    # Try common main content containers
    main_content = (
        soup.find("main") or
        soup.find("article") or
        soup.find(id="page-content") or
        soup.find(id="main-content") or
        soup.find(id="content") or
        soup.find(class_="entry-content") or
        soup.find(role="main")
    )
    
    if main_content:
        text = main_content.get_text(separator="\n", strip=True)
    else:
        # Fallback: use the body with nav/header/footer already removed
        body = soup.find("body")
        text = body.get_text(separator="\n", strip=True) if body else soup.get_text(separator="\n", strip=True)
    
    # Clean up excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text


def extract_text(source: str) -> str:
    """Extract text from the source based on its type."""
    input_type = detect_input_type(source)
    
    if input_type == "pdf_file":
        print(f"Extracting text from PDF file: {source}")
        return extract_from_pdf(source)
    elif input_type == "pdf_url":
        print(f"Downloading and extracting PDF from: {source}")
        return extract_from_pdf_url(source)
    elif input_type == "html_url":
        print(f"Fetching HTML from: {source}")
        return extract_from_html(source)
    else:
        raise ValueError(f"Unknown input type: {input_type}")


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_file_size(source: str) -> None:
    """Check that a local PDF file is under the size limit.
    
    Only applies to local files — URL content is checked after download.
    """
    if os.path.isfile(source):
        size_mb = os.path.getsize(source) / (1024 * 1024)
        if size_mb > MAX_FILE_SIZE_MB:
            raise ValueError(
                f"File size ({size_mb:.1f} MB) exceeds the {MAX_FILE_SIZE_MB} MB limit."
            )


def validate_text_length(text: str) -> None:
    """Check that extracted text meets the minimum length."""
    if len(text) < MIN_TEXT_LENGTH:
        raise ValueError(
            f"Extracted text is too short ({len(text)} characters). "
            f"Minimum is {MIN_TEXT_LENGTH} characters. "
            "The document may be empty, image-only, or not a valid RFP."
        )


def validate_keywords(text: str) -> None:
    """Check that the text contains all required keywords (case-insensitive).
    
    All keywords must appear at least once.
    """
    text_lower = text.lower()
    missing = [kw for kw in REQUIRED_KEYWORDS if kw not in text_lower]
    if missing:
        raise ValueError(
            "This document does not appear to be a Request for Proposal for audit services. "
            "Please verify you have uploaded the correct document and try again."
        )


def validate_language(text: str) -> None:
    """Check that the text is in English."""
    # Use a sample from the beginning of the text for faster detection
    sample = text[:3000]
    try:
        lang = detect(sample)
    except Exception:
        # If detection fails, let it through rather than blocking
        return
    
    if lang != "en":
        raise ValueError(
            f"Document does not appear to be in English (detected: {lang}). "
            "Only English-language RFPs are supported."
        )


def validate_document(source: str, text: str) -> None:
    """Run all validation checks on the source and extracted text.
    
    Raises ValueError if any check fails.
    """
    validate_file_size(source)
    validate_text_length(text)
    validate_keywords(text)
    validate_language(text)


# ---------------------------------------------------------------------------
# LLM extraction
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert at reading Requests for Proposals (RFPs) for audit services. 

Your task is to extract structured information from an RFP. First, you must verify that the document you have received is a legitimate RFP for financial audit services. If the document you have received is an RFP for financial audit services, extract the following five fields:

1. **proposal_instructions**: An object with two subfields:
   - instructions: How the proposal should be formatted, what sections to include, submission requirements, page limits, number of copies, and any other instructions for preparing the proposal.
   - submission_deadline: The deadline for submitting the proposal, including date and time if specified. Use the exact wording from the RFP.

2. **purpose_and_services**: What audit services are being requested, for what entity, what fiscal years, what standards apply (GAAS, GASB, etc.), and any specific deliverables or scope items.

3. **entity_background**: Description of the requesting entity — what they are, their size, budget, organizational structure, accounting systems used, number of employees/departments, and any other relevant background.

4. **addressee**: Who the proposal should be directed to. Extract:
   - name: The contact person's name
   - title: Their title/position
   - organization: The organization name
   - address: Full mailing address
   - phone: Phone number
   - email: Email address

5. **summary**: An executive summary of the RFP, emphasizing what stands out and any important information not included in the other fields, such as evaluation criteria, selection process, contract terms, or special requirements. Aim for 200-300 words, though shorter is acceptable if the RFP does not contain enough additional detail to warrant it.

Respond ONLY with valid JSON matching this exact structure. Do not include any other text, markdown formatting, or code fences. Each field should contain only information specific to that field. Do not repeat information across fields.

{
    "proposal_instructions": {
        "instructions": "...",
        "submission_deadline": "..."
    },
    "purpose_and_services": "...",
    "entity_background": "...",
    "addressee": {
        "name": "...",
        "title": "...",
        "organization": "...",
        "address": "...",
        "phone": "...",
        "email": "..."
    },
    "summary": "..."
}

If a field cannot be determined from the RFP, use "Not specified" as the value. For the addressee and proposal_instructions, use "Not specified" for any subfield that cannot be determined. If you believe the RFP to not be a legitimate request for audit services, every field should use "Not specified", except for the summary, which you should use to add an explanation of your reasoning why the RFP may not be legitimate. Such an explanation should be limited to fewer than 50 words."""


def parse_rfp(text: str) -> dict:
    """Send extracted RFP text to Claude for structured extraction.
    
    Returns a dict with the five parser fields.
    """
    llm = ChatAnthropic(model=MODEL, temperature=0, max_tokens=4096)
    
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Extract the required fields from this RFP:\n\n{text}")
    ]
    
    response = llm.invoke(messages)
    
    # Parse the JSON response
    response_text = response.content.strip()
    
    # Remove markdown code fences if present (just in case)
    response_text = re.sub(r'^```json\s*', '', response_text)
    response_text = re.sub(r'\s*```$', '', response_text)
    
    try:
        parsed = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response_text[:500]}")
    
    return parsed


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def parse(source: str) -> dict:
    """Full parser pipeline: validate, extract text, then extract fields.
    
    Args:
        source: URL or file path to an RFP
        
    Returns:
        Dict with the five parser fields
        
    Raises:
        ValueError: If validation fails (file too large, not an audit RFP, 
                    not in English, or insufficient text)
    """
    # Check file size before extraction (local files only)
    validate_file_size(source)
    
    text = extract_text(source)
    print(f"Extracted {len(text)} characters of text")
    
    # Validate extracted text
    print("Validating document...")
    validate_text_length(text)
    validate_keywords(text)
    validate_language(text)
    print("Validation passed")
    
    print("Sending to Claude for extraction...")
    result = parse_rfp(text)
    
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Parse an RFP and extract structured fields.")
    parser.add_argument("source", help="URL or file path to an RFP (HTML page, PDF URL, or local PDF)")
    parser.add_argument("--output", "-o", help="Save output to a JSON file")
    
    args = parser.parse_args()
    
    load_dotenv(ENV_LOC)
    
    try:
        result = parse(args.source)
        
        print(f"\n{'='*60}")
        print("Parser Output")
        print(f"{'='*60}")
        print(json.dumps(result, indent=2))
        
        if args.output:
            with open(args.output, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\nSaved to: {args.output}")
    
    except Exception as e:
        print(f"\n❌ Error: {e}")
        exit(1)


if __name__ == "__main__":
    main()