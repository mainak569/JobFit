import logging

from django.db import transaction
from django.db.models import Count
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from analysis.demo import is_demo_resume
from analysis.extractor import PDFExtractionError, ScannedPDFError
from analysis.models import JobDescription
from analysis.service import create_resume
from jobfit_api.exceptions import DemoReadOnly, ScannedPDF, UnreadablePDF
from resumes.models import Resume
from resumes.serializers import ResumeDetailSerializer, ResumeSerializer, ResumeUploadSerializer
from storage import object_storage

logger = logging.getLogger(__name__)


class ResumeUploadView(APIView):
    """
    POST: upload a PDF (multipart field "file").

    WHY there is no GET list here: the API has no accounts, so a public list of
    resumes would show every visitor's uploads, contact details included, to
    anyone. Instead a resume is only reachable by its random UUID, which the
    uploader's browser keeps. Knowing the id is the permission. That is not
    real access control (anyone given the id can read it), but it stops
    browsing and enumeration, which is the realistic risk for a public demo.
    """

    parser_classes = [MultiPartParser]

    def post(self, request):
        upload = ResumeUploadSerializer(data=request.data)
        upload.is_valid(raise_exception=True)
        uploaded_file = upload.validated_data["file"]

        try:
            resume = create_resume(uploaded_file.name[:255], uploaded_file.read())
        except ScannedPDFError as exc:
            raise ScannedPDF(str(exc)) from exc
        except PDFExtractionError as exc:
            raise UnreadablePDF(str(exc)) from exc

        resume.analysis_count = 0
        return Response(ResumeSerializer(resume).data, status=status.HTTP_201_CREATED)


class ResumeDetailView(generics.RetrieveDestroyAPIView):
    """GET: one resume with its full extracted text. DELETE: remove it and its file."""

    serializer_class = ResumeDetailSerializer

    def get_queryset(self):
        return Resume.objects.annotate(analysis_count=Count("analyses"))

    def perform_destroy(self, resume):
        if is_demo_resume(resume.id):
            raise DemoReadOnly()
        storage_key = resume.storage_key

        with transaction.atomic():
            job_description_ids = list(resume.analyses.values_list("job_description_id", flat=True))
            resume.delete()  # cascades to its analyses
            # Each JD was pasted for an analysis of this resume. Once those
            # analyses are gone, nothing can reach the JD, so remove it too.
            JobDescription.objects.filter(id__in=job_description_ids, analysis__isnull=True).delete()

        # WHY delete the database row first, then the file: if storage fails
        # after the row is gone, the cost is an orphaned object in the bucket
        # (logged, cleanable later). The other order risks a row that points at
        # a file that no longer exists, which breaks for the user.
        # The seeded demo resume has no stored file, so its key is empty.
        if storage_key:
            try:
                object_storage.delete_file(storage_key)
            except Exception:
                logger.exception("Deleted resume %s but could not delete object %s", resume.pk, storage_key)
