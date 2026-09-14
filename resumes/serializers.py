from rest_framework import serializers

from resumes.models import Resume

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
PDF_MAGIC_BYTES = b"%PDF-"
PREVIEW_CHARACTERS = 500


class ResumeUploadSerializer(serializers.Serializer):
    file = serializers.FileField()

    def validate_file(self, uploaded):
        if uploaded.size == 0:
            raise serializers.ValidationError("The file is empty.")
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise serializers.ValidationError("The file is larger than the 5 MB limit.")

        # WHY magic bytes instead of the extension or Content-Type: both are
        # chosen by the client. Renaming malware.exe to resume.pdf changes the
        # extension, and any HTTP client can send "application/pdf". Every PDF
        # starts with "%PDF-", so reading the first five bytes checks what the
        # file actually is. Extraction still has to succeed afterwards; this
        # only rejects obvious non-PDFs before any parser touches them.
        header = uploaded.read(len(PDF_MAGIC_BYTES))
        uploaded.seek(0)
        if header != PDF_MAGIC_BYTES:
            raise serializers.ValidationError("The file is not a PDF.")
        return uploaded


class ResumeSerializer(serializers.ModelSerializer):
    text_length = serializers.SerializerMethodField()
    text_preview = serializers.SerializerMethodField()
    analysis_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Resume
        fields = ["id", "filename", "created_at", "text_length", "text_preview", "analysis_count"]

    def get_text_length(self, resume):
        return len(resume.extracted_text)

    def get_text_preview(self, resume):
        return resume.extracted_text[:PREVIEW_CHARACTERS]


class ResumeDetailSerializer(ResumeSerializer):
    class Meta(ResumeSerializer.Meta):
        # The full text is only sent for one resume at a time; the list stays
        # small by sending previews.
        fields = ResumeSerializer.Meta.fields + ["extracted_text"]
