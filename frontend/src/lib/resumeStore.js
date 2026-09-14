import { DEMO_RESUME_ID } from "./demo.js";

/**
 * Resumes uploaded from this browser.
 *
 * WHY the browser keeps this list: the API deliberately has no "list all
 * resumes" endpoint, because with no accounts that list would show every
 * visitor's uploads to everyone. A resume is reachable only by its random id,
 * so the browser that uploaded it remembers the id. Clearing site data forgets
 * the list; the resumes themselves stay on the server.
 */

const STORAGE_KEY = "jobfit.resumes";
const MAX_REMEMBERED = 20;

export function getRememberedResumes() {
  // localStorage can throw (private mode, blocked storage), so every access is
  // wrapped and falls back to "nothing remembered".
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function rememberResume({ id, filename, createdAt }) {
  try {
    const others = getRememberedResumes().filter((resume) => resume.id !== id);
    const updated = [{ id, filename, createdAt }, ...others].slice(0, MAX_REMEMBERED);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));
  } catch {
    // Storage unavailable: the upload still works for this visit.
  }
}

export function defaultResumeId() {
  const remembered = getRememberedResumes();
  return remembered.length > 0 ? remembered[0].id : DEMO_RESUME_ID;
}
