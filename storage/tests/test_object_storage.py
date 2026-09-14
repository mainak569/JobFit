import logging

import pytest

from storage import object_storage


@pytest.fixture
def no_storage_credentials(settings, tmp_path):
    for name in object_storage.REQUIRED_STORAGE_SETTINGS:
        setattr(settings, name, "")
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def test_missing_credentials_fall_back_to_local_media_with_warning(no_storage_credentials, caplog):
    caplog.set_level(logging.WARNING, logger="storage.object_storage")

    key = object_storage.upload_file("resumes/abc.pdf", b"%PDF-1.4 fake")

    assert key == "resumes/abc.pdf"
    assert (no_storage_credentials / "resumes" / "abc.pdf").read_bytes() == b"%PDF-1.4 fake"
    assert "Object storage is not configured" in caplog.text
    assert "STORAGE_BUCKET" in caplog.text

    assert object_storage.presigned_url(key) == "/media/resumes/abc.pdf"

    object_storage.delete_file(key)
    assert not (no_storage_credentials / "resumes" / "abc.pdf").exists()
    # Deleting again is not an error.
    object_storage.delete_file(key)


def test_partial_credentials_still_fall_back(no_storage_credentials, settings):
    settings.STORAGE_BUCKET = "jobfit-resumes"
    assert not object_storage.is_configured()
    object_storage.upload_file("resumes/partial.pdf", b"x")
    assert (no_storage_credentials / "resumes" / "partial.pdf").exists()


def test_local_fallback_rejects_keys_that_escape_media_root(no_storage_credentials):
    with pytest.raises(ValueError):
        object_storage.upload_file("../outside.pdf", b"x")


def test_presigned_url_is_signed_short_lived_and_uses_the_region(settings):
    settings.STORAGE_ENDPOINT = "https://s3.us-west-004.backblazeb2.com"
    settings.STORAGE_REGION = "us-west-004"
    settings.STORAGE_BUCKET = "jobfit-resumes"
    settings.STORAGE_ACCESS_KEY_ID = "test-key"
    settings.STORAGE_SECRET_ACCESS_KEY = "test-secret"

    # Signing happens locally, so no network access is needed.
    url = object_storage.presigned_url("resumes/abc.pdf")

    assert url.startswith("https://s3.us-west-004.backblazeb2.com/jobfit-resumes/resumes/abc.pdf?")
    assert "X-Amz-Signature=" in url
    assert "X-Amz-Expires=900" in url
    assert "us-west-004" in url
