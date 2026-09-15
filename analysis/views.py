import uuid

from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from analysis.demo import is_demo_resume
from analysis.models import Analysis, JobDescription
from analysis.serializers import AnalysisSerializer, AnalysisSummarySerializer, AnalyzeRequestSerializer
from analysis.service import run_analysis
from jobfit_api.exceptions import DemoReadOnly
from resumes.models import Resume


def parse_resume_id(request):
    """Read the required ?resume_id= query parameter as a UUID."""
    raw_value = request.query_params.get("resume_id", "").strip()
    if not raw_value:
        raise ValidationError({"resume_id": ["This query parameter is required."]})
    try:
        return uuid.UUID(raw_value)
    except ValueError:
        raise ValidationError({"resume_id": ["Must be a valid UUID."]})


def get_resume_or_404(resume_id):
    try:
        return Resume.objects.get(id=resume_id)
    except Resume.DoesNotExist:
        raise NotFound(f"No resume with id {resume_id}.")


class AnalyzeView(APIView):
    """POST {resume_id, jd_text, title?, company?} -> the full saved analysis."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "analyze"

    def post(self, request):
        serializer = AnalyzeRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        resume = get_resume_or_404(data["resume_id"])
        if is_demo_resume(resume.id):
            raise DemoReadOnly()
        analysis, _result = run_analysis(
            resume,
            data["jd_text"],
            title=data["title"],
            company=data["company"],
        )
        return Response(AnalysisSerializer(analysis).data, status=status.HTTP_201_CREATED)


class AnalysisListView(generics.ListAPIView):
    """GET ?resume_id= -> analyses newest first, paginated."""

    serializer_class = AnalysisSummarySerializer

    def get_queryset(self):
        # select_related: one query for analyses and their JD titles, rather
        # than one extra query per row.
        # WHY resume_id is required: without it this would list every
        # visitor's analyses to anyone, the same leak as a public resume list.
        resume_id = parse_resume_id(self.request)
        return (
            Analysis.objects.filter(resume_id=resume_id)
            .select_related("job_description")
            .order_by("-created_at")
        )


class AnalysisDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = AnalysisSerializer
    queryset = Analysis.objects.select_related("job_description")

    def perform_destroy(self, analysis):
        if is_demo_resume(analysis.resume_id):
            raise DemoReadOnly()
        with transaction.atomic():
            job_description_id = analysis.job_description_id
            analysis.delete()
            # A JD is created per analysis; remove it once nothing uses it.
            JobDescription.objects.filter(id=job_description_id, analysis__isnull=True).delete()


PRESENT = "present"
INFERRED = "inferred"
ABSENT = "absent"


class CompareView(APIView):
    """
    GET ?resume_id= -> one resume against all its JDs, shaped as a table:

        columns: one per analysis (newest first)
        rows:    one per skill any of those JDs asked for
        cells:   rows[i].cells[j] is "present", "inferred" (implied by another
                 skill on the resume), "absent", or null when JD j didn't
                 ask for skill i at all
    """

    def get(self, request):
        resume_id = parse_resume_id(request)
        resume = get_resume_or_404(resume_id)
        analyses = list(
            Analysis.objects.filter(resume=resume)
            .select_related("job_description")
            .order_by("-created_at")
        )

        columns = []
        for analysis in analyses:
            columns.append({
                "analysis_id": analysis.id,
                "job_description_id": analysis.job_description_id,
                "title": analysis.job_description.title,
                "company": analysis.job_description.company,
                "overall_score": analysis.overall_score,
                "created_at": analysis.created_at,
            })

        rows_by_skill = {}
        for column_index, analysis in enumerate(analyses):
            for skill in analysis.matched_skills:
                row = self._row_for(rows_by_skill, skill, len(analyses))
                # .get(): analyses saved before inference existed have no key.
                row["cells"][column_index] = INFERRED if skill.get("inferred_from") else PRESENT
            for skill in analysis.missing_skills:
                row = self._row_for(rows_by_skill, skill, len(analyses))
                row["cells"][column_index] = ABSENT

        rows = list(rows_by_skill.values())
        # Skills asked for by the most JDs first: those matter most when
        # deciding what to learn or add. Name breaks ties so order is stable.
        rows.sort(key=lambda row: (-self._times_asked(row), row["name"].lower()))

        return Response({
            "resume": {"id": resume.id, "filename": resume.filename},
            "columns": columns,
            "rows": rows,
        })

    @staticmethod
    def _row_for(rows_by_skill, skill, column_count):
        name = skill["name"]
        if name not in rows_by_skill:
            rows_by_skill[name] = {
                "name": name,
                "category": skill["category"],
                "cells": [None] * column_count,
            }
        return rows_by_skill[name]

    @staticmethod
    def _times_asked(row):
        return sum(1 for cell in row["cells"] if cell is not None)
