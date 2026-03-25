"""
Pytest configuration for PursuitDocs backend tests.

Module-level setup runs before any test file is collected:
  - Sets ENVIRONMENT=local so main.py uses in-memory stores
  - Creates a temporary firm profile JSON file
  - Mocks the graph package so LangGraph/Chroma/LLMs never actually run
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

# ── Must happen before main.py is imported ────────────────────────────────────

os.environ["ENVIRONMENT"] = "local"
os.environ["RECAPTCHA_SECRET_KEY"] = ""  # disable reCAPTCHA verification in tests

# Create a temp firm profile and point the env var at it
_profile = {
    "firm_name": "Tesseract & Partners LLP",
    "tagline": "Precision. Independence. Trust.",
    "services": ["Financial statement audits", "SOC 1/2/3 reporting", "Cybersecurity audits"],
    "sectors": ["Technology", "Life Sciences", "Government/Nonprofit"],
    "contact": {
        "name": "Alex Chen",
        "title": "Assurance Partner",
        "email": "achen@tesseract.cpa",
        "phone": "(555) 867-5309",
    },
}
_profile_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
json.dump(_profile, _profile_file)
_profile_file.close()
os.environ["FIRM_PROFILE_PATH"] = _profile_file.name

# Mock the graph package so chromadb/OpenAI/Anthropic are never imported
_mock_graph_instance = MagicMock()
_mock_graph_instance.invoke.return_value = {
    "status": "ready_for_review",
    "current_draft": "Dear Selection Committee,\n\nWe are pleased to submit this proposal.",
    "change_log": [],
    "parsed_rfp": {"summary": "Annual financial audit for City of Testville"},
    "iteration": 1,
}
_mock_build_graph = MagicMock(return_value=_mock_graph_instance)

_mock_export = MagicMock()
_mock_export.letter_to_docx.return_value = b"PK\x03\x04fake_docx_bytes"
_mock_graph_utils = MagicMock()
_mock_graph_utils.export = _mock_export

sys.modules["graph"] = MagicMock(build_graph=_mock_build_graph)
sys.modules["graph.utils"] = _mock_graph_utils
sys.modules["graph.utils.export"] = _mock_export

# ── Fixtures ──────────────────────────────────────────────────────────────────

import pytest  # noqa: E402  (must come after sys.modules patch)


@pytest.fixture(autouse=True)
def reset_stores():
    """Clear in-memory state between every test."""
    import main
    main.rate_limit_store.clear()
    main.local_jobs.clear()
    yield
    main.rate_limit_store.clear()
    main.local_jobs.clear()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    import main
    return TestClient(main.app)


@pytest.fixture
def mock_graph():
    """Return the mock graph instance so tests can override return values."""
    return _mock_graph_instance
