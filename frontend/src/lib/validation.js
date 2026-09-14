import { MAX_UPLOAD_BYTES } from "./limits.js";

/** A message explaining why this file can't be uploaded, or null if it can. */
export function validateResumeFile(file) {
  if (!file) {
    return "Choose a PDF file.";
  }
  const isPdf = file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) {
    return `"${file.name}" isn't a PDF. Save your resume as a PDF and try again.`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    const megabytes = (file.size / (1024 * 1024)).toFixed(1);
    return `This PDF is ${megabytes} MB. The limit is 5 MB.`;
  }
  return null;
}
