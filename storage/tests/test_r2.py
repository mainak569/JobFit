import logging

import pytest

from storage import r2


@pytest.fixture
def no_r2_credentials(settings, tmp_path):
    settings.R2_ACCESS_KEY_ID = ""
    settings.R2_SECRET_ACCESS_KEY = ""
    settings.R2_BUCKET = ""
    settings.R2_ENDPOINT = ""
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def test_missing_credentials_fall_back_to_local_media_with_warning(no_r2_credentials, caplog):
    caplog.set_level(logging.WARNING, logger="storage.r2")

    key = r2.upload_file("resumes/abc.pdf", b"%PDF-1.4 fake")

    assert key == "resumes/abc.pdf"
    assert (no_r2_credentials / "resumes" / "abc.pdf").read_bytes() == b"%PDF-1.4 fake"
    assert "R2 is not configured" in caplog.text
    assert "R2_BUCKET" in caplog.text

    assert r2.presigned_url(key) == "/media/resumes/abc.pdf"

    r2.delete_file(key)
    assert not (no_r2_credentials / "resumes" / "abc.pdf").exists()
    # Deleting again is not an error.
    r2.delete_file(key)


def test_local_fallback_rejects_keys_that_escape_media_root(no_r2_credentials):
    with pytest.raises(ValueError):
        r2.upload_file("../outside.pdf", b"x")


def test_presigned_url_is_signed_and_short_lived_when_configured(settings):
    settings.R2_ACCESS_KEY_ID = "test-key"
    settings.R2_SECRET_ACCESS_KEY = "test-secret"
    settings.R2_BUCKET = "jobfit-resumes"
    settings.R2_ENDPOINT = "https://example.r2.cloudflarestorage.com"

    # Signing happens locally, so no network access is needed.
    url = r2.presigned_url("resumes/abc.pdf")

    assert url.startswith("https://example.r2.cloudflarestorage.com/jobfit-resumes/resumes/abc.pdf?")
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=900" in url
