from django.urls import path

from resumes import views

urlpatterns = [
    path("resumes/", views.ResumeUploadView.as_view(), name="resume-upload"),
    # WHY <str:pk> and not <uuid:pk>: a malformed id with <uuid:> fails URL
    # routing and falls through to the catch-all. With <str:> it reaches DRF's
    # get_object, which turns an invalid UUID into the same 404 as a missing one.
    path("resumes/<str:pk>/", views.ResumeDetailView.as_view(), name="resume-detail"),
]
