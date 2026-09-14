/**
 * The only module that knows the API's URLs and error format.
 *
 * Every function returns parsed JSON or throws an ApiError with a stable
 * `code` (from the backend's {"error": {"code", "message"}} shape) and a
 * message that is safe to show to the user as-is.
 */

const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api").replace(/\/+$/, "");

export class ApiError extends Error {
  constructor({ code, message, status, fields = null }) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.fields = fields;
  }
}

function networkError() {
  return new ApiError({
    code: "network_error",
    message: "Couldn't reach the server. Check your connection and try again.",
    status: 0,
  });
}

function errorFromResponse(status, body) {
  if (body && body.error) {
    return new ApiError({
      code: body.error.code,
      message: body.error.message,
      status,
      fields: body.error.fields ?? null,
    });
  }
  return new ApiError({
    code: "server_error",
    message: `The server sent an unexpected response (${status}). Try again in a moment.`,
    status,
  });
}

/** Network failures and 5xx can succeed on a second attempt; a 404 or 400 won't. */
export function isRetryable(error) {
  if (!error) return false;
  return error.status === 0 || error.status >= 500;
}

async function request(path, { method = "GET", body } = {}) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, options);
  } catch {
    throw networkError();
  }

  if (response.status === 204) {
    return null;
  }

  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }

  if (!response.ok) {
    throw errorFromResponse(response.status, data);
  }
  return data;
}

/**
 * Upload a resume PDF, reporting progress as a fraction from 0 to 1.
 *
 * WHY XMLHttpRequest instead of fetch: fetch has no upload progress events.
 * Its streams API can report download progress, but a request body's upload
 * progress isn't exposed in browsers. XHR's `upload.onprogress` is still the
 * only way to show a real progress bar, and a 5 MB PDF on a slow mobile
 * connection takes long enough that a bar matters.
 */
export function uploadResume(file, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_BASE_URL}/resumes/`);
    xhr.responseType = "json";

    xhr.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) {
        onProgress(event.loaded / event.total);
      }
    });

    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(xhr.response);
      } else {
        reject(errorFromResponse(xhr.status, xhr.response));
      }
    });

    xhr.addEventListener("error", () => reject(networkError()));

    const form = new FormData();
    form.append("file", file);
    xhr.send(form);
  });
}

export function pingHealth() {
  return request("/health/");
}

export function getResume(resumeId) {
  return request(`/resumes/${resumeId}/`);
}

export function analyze({ resumeId, jdText, title, company }) {
  return request("/analyze/", {
    method: "POST",
    body: { resume_id: resumeId, jd_text: jdText, title, company },
  });
}

export function listAnalyses(resumeId, page = 1) {
  return request(`/analyses/?resume_id=${encodeURIComponent(resumeId)}&page=${page}`);
}

export function getAnalysis(analysisId) {
  return request(`/analyses/${analysisId}/`);
}

export function deleteAnalysis(analysisId) {
  return request(`/analyses/${analysisId}/`, { method: "DELETE" });
}

export function compareResume(resumeId) {
  return request(`/compare/?resume_id=${encodeURIComponent(resumeId)}`);
}
