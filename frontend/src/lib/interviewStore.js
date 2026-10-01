// Interviews started from this browser. The API has no list endpoint (see interviews/views.py).

const STORAGE_KEY = "jobfit.interviews";
const MAX_REMEMBERED = 20;

export function getRememberedInterviews() {
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function save(interviews) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(interviews.slice(0, MAX_REMEMBERED)));
  } catch {
    // Storage unavailable; the interview still works for this visit.
  }
}

export function rememberInterview(session) {
  const entry = {
    id: session.id,
    title: session.title,
    createdAt: session.created_at,
    status: session.status,
    score: session.overall_score,
  };
  const remembered = getRememberedInterviews();
  const index = remembered.findIndex((interview) => interview.id === entry.id);
  if (index === -1) {
    save([entry, ...remembered]);
  } else {
    remembered[index] = entry;
    save(remembered);
  }
}

export function forgetInterview(interviewId) {
  save(getRememberedInterviews().filter((interview) => interview.id !== interviewId));
}
