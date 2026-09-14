import uuid

from django.db import models


class Resume(models.Model):
    # WHY UUID primary keys: these ids go into public API URLs
    # (/api/resumes/<id>/). Sequential integers would let anyone walk through
    # other people's resumes by counting upwards.
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    filename = models.CharField(max_length=255)
    # WHY store the object key, not a URL: files are served through presigned
    # links generated on demand, and those expire after minutes. A stored
    # presigned URL would be dead by the next request; a stored public URL
    # would make the resume readable by anyone who ever saw it. The key is the
    # stable identifier; the URL is derived fresh each time it is needed.
    storage_key = models.CharField(max_length=512)
    extracted_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.filename
