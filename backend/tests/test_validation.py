"""
Unit tests for the pure validation helpers in main.py:
  - validate_url
  - verify_recaptcha
  - check_rate_limit (in-memory variant)
"""

from unittest.mock import patch
import pytest
from fastapi import HTTPException

import main


# ── validate_url ──────────────────────────────────────────────────────────────

class TestValidateUrl:
    def test_gov_url_accepted(self):
        url = "https://example.gov/rfp.pdf"
        assert main.validate_url(url) == url

    def test_edu_url_accepted(self):
        assert main.validate_url("https://university.edu/rfp.pdf") is not None

    def test_org_url_accepted(self):
        assert main.validate_url("https://nonprofit.org/rfp.pdf") is not None

    def test_us_url_accepted(self):
        assert main.validate_url("https://state.us/rfp.pdf") is not None

    def test_returns_original_url_unchanged(self):
        url = "https://cityoftest.gov/documents/rfp-audit-2024.pdf"
        assert main.validate_url(url) == url

    def test_subdomain_of_allowed_domain_accepted(self):
        assert main.validate_url("https://www.cityoftest.gov/rfp.pdf") is not None

    def test_deep_subdomain_accepted(self):
        assert main.validate_url("https://finance.dept.cityoftest.gov/rfp.pdf") is not None

    def test_com_domain_rejected(self):
        with pytest.raises(HTTPException) as exc:
            main.validate_url("https://example.com/rfp.pdf")
        assert exc.value.status_code == 400
        assert "approved domains" in exc.value.detail

    def test_net_domain_rejected(self):
        with pytest.raises(HTTPException):
            main.validate_url("https://example.net/rfp.pdf")

    def test_io_domain_rejected(self):
        with pytest.raises(HTTPException):
            main.validate_url("https://example.io/rfp.pdf")

    def test_ftp_scheme_rejected(self):
        with pytest.raises(HTTPException) as exc:
            main.validate_url("ftp://example.gov/rfp.pdf")
        assert exc.value.status_code == 400
        assert "http" in exc.value.detail.lower()

    def test_http_scheme_accepted(self):
        assert main.validate_url("http://example.gov/rfp.pdf") is not None

    def test_url_with_query_string_accepted(self):
        assert main.validate_url("https://example.gov/rfp.pdf?version=2") is not None

    def test_fake_gov_suffix_rejected(self):
        # example.govfake.com should NOT match .gov
        with pytest.raises(HTTPException):
            main.validate_url("https://example.govfake.com/rfp.pdf")


# ── verify_recaptcha ──────────────────────────────────────────────────────────

class TestVerifyRecaptcha:
    def test_returns_true_when_no_secret_key(self):
        """Development mode: empty secret key bypasses verification."""
        original = main.RECAPTCHA_SECRET_KEY
        main.RECAPTCHA_SECRET_KEY = ""
        try:
            assert main.verify_recaptcha("any-token") is True
        finally:
            main.RECAPTCHA_SECRET_KEY = original

    def test_returns_true_on_high_score(self):
        with patch("main.http_requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"success": True, "score": 0.9}
            main.RECAPTCHA_SECRET_KEY = "test-secret"
            try:
                assert main.verify_recaptcha("valid-token") is True
            finally:
                main.RECAPTCHA_SECRET_KEY = ""

    def test_returns_true_on_score_at_threshold(self):
        with patch("main.http_requests.post") as mock_post:
            mock_post.return_value.json.return_value = {
                "success": True,
                "score": main.RECAPTCHA_THRESHOLD,
            }
            main.RECAPTCHA_SECRET_KEY = "test-secret"
            try:
                assert main.verify_recaptcha("threshold-token") is True
            finally:
                main.RECAPTCHA_SECRET_KEY = ""

    def test_returns_false_on_low_score(self):
        with patch("main.http_requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"success": True, "score": 0.1}
            main.RECAPTCHA_SECRET_KEY = "test-secret"
            try:
                assert main.verify_recaptcha("spam-token") is False
            finally:
                main.RECAPTCHA_SECRET_KEY = ""

    def test_returns_false_on_google_failure(self):
        with patch("main.http_requests.post") as mock_post:
            mock_post.return_value.json.return_value = {"success": False, "score": 0.0}
            main.RECAPTCHA_SECRET_KEY = "test-secret"
            try:
                assert main.verify_recaptcha("bad-token") is False
            finally:
                main.RECAPTCHA_SECRET_KEY = ""

    def test_returns_false_on_network_error(self):
        with patch("main.http_requests.post", side_effect=Exception("Network error")):
            main.RECAPTCHA_SECRET_KEY = "test-secret"
            try:
                assert main.verify_recaptcha("any-token") is False
            finally:
                main.RECAPTCHA_SECRET_KEY = ""


# ── check_rate_limit ──────────────────────────────────────────────────────────

class TestCheckRateLimit:
    def test_first_request_allowed(self):
        main.rate_limit_store.clear()
        assert main.check_rate_limit("1.2.3.4") is True

    def test_requests_within_limit_allowed(self):
        main.rate_limit_store.clear()
        for _ in range(main.RATE_LIMIT_MAX):
            assert main.check_rate_limit("1.2.3.4") is True

    def test_request_over_limit_blocked(self):
        main.rate_limit_store.clear()
        for _ in range(main.RATE_LIMIT_MAX):
            main.check_rate_limit("1.2.3.4")
        assert main.check_rate_limit("1.2.3.4") is False

    def test_different_ips_tracked_independently(self):
        main.rate_limit_store.clear()
        for _ in range(main.RATE_LIMIT_MAX):
            main.check_rate_limit("1.2.3.4")
        # Different IP should still be allowed
        assert main.check_rate_limit("9.9.9.9") is True

    def test_expired_window_resets_count(self):
        import time
        main.rate_limit_store.clear()
        ip = "1.2.3.4"
        for _ in range(main.RATE_LIMIT_MAX):
            main.check_rate_limit(ip)
        # Manually expire the window
        main.rate_limit_store[ip]["window_start"] = time.time() - main.RATE_LIMIT_WINDOW - 1
        assert main.check_rate_limit(ip) is True
