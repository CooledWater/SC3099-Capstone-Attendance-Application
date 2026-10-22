const API_BASE_URL = (
  import.meta.env["VITE_API_BASE_URL"] ?? "/api/v1"
).replace(/\/$/, "");
let accessToken: string | null = null;
// Remove credentials persisted by previous dashboard versions. New tokens
// remain in memory; the HttpOnly refresh cookie restores them after reload.
try {
  localStorage.removeItem("saiv.access-token");
  localStorage.removeItem("saiv.dashboard.access-token");
} catch {
  // Authentication also works when browser storage access is restricted.
}
const SIGNED_OUT_KEY = "saiv.dashboard.signed-out";
let refreshInFlight: Promise<boolean> | null = null;
let restorationInFlight: Promise<CurrentUser | null> | null = null;

export type AppRole = "student" | "ta" | "instructor" | "admin";

export type CurrentUser = {
  id: string;
  email: string;
  full_name: string;
  role: AppRole;
};

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

function getAccessToken() {
  return accessToken;
}

export function clearAccessToken() {
  accessToken = null;
}

async function request<T>(
  path: string,
  init: RequestInit & { timeoutMs?: number } = {},
  retry = true,
  responseType: "json" | "text" | "response" = "json",
): Promise<T> {
  const { timeoutMs = 15000, ...fetchOptions } = init;
  const token = getAccessToken();
  const controller = new AbortController();
  let timedOut = false;
  const timeout = window.setTimeout(() => { timedOut = true; controller.abort(); }, timeoutMs);
  const abortFromCaller = () => controller.abort();
  if (init.signal?.aborted) controller.abort();
  else init.signal?.addEventListener("abort", abortFromCaller, { once: true });
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...fetchOptions,
      signal: controller.signal,
      credentials: "include",
      headers: {
        Accept: "application/json",
        ...(init.body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
    if (
      response.status === 401 &&
      retry &&
      !path.startsWith("/auth/") &&
      (await refreshDashboard())
    ) {
      return await request<T>(path, init, false, responseType);
    }
    if (!response.ok) {
      const payload = (await response.json().catch(() => null)) as {
        detail?: string;
        message?: string;
      } | null;
      throw new ApiError(
        response.status,
        payload?.detail ?? payload?.message ?? `Request failed (${response.status})`,
      );
    }
    if (response.status === 204) return undefined as T;
    if (responseType === "response") {
      // Read the body while timeout/caller cancellation still apply. The caller
      // receives the same server bytes and headers in a consumable response.
      const body = await response.blob();
      return new Response(body, {
        status: response.status,
        statusText: response.statusText,
        headers: response.headers,
      }) as T;
    }
    if (responseType === "text") return (await response.text()) as T;
    return (await response.json()) as T;
  } catch (error) {
    if (timedOut) {
      const saving = init.method && !["GET", "HEAD"].includes(init.method.toUpperCase());
      throw new ApiError(408, saving
        ? "The server took too long to respond. The save may have completed; check the list before trying again."
        : "The server took too long to respond. Please try again.");
    }
    throw error;
  } finally {
    window.clearTimeout(timeout);
    init.signal?.removeEventListener("abort", abortFromCaller);
  }
}

async function obtainSession(path: string) {
  const result = await request<{ access_token: string }>(path, { method: "POST" }, false);
  accessToken = result.access_token;
}

function refreshDashboard(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = obtainSession("/auth/dashboard/refresh")
      .then(() => true)
      .catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 401) {
          clearAccessToken();
          return false;
        }
        throw error;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function restoreSession(): Promise<CurrentUser | null> {
  if (sessionStorage.getItem(SIGNED_OUT_KEY)) return null;
  if (!(await refreshDashboard())) {
    try {
      await obtainSession("/auth/dashboard/student-session");
    } catch (error) {
      if (error instanceof ApiError && (error.status === 401 || error.status === 403)) return null;
      throw error;
    }
  }
  return request<CurrentUser>("/users/me");
}

export const api = {
  request,
  response: (path: string, init: RequestInit = {}) =>
    request<Response>(path, init, true, "response"),
  text: (path: string) => request<string>(path, { headers: { Accept: "text/csv" } }, true, "text"),
  restoreSession() {
    if (!restorationInFlight) {
      restorationInFlight = restoreSession().finally(() => {
        restorationInFlight = null;
      });
    }
    return restorationInFlight;
  },
  async login(email: string, password: string) {
    const result = await request<{ access_token: string; user: CurrentUser }>(
      "/auth/dashboard/login",
      {
        method: "POST",
        body: JSON.stringify({ email, password }),
      },
    );
    accessToken = result.access_token;
    sessionStorage.removeItem(SIGNED_OUT_KEY);
    return result.user;
  },
  async register(input: { email: string; password: string; full_name: string; role: AppRole }) {
    return request<CurrentUser>("/auth/register", { method: "POST", body: JSON.stringify(input) });
  },
  me: () => request<CurrentUser>("/users/me"),
  async logout() {
    // Prevent the still-valid SAIV student session from immediately signing
    // the user back in when the authentication page mounts after logout.
    sessionStorage.setItem(SIGNED_OUT_KEY, "true");
    try {
      await request<void>("/auth/dashboard/logout", { method: "POST" });
    } finally {
      clearAccessToken();
    }
  },
};
