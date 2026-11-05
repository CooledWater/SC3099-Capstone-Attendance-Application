import { api } from "@/lib/api";

export type DeviceApprovalStatus = "approved" | "pending" | "rejected" | "inactive" | "removed";

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
  approval_status?: DeviceApprovalStatus;
  first_seen_at: string | null;
  last_seen_at: string | null;
  total_checkins: number;
};

export function deviceApprovalStatus(device: Device): DeviceApprovalStatus {
  if (device.is_removed) return "removed";
  return (
    device.approval_status ??
    (!device.is_active ? "inactive" : device.is_trusted ? "approved" : "pending")
  );
}

export const deviceApprovalLabels: Record<DeviceApprovalStatus, string> = {
  approved: "Approved",
  pending: "Pending approval",
  rejected: "Rejected (device limit)",
  inactive: "Inactive",
  removed: "Removed",
};

export function deviceAccessMessage(device: Device): string {
  const status = deviceApprovalStatus(device);
  if (status === "rejected")
    return "Login allowed. Check-in blocked until an admin approves this extra device.";
  if (status === "pending")
    return "Login and check-in allowed. Check-ins are flagged until this device is approved.";
  if (status === "inactive" || status === "removed") return "Check-in blocked on this device.";
  return "";
}

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
        if (record.result?.fingerprint) resolve(record.result.fingerprint);
        else reject(new DeviceIdentificationUnsupportedError());
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
