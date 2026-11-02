import { api } from "@/lib/api";

export type Device = {
  id: string;
  device_fingerprint: string;
  browser_fingerprint?: string | null;
  shared_browser?: boolean;
  browser_identity_verified?: boolean;
  device_name: string | null;
  platform: "ios" | "android" | "web" | "desktop" | null;
  browser?: string | null;
  is_trusted: boolean;
  trust_score: string | null;
  is_active: boolean;
  is_removed?: boolean;
  first_seen_at: string | null;
  last_seen_at: string | null;
  total_checkins: number;
};

export const fetchMyDevices = async (signal?: AbortSignal) => {
  const devices = await api.request<Device[]>("/devices/my-devices", { signal: signal ?? null });
  return devices.filter((device) => !device.is_removed);
};

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

// Read the key already created by the attendance PWA on this origin.
// A separate dashboard origin cannot access the PWA's IndexedDB.
export async function createDeviceFingerprint() {
  if (!globalThis.indexedDB) throw new DeviceIdentificationUnsupportedError();
  return new Promise<string>((resolve, reject) => {
    const request = indexedDB.open("saiv-device-keys", 1);
    request.onupgradeneeded = () => request.result.createObjectStore("identities");
    request.onerror = () => reject(new DeviceIdentificationUnsupportedError());
    request.onsuccess = () => {
      const db = request.result;
      const record = db
        .transaction("identities")
        .objectStore("identities")
        .get("browser-installation-v1");
      record.onsuccess = () => {
        db.close();
        record.result?.fingerprint
          ? resolve(record.result.fingerprint)
          : reject(new DeviceIdentificationUnsupportedError());
      };
      record.onerror = () => {
        db.close();
        reject(new DeviceIdentificationUnsupportedError());
      };
    };
  });
}

export function isDeviceIdentificationUnsupported(error: unknown) {
  return error instanceof DeviceIdentificationUnsupportedError;
}
