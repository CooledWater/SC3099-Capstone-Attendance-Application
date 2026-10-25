import { api } from "@/lib/api";

export type Device = {
  id: string;
  device_fingerprint: string;
  device_name: string | null;
  platform: "ios" | "android" | "web" | "desktop" | null;
  browser?: string | null;
  is_trusted: boolean;
  trust_score: string | null;
  is_active: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  total_checkins: number;
};

export const fetchMyDevices = (signal?: AbortSignal) =>
  api.request<Device[]>("/devices/my-devices", { signal: signal ?? null });

export const renameDevice = (deviceId: string, deviceName: string) =>
  api.request<Device>(`/devices/${encodeURIComponent(deviceId)}`, {
    method: "PATCH",
    body: JSON.stringify({ device_name: deviceName.trim() }),
  });

export const removeDevice = (deviceId: string) =>
  api.request<void>(`/devices/${encodeURIComponent(deviceId)}`, { method: "DELETE" });

class DeviceIdentificationUnsupportedError extends Error {
  constructor() {
    super("This browser does not support reliable device identification.");
    this.name = "DeviceIdentificationUnsupportedError";
  }
}

// Keep this in sync with module1-frontend/lib/device.ts so a browser registered
// by the check-in flow can be matched without exposing its fingerprint in UI.
export async function createDeviceFingerprint() {
  if (!globalThis.crypto?.subtle || typeof globalThis.navigator === "undefined") {
    throw new DeviceIdentificationUnsupportedError();
  }

  const signals = [
    navigator.userAgent,
    navigator.language,
    navigator.platform,
    screen.width,
    screen.height,
  ].join("|");
  const digest = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(signals));
  return btoa(String.fromCharCode(...Array.from(new Uint8Array(digest))));
}

export function isDeviceIdentificationUnsupported(error: unknown) {
  return error instanceof DeviceIdentificationUnsupportedError;
}
