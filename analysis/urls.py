from django.urls import path

from analysis import views

urlpatterns = [
    path("analyze/", views.AnalyzeView.as_view(), name="analyze"),
    path("analyses/", views.AnalysisListView.as_view(), name="analysis-list"),
    path("analyses/<str:pk>/", views.AnalysisDetailView.as_view(), name="analysis-detail"),
    path("compare/", views.CompareView.as_view(), name="compare"),
]
