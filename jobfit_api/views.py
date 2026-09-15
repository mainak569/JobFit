from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
from rest_framework.response import Response

from jobfit_api.exceptions import error_response


@api_view(["GET"])
def health(request):
    # WHY no database check: this is hit by an uptime pinger every few minutes
    # to keep the free-tier instance awake. It should answer "is the process
    # up" as cheaply as possible, not open a DB connection each time.
    return Response({"status": "ok"})


@api_view(["GET"])
def root(request):
    # WHY a response at "/": Render probes the root URL after every deploy.
    # With no route there, each probe logged a "Not Found" warning that looked
    # like a real error. A small status reply keeps the logs clean and tells
    # anyone who opens the API's address where the endpoints are.
    return Response({"status": "ok", "service": "jobfit-api", "api": "/api/"})


# WHY csrf_exempt: this is a plain Django view, so CsrfViewMiddleware checks
# it. A POST or DELETE to an unknown /api/ path would otherwise get Django's
# HTML 403 page instead of a JSON 404. The view changes nothing, so skipping
# CSRF here is safe.
@csrf_exempt
def api_not_found(request, exception=None):
    return error_response("not_found", f"No endpoint at {request.path}.", 404)


def server_error(request):
    # Never include exception details here; they go to the logs, not the client.
    return error_response("server_error", "Something went wrong on our side. Please try again.", 500)
