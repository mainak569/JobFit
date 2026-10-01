import uuid

from django.db import models

from analysis.models import Analysis
from resumes.models import Resume


class InterviewSession(models.Model):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    STATUS_CHOICES = [(IN_PROGRESS, "In progress"), (COMPLETED, "Completed")]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    resume = models.ForeignKey(Resume, null=True, blank=True, on_delete=models.CASCADE, related_name="interviews")
    # SET_NULL: deleting an analysis keeps the interview; jd_text is a copy.
    analysis = models.ForeignKey(Analysis, null=True, blank=True, on_delete=models.SET_NULL, related_name="interviews")
    title = models.CharField(max_length=255, blank=True)
    jd_text = models.TextField(blank=True)

    # Planner slots plus the AI's question: [{"kind", "focus", "reason", "question"}]
    plan = models.JSONField(default=list)
    current_question = models.IntegerField(default=0)
    follow_up_asked = models.BooleanField(default=False)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=IN_PROGRESS)
    report = models.JSONField(null=True, blank=True)
    overall_score = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def questions_done(self):
        return self.current_question >= len(self.plan)

    def __str__(self):
        return f"Interview: {self.title or 'untitled'} ({self.status})"


class InterviewMessage(models.Model):
    INTERVIEWER = "interviewer"
    CANDIDATE = "candidate"
    SPEAKER_CHOICES = [(INTERVIEWER, "Interviewer"), (CANDIDATE, "Candidate")]

    # WHY rows, not JSON on the session: the unique (session, order) constraint
    # stops a double-clicked Send from saving the same turn twice.
    session = models.ForeignKey(InterviewSession, on_delete=models.CASCADE, related_name="messages")
    order = models.PositiveIntegerField()
    speaker = models.CharField(max_length=20, choices=SPEAKER_CHOICES)
    text = models.TextField()
    question_index = models.IntegerField(null=True, blank=True)
    is_follow_up = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["session", "order"], name="unique_message_order_per_session"),
        ]

    def __str__(self):
        return f"{self.speaker} #{self.order}"
