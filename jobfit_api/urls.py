from django.contrib import admin
from django.urls import include, path, re_path

from jobfit_api import views

api_patterns = [
    path("health/", views.health, name="health"),
    path("", include("resumes.urls")),
    path("", include("analysis.urls")),
    # WHY a catch-all: with DEBUG on, Django answers unknown URLs with an HTML
    # debug page. Anything under /api/ should get the JSON error shape instead,
    # in every environment.
    re_path(r"^.*$", views.api_not_found),
]

urlpatterns = [
    path("", views.root, name="root"),
    path("admin/", admin.site.urls),
    path("api/", include(api_patterns)),
]

handler404 = "jobfit_api.views.api_not_found"
handler500 = "jobfit_api.views.server_error"
