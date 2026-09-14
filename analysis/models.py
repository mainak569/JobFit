import uuid

from django.db import models

from resumes.models import Resume


class JobDescription(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255, blank=True)
    company = models.CharField(max_length=255, blank=True)
    raw_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.title and self.company:
            return f"{self.title} @ {self.company}"
        return self.title or self.company or f"Job description {self.id}"


class Analysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resume = models.ForeignKey(Resume, on_delete=models.CASCADE, related_name="analyses")
    job_description = models.ForeignKey(JobDescription, on_delete=models.CASCADE)
    overall_score = models.IntegerField()  # 0-100, clamped to 5-97 by the scorer
    similarity_score = models.FloatField()  # raw TF-IDF cosine, 0-1

    # WHY JSONField instead of related tables: these lists are only ever read
    # whole, to render one analysis or one column of the compare view. Nothing
    # queries an individual element. Normalising into AnalysisSkill rows would
    # mean a join (or a prefetch) on every read and a bulk insert on every
    # write, with no query it makes possible that we currently need.
    #
    # What would force normalising: a question across analyses, such as "how
    # many analyses were missing Docker" or "most common gaps for frontend
    # JDs". JSON containment lookups can technically answer that in Postgres,
    # but without a proper table and index they scan every row.
    matched_skills = models.JSONField(default=list)
    missing_skills = models.JSONField(default=list)
    category_scores = models.JSONField(default=dict)
    suggestions = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "analyses"
        # WHY this index: the history view is "analyses for this resume,
        # newest first". A composite index on (resume, -created_at) answers
        # that with one index scan instead of filtering and then sorting.
        indexes = [models.Index(fields=["resume", "-created_at"])]

    def __str__(self):
        return f"{self.resume} vs {self.job_description}: {self.overall_score}"
