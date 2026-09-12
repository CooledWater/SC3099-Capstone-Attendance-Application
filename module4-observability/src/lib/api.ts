const API_BASE_URL = (
  import.meta.env["VITE_API_BASE_URL"] ?? "http://localhost:8000/api/v1"
).replace(/\/$/, "");
const ACCESS_TOKEN_KEY = "saiv.access-token";

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

export function getAccessToken() {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function clearAccessToken() {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      Accept: "application/json",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
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
  return response.json() as Promise<T>;
}

export const api = {
  request,
  async login(email: string, password: string) {
    const result = await request<{ access_token: string; user: CurrentUser }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    localStorage.setItem(ACCESS_TOKEN_KEY, result.access_token);
    return result.user;
  },
  async register(input: { email: string; password: string; full_name: string; role: AppRole }) {
    return request<CurrentUser>("/auth/register", { method: "POST", body: JSON.stringify(input) });
  },
  me: () => request<CurrentUser>("/users/me"),
  async logout() {
    try {
      await request<void>("/auth/logout", { method: "POST" });
    } finally {
      clearAccessToken();
    }
  },
};
