const API_URL = (import.meta.env.VITE_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");

async function request(path, options = {}) {
  let response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      headers: { "Content-Type": "application/json", ...(options.headers || {}) },
      ...options,
    });
  } catch {
    throw new Error("Can't connect to the backend. Check that FastAPI is running on port 8000.");
  }

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = payload.detail;
    throw new Error(typeof detail === "string" ? detail : "The request failed. Please try again.");
  }
  return payload;
}

export const api = {
  health: () => request("/api/health"),
  generateQuiz: (data) => request("/api/quiz/generate", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  submitQuiz: (data) => request("/api/quiz/submit", {
    method: "POST",
    body: JSON.stringify(data),
  }),
  history: () => request("/api/history"),
  historyItem: (id) => request(`/api/history/${id}`),
};
