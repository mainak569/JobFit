from django.urls import path

from interviews import views

urlpatterns = [
    path("interviews/", views.StartInterviewView.as_view(), name="interview-start"),
    path("interviews/<str:pk>/", views.InterviewDetailView.as_view(), name="interview-detail"),
    path("interviews/<str:pk>/answer/", views.AnswerView.as_view(), name="interview-answer"),
    path("interviews/<str:pk>/finish/", views.FinishView.as_view(), name="interview-finish"),
]
