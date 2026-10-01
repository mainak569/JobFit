from rest_framework import serializers

from analysis.serializers import MAX_JD_CHARACTERS, MIN_JD_CHARACTERS
from interviews.models import InterviewMessage, InterviewSession
from interviews.roles import ROLE_FILES

MAX_ANSWER_CHARACTERS = 4_000


class StartInterviewSerializer(serializers.Serializer):
    """Either {analysis_id}, or any of {resume_id, jd_text | role}."""

    analysis_id = serializers.UUIDField(required=False)
    resume_id = serializers.UUIDField(required=False)
    jd_text = serializers.CharField(
        required=False, allow_blank=True, default="",
        min_length=MIN_JD_CHARACTERS, max_length=MAX_JD_CHARACTERS,
    )
    role = serializers.ChoiceField(choices=sorted(ROLE_FILES), required=False, allow_blank=True, default="")

    def validate(self, data):
        if data.get("analysis_id"):
            if data.get("resume_id") or data["jd_text"] or data["role"]:
                raise serializers.ValidationError(
                    "Send analysis_id on its own: the analysis already has the resume and job description."
                )
            return data
        if data["jd_text"] and data["role"]:
            raise serializers.ValidationError("Choose a role or paste a job description, not both.")
        if not (data.get("resume_id") or data["jd_text"] or data["role"]):
            raise serializers.ValidationError("Choose a resume, a role or a job description to interview for.")
        return data


class AnswerSerializer(serializers.Serializer):
    text = serializers.CharField(max_length=MAX_ANSWER_CHARACTERS, trim_whitespace=True)
    turn = serializers.IntegerField(min_value=0)


class InterviewMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = InterviewMessage
        fields = ["order", "speaker", "text", "question_index", "is_follow_up"]


class InterviewSessionSerializer(serializers.ModelSerializer):
    resume_id = serializers.UUIDField(read_only=True)
    analysis_id = serializers.UUIDField(read_only=True)
    question_count = serializers.SerializerMethodField()
    questions_done = serializers.BooleanField(read_only=True)
    turn = serializers.SerializerMethodField()
    messages = InterviewMessageSerializer(many=True, read_only=True)

    class Meta:
        model = InterviewSession
        fields = [
            "id",
            "resume_id",
            "analysis_id",
            "title",
            "status",
            "question_count",
            "current_question",
            "questions_done",
            "turn",
            "messages",
            "report",
            "overall_score",
            "created_at",
        ]

    def get_question_count(self, session):
        return len(session.plan)

    def get_turn(self, session):
        return len(session.messages.all())
