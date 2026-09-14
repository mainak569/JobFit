// Mirrors the backend (resumes/serializers.py, analysis/serializers.py).
// WHY check these in the browser too: rejecting a 20 MB file or a two-word job
// description instantly beats uploading it and waiting for a 400. The server
// still enforces every limit; these are for feedback, not security.
export const MAX_UPLOAD_BYTES = 5 * 1024 * 1024;
export const MIN_JD_CHARACTERS = 50;
export const MAX_JD_CHARACTERS = 20000;
