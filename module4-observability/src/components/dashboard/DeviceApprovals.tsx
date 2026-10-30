import { useState } from "react";
import { keepPreviousData, useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import type { Device } from "@/lib/devices";

type Row = Device & { user_email?: string | null; user_name?: string | null };
type Action = {
  id: string;
  method: "PATCH" | "DELETE";
  updates?: { device_name?: string; is_trusted?: boolean; is_active?: boolean };
};
const control =
  "rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm disabled:opacity-50";

export function DeviceApprovals({
  userId,
  initialActive = "all",
  initialTrusted = "all",
}: {
  userId: string;
  initialActive?: string;
  initialTrusted?: string;
}) {
  const [page, setPage] = useState(0);
  const [active, setActive] = useState(initialActive);
  const [trusted, setTrusted] = useState(initialTrusted);
  const [userEmail, setUserEmail] = useState("");
  const [editing, setEditing] = useState<Row | null>(null);
  const [name, setName] = useState("");
  const qc = useQueryClient();
  const debouncedUserEmail = useDebouncedValue(userEmail);
  const devices = useQuery({
    queryKey: ["admin-devices", userId, active, trusted, debouncedUserEmail, page],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({ limit: "25", offset: String(page * 25) });
      if (active !== "all") params.set("is_active", active);
      if (trusted !== "all") params.set("is_trusted", trusted);
      if (debouncedUserEmail.trim()) params.set("user_email", debouncedUserEmail.trim());
      return api.request<{ items: Row[]; total: number }>(`/devices/?${params}`, { signal });
    },
    placeholderData: keepPreviousData,
    retry: false,
    refetchInterval: 30000,
  });
  const update = useMutation({
    mutationFn: ({ id, method, updates }: Action) =>
      api.request(`/devices/${encodeURIComponent(id)}`, {
        method,
        ...(updates ? { body: JSON.stringify(updates) } : {}),
      }),
    onSuccess: async () => {
      setEditing(null);
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["admin-devices"] }),
        qc.invalidateQueries({ queryKey: ["my-devices"] }),
        qc.invalidateQueries({ queryKey: ["admin-device-approval-count", userId] }),
      ]);
    },
  });
  function confirm(device: Row, message: string, action: Omit<Action, "id">) {
    if (
      window.confirm(
        `${message}\n${device.user_email ?? "User"} · ${device.device_name || "Browser"}`,
      )
    )
      update.mutate({ id: device.id, ...action });
  }
  return (
    <section className="space-y-4 rounded-xl border border-border bg-card p-6">
      <h2 className="text-lg font-semibold">Device management</h2>
      <div className="flex flex-wrap gap-3">
        <label>
          Device status{" "}
          <select
            className={control}
            value={active}
            onChange={(e) => {
              setActive(e.target.value);
              setPage(0);
            }}
          >
            <option value="all">All</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </label>
        <label>
          Trust{" "}
          <select
            className={control}
            value={trusted}
            onChange={(e) => {
              setTrusted(e.target.value);
              setPage(0);
            }}
          >
            <option value="all">All</option>
            <option value="true">Approved</option>
            <option value="false">Untrusted</option>
          </select>
        </label>
        <input
          type="search"
          className={control}
          value={userEmail}
          placeholder="Search email"
          aria-label="Search devices by user email"
          onChange={(e) => {
            setUserEmail(e.target.value);
            setPage(0);
          }}
        />
      </div>
      {update.isError && (
        <p role="alert" className="text-destructive">
          {update.error.message}
        </p>
      )}
      {update.isSuccess && <p role="status">Device updated.</p>}
      {devices.isError && (
        <p role="alert">
          Devices could not be loaded.{" "}
          <button className={control} onClick={() => void devices.refetch()}>
            Retry
          </button>
        </p>
      )}
      {devices.isPending && <p role="status">Loading devices…</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th className="p-3">User</th>
              <th className="p-3">Device</th>
              <th className="p-3">Status</th>
              <th className="p-3">Check-ins</th>
              <th className="p-3">Actions</th>
            </tr>
          </thead>
          <tbody>
            {devices.data?.items.map((device) => (
              <tr className="border-t border-border" key={device.id}>
                <td className="p-3">
                  <span className="block font-medium">{device.user_name || "Unknown user"}</span>
                  <span className="block text-xs text-muted-foreground">{device.user_email}</span>
                </td>
                <td className="p-3">
                  {editing?.id === device.id ? (
                    <form
                      className="flex flex-wrap items-center gap-2"
                      onSubmit={(event) => {
                        event.preventDefault();
                        if (update.isPending || !name.trim()) return;
                        if (name.trim() === (device.device_name ?? "")) {
                          setEditing(null);
                          return;
                        }
                        update.mutate({
                          id: device.id,
                          method: "PATCH",
                          updates: { device_name: name.trim() },
                        });
                      }}
                    >
                      <input
                        aria-label="Device name"
                        className={control}
                        autoFocus
                        onFocus={(event) => event.currentTarget.select()}
                        required
                        maxLength={255}
                        disabled={update.isPending}
                        value={name}
                        onChange={(event) => setName(event.target.value)}
                        onKeyDown={(event) => {
                          if (event.key === "Escape" && !update.isPending) {
                            event.preventDefault();
                            setEditing(null);
                          }
                        }}
                      />
                      <button className={control} disabled={update.isPending || !name.trim()}>
                        Save
                      </button>
                      <button
                        type="button"
                        className={control}
                        disabled={update.isPending}
                        onClick={() => setEditing(null)}
                      >
                        Cancel
                      </button>
                    </form>
                  ) : (
                    <button
                      type="button"
                      className="rounded text-left hover:text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
                      title="Double-click to edit; press Enter or F2 when focused"
                      aria-label={`Edit device name: ${device.device_name || "Browser"}`}
                      disabled={update.isPending}
                      onDoubleClick={() => {
                        update.reset();
                        setEditing(device);
                        setName(device.device_name ?? "");
                      }}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === "F2") {
                          event.preventDefault();
                          update.reset();
                          setEditing(device);
                          setName(device.device_name ?? "");
                        }
                      }}
                    >
                      {device.device_name || "Browser"}
                    </button>
                  )}
                  <small className="block text-muted-foreground">
                    Approval reference:{" "}
                    {(device.browser_fingerprint ?? device.device_fingerprint).slice(0, 16)}
                  </small>
                </td>
                <td className="p-3">
                  <span
                    className={`inline-block whitespace-nowrap rounded-full px-2 py-1 text-xs ${
                      !device.is_active
                        ? "bg-secondary text-muted-foreground"
                        : device.is_trusted
                          ? "bg-accent/10 text-accent"
                          : "bg-orange-400/10 text-orange-400"
                    }`}
                  >
                    {!device.is_active ? "Inactive" : device.is_trusted ? "Approved" : "Untrusted"}
                  </span>
                  {device.shared_browser && (
                    <strong className="block text-destructive">
                      Shared browser · check-ins flagged
                    </strong>
                  )}
                </td>
                <td className="p-3">{device.total_checkins}</td>
                <td className="p-3">
                  <div className="flex flex-wrap gap-2">
                    <button
                      className={`${control} ${device.is_trusted ? "text-orange-400" : "text-accent"}`}
                      disabled={!device.is_active || update.isPending}
                      onClick={() =>
                        confirm(
                          device,
                          device.is_trusted
                            ? "Revoke trust for this device?"
                            : "Have you independently verified this user and device? Approve this device?",
                          { method: "PATCH", updates: { is_trusted: !device.is_trusted } },
                        )
                      }
                    >
                      {device.is_trusted ? "Revoke trust" : "Approve device"}
                    </button>
                    <button
                      className={control}
                      disabled={update.isPending}
                      onClick={() =>
                        confirm(
                          device,
                          device.is_active
                            ? "Deactivate this device? Its trust setting will be retained."
                            : "Reactivate this device with its existing trust setting?",
                          { method: "PATCH", updates: { is_active: !device.is_active } },
                        )
                      }
                    >
                      {device.is_active ? "Deactivate" : "Reactivate"}
                    </button>
                    <button
                      className={`${control} text-destructive`}
                      disabled={update.isPending}
                      onClick={() =>
                        confirm(
                          device,
                          "Remove this device from the registered device list and revoke its trust? Check-in history will be retained.",
                          { method: "DELETE" },
                        )
                      }
                    >
                      Remove
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {devices.isSuccess && !devices.data.items.length && <p>No matching devices.</p>}
      <div className="flex flex-wrap items-center gap-4">
        <button
          className={control}
          disabled={page === 0 || devices.isFetching}
          onClick={() => setPage((value) => value - 1)}
        >
          Previous
        </button>
        <span>
          Page {page + 1} · {devices.data?.total ?? 0} devices
        </span>
        <button
          className={control}
          disabled={!devices.data || devices.isFetching || (page + 1) * 25 >= devices.data.total}
          onClick={() => setPage((value) => value + 1)}
        >
          Next
        </button>
      </div>
    </section>
  );
}
