from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from analysis.models import Analysis
from analysis.views import get_resume_or_404
from interviews import service
from interviews.llm import AIUnavailable
from interviews.models import InterviewSession
from interviews.serializers import AnswerSerializer, InterviewSessionSerializer, StartInterviewSerializer
from jobfit_api.exceptions import AIUnavailableError, InterviewFinishedError, TurnConflictError

# WHY no list endpoint: listing by resume would show every visitor's answers
# on the shared demo resume. The browser remembers its own interview ids.


def _sessions():
    return InterviewSession.objects.prefetch_related("messages")


def _get_session_or_404(pk):
    try:
        return _sessions().get(pk=pk)
    except (InterviewSession.DoesNotExist, DjangoValidationError):
        raise NotFound(f"No interview with id {pk}.")


def _respond(session, status_code=status.HTTP_200_OK):
    session = _sessions().get(pk=session.pk)
    return Response(InterviewSessionSerializer(session).data, status=status_code)


class StartInterviewView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "interview_start"

    def post(self, request):
        serializer = StartInterviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        analysis = None
        resume = None
        if data.get("analysis_id"):
            try:
                analysis = Analysis.objects.select_related("resume", "job_description").get(id=data["analysis_id"])
            except Analysis.DoesNotExist:
                raise NotFound(f"No analysis with id {data['analysis_id']}.")
        elif data.get("resume_id"):
            resume = get_resume_or_404(data["resume_id"])

        # The demo resume is allowed: an interview never shows up in its history.
        try:
            session = service.start_interview(
                resume=resume, analysis=analysis, jd_text=data["jd_text"], role=data["role"],
            )
        except AIUnavailable:
            raise AIUnavailableError()
        return _respond(session, status.HTTP_201_CREATED)


class InterviewDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = InterviewSessionSerializer

    def get_object(self):
        return _get_session_or_404(self.kwargs["pk"])


class AnswerView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "interview_turn"

    def post(self, request, pk):
        session = _get_session_or_404(pk)
        serializer = AnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            session = service.submit_answer(session, serializer.validated_data["text"], serializer.validated_data["turn"])
        except service.InterviewFinished:
            raise InterviewFinishedError()
        except service.TurnConflict:
            raise TurnConflictError()
        except AIUnavailable:
            raise AIUnavailableError()
        return _respond(session)


class FinishView(APIView):
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "interview_turn"

    def post(self, request, pk):
        session = _get_session_or_404(pk)
        try:
            session = service.finish_interview(session)
        except AIUnavailable:
            raise AIUnavailableError()
        return _respond(session)
