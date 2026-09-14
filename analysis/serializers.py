from rest_framework import serializers

from analysis.models import Analysis, JobDescription

# WHY 50: fewer characters than a sentence or two can't describe a job, and
# the analysis would be scoring noise.
MIN_JD_CHARACTERS = 50
# WHY 20,000: real JDs are 2-6k characters. The cap bounds the CPU a single
# anonymous request can spend on tokenising and matching.
MAX_JD_CHARACTERS = 20_000


class AnalyzeRequestSerializer(serializers.Serializer):
    resume_id = serializers.UUIDField()
    jd_text = serializers.CharField(min_length=MIN_JD_CHARACTERS, max_length=MAX_JD_CHARACTERS)
    title = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")
    company = serializers.CharField(required=False, allow_blank=True, max_length=255, default="")


class JobDescriptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDescription
        fields = ["id", "title", "company", "raw_text", "created_at"]


class JobDescriptionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = JobDescription
        fields = ["id", "title", "company"]


class AnalysisSerializer(serializers.ModelSerializer):
    resume_id = serializers.UUIDField(read_only=True)
    job_description = JobDescriptionSerializer(read_only=True)

    class Meta:
        model = Analysis
        fields = [
            "id",
            "resume_id",
            "job_description",
            "overall_score",
            "similarity_score",
            "matched_skills",
            "missing_skills",
            "category_scores",
            "suggestions",
            "created_at",
        ]


class AnalysisSummarySerializer(serializers.ModelSerializer):
    """For history lists: everything a table row needs, none of the long text."""

    resume_id = serializers.UUIDField(read_only=True)
    job_description = JobDescriptionSummarySerializer(read_only=True)
    matched_count = serializers.SerializerMethodField()
    missing_count = serializers.SerializerMethodField()

    class Meta:
        model = Analysis
        fields = [
            "id",
            "resume_id",
            "job_description",
            "overall_score",
            "similarity_score",
            "matched_count",
            "missing_count",
            "created_at",
        ]

    def get_matched_count(self, analysis):
        return len(analysis.matched_skills)

    def get_missing_count(self, analysis):
        return len(analysis.missing_skills)
