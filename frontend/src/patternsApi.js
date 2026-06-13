// Thin API client for the Pattern Recognition backend (the standalone
// patterns service). Local dev talks to it directly on :8003. In production
// (ECS + ALB) set VITE_PATTERNS_API_BASE to the gateway/ALB path, e.g.
// "https://<alb-host>/patterns".
const BASE = import.meta.env.VITE_PATTERNS_API_BASE || "http://localhost:8003";

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`${res.status} ${res.statusText} — ${text}`);
  }
  // 204 / empty bodies
  const ct = res.headers.get("content-type") || "";
  return ct.includes("application/json") ? res.json() : null;
}

export const api = {
  health: () => request("/health"),

  getState: (householdId) => request(`/state/${householdId}`),

  getPatterns: (householdId) => request(`/patterns/${householdId}`),

  // `at` is an optional "HH:MM" simulated clock value.
  getContext: (householdId, at) =>
    request(
      `/context/${householdId}${at ? `?at=${encodeURIComponent(at)}` : ""}`,
    ),

  // Evaluate a user-supplied what-if state against the learned patterns.
  // This powers the "set the state + clock, then hit Go" flow: the supplied
  // device states are compared to the patterns in-memory only (nothing is
  // persisted, so repeated evaluations never pollute the demo data).
  evaluate: (
    householdId,
    { at, activeDevices, peopleHome, deviceOnSince } = {},
  ) =>
    request(`/context/${householdId}/evaluate`, {
      method: "POST",
      body: JSON.stringify({
        current_time: at || null,
        active_devices: activeDevices || [],
        people_home: peopleHome || {},
        device_on_since: deviceOnSince || {},
      }),
    }),

  // Turn a context object into a natural, spoken-style "Alexa says…" line.
  // The backend uses Groq when GROQ_API_KEY is set, else a deterministic
  // fallback sentence. Returns { alexa_response, llm_powered, reasoning }.
  narrate: (context) =>
    request(`/context/narrate`, {
      method: "POST",
      body: JSON.stringify(context),
    }),

  // Fetch events for a household. With no options it returns the full
  // chronological history (the backend paginates); pass { since, limit } to
  // constrain the window or grab only the latest N.
  getEvents: (householdId, { since, limit } = {}) => {
    const params = new URLSearchParams({ household_id: householdId });
    if (since) params.set("since", since);
    if (limit) params.set("limit", String(limit));
    return request(`/events?${params.toString()}`);
  },

  postEvent: (event) =>
    request("/events", { method: "POST", body: JSON.stringify(event) }),

  seed: (householdId) =>
    request(`/admin/seed/${householdId}`, { method: "POST" }),
};

export { BASE as API_BASE };
