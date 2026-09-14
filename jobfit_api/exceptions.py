"""
One error shape for the whole API:

    {"error": {"code": "not_found", "message": "No resume with that id."}}

Validation errors also carry "fields" with the per-field messages, so a form
can put each message next to its input.
"""

from django.http import Http404, JsonResponse
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler


class ScannedPDF(APIException):
    # WHY 422 rather than 400: the request was well-formed and the file really
    # is a PDF; the server understood it but can't process its content.
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "scanned_pdf"
    default_detail = "The PDF has no selectable text and needs OCR."


class UnreadablePDF(APIException):
    status_code = status.HTTP_422_UNPROCESSABLE_ENTITY
    default_code = "unreadable_pdf"
    default_detail = "The file could not be read as a PDF."


class DemoReadOnly(APIException):
    # WHY the demo is read-only: every visitor shares the one demo resume. If
    # anyone could delete its analyses, the demo would break for the next
    # visitor; if anyone could analyze new JDs against it, whatever they pasted
    # would appear in every other visitor's history.
    status_code = status.HTTP_403_FORBIDDEN
    default_code = "demo_read_only"
    default_detail = "The sample resume is read-only. Upload your own resume to analyze a new job description."


def _first_message(detail):
    """Pull one human-readable sentence out of DRF's nested error detail."""
    if isinstance(detail, list):
        if not detail:
            return "Invalid request."
        return _first_message(detail[0])
    if isinstance(detail, dict):
        if not detail:
            return "Invalid request."
        field, value = next(iter(detail.items()))
        message = _first_message(value)
        if field in ("detail", "non_field_errors"):
            return message
        return f"{field}: {message}"
    return str(detail)


def _error_code(exc):
    if isinstance(exc, ValidationError):
        return "validation_error"
    # Django's Http404 is converted to a response by DRF but has no code.
    if isinstance(exc, Http404):
        return "not_found"
    return getattr(exc, "default_code", "error")


def api_exception_handler(exc, context):
    response = exception_handler(exc, context)
    if response is None:
        # Not an API exception: let Django turn it into a 500, which
        # jobfit_api.views.server_error renders in the same shape.
        return None

    error = {"code": _error_code(exc), "message": _first_message(response.data)}
    if isinstance(exc, ValidationError) and isinstance(response.data, dict):
        error["fields"] = response.data
    response.data = {"error": error}
    return response


def error_response(code, message, status_code):
    """Same shape, for plain Django views outside DRF."""
    return JsonResponse({"error": {"code": code, "message": message}}, status=status_code)
