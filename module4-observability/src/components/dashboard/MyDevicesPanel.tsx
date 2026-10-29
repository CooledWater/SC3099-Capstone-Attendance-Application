import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Globe2, Laptop, Monitor, Pencil, Smartphone, Trash2 } from "lucide-react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import {
  createDeviceFingerprint,
  fetchMyDevices,
  isDeviceIdentificationUnsupported,
  removeDevice,
  renameDevice,
  type Device,
} from "@/lib/devices";
import { formatSingaporeDateTime } from "@/lib/time";

const input =
  "mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground outline-none focus-visible:ring-2 focus-visible:ring-primary";

function dateLabel(value: string | null) {
  if (!value) return "—";
  const formatted = formatSingaporeDateTime(value);
  return formatted === "Invalid time" ? "—" : formatted;
}

function label(value: string | null | undefined) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : "—";
}

function PlatformIcon({ platform }: { platform: Device["platform"] }) {
  const Icon = platform === "ios" || platform === "android"
    ? Smartphone
    : platform === "desktop"
      ? Monitor
      : platform === "web"
        ? Globe2
        : Laptop;
  return <Icon aria-hidden="true" className="size-4" />;
}

function DeviceSkeleton() {
  return (
    <div className="animate-pulse rounded-2xl border border-border bg-glass p-5">
      <div className="h-5 w-2/5 rounded bg-secondary" />
      <div className="mt-3 h-4 w-1/4 rounded bg-secondary" />
      <div className="mt-8 grid grid-cols-2 gap-5">
        <div className="h-10 rounded bg-secondary" />
        <div className="h-10 rounded bg-secondary" />
        <div className="h-10 rounded bg-secondary" />
        <div className="h-10 rounded bg-secondary" />
      </div>
    </div>
  );
}

export function MyDevicesPanel() {
  const queryClient = useQueryClient();
  const devices = useQuery({
    queryKey: ["my-devices"],
    queryFn: ({ signal }) => fetchMyDevices(signal),
  });
  const fingerprint = useQuery({
    queryKey: ["current-device-fingerprint"],
    queryFn: createDeviceFingerprint,
    retry: false,
    staleTime: Infinity,
  });
  const [renameTarget, setRenameTarget] = useState<Device | null>(null);
  const [removeTarget, setRemoveTarget] = useState<Device | null>(null);
  const [name, setName] = useState("");
  const [renameError, setRenameError] = useState("");

  const currentDevice = useMemo(
    () => devices.data?.find((device) => (device.browser_fingerprint ?? device.device_fingerprint) === fingerprint.data),
    [devices.data, fingerprint.data],
  );
  const orderedDevices = useMemo(() => {
    const rows = [...(devices.data ?? [])];
    return rows.sort((a, b) => {
      if (a.id === currentDevice?.id) return -1;
      if (b.id === currentDevice?.id) return 1;
      return Date.parse(b.last_seen_at ?? "") - Date.parse(a.last_seen_at ?? "");
    });
  }, [currentDevice?.id, devices.data]);

  const rename = useMutation({
    mutationFn: ({ device, value }: { device: Device; value: string }) =>
      renameDevice(device.id, value),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["my-devices"] });
      setRenameTarget(null);
      toast.success("Device renamed.");
    },
    onError: (error) => setRenameError(error instanceof Error ? error.message : "Could not rename device."),
  });
  const remove = useMutation({
    mutationFn: (device: Device) => removeDevice(device.id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["my-devices"] });
      setRemoveTarget(null);
      toast.success("Device removed.");
    },
    onError: (error) => toast.error(error instanceof Error ? error.message : "Could not remove device."),
  });

  const retryCurrentDevice = () => {
    void Promise.all([devices.refetch(), fingerprint.refetch()]);
  };

  return (
    <section aria-labelledby="my-devices-heading" className="space-y-6">
      <div>
        <h2 id="my-devices-heading" className="font-display text-2xl font-semibold text-card-foreground">
          My devices
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">Manage the devices linked to your check-ins.</p>
      </div>

      {!isDeviceIdentificationUnsupported(fingerprint.error) && (
        <section className="rounded-xl border border-emerald-400/15 bg-emerald-400/[0.04] p-4 sm:p-5" aria-live="polite">
          {fingerprint.isPending || devices.isPending ? (
            <p role="status" className="text-sm text-muted-foreground">Checking device registration…</p>
          ) : fingerprint.isError || devices.isError ? (
            <div role="alert" className="flex flex-wrap items-center justify-between gap-3 text-sm text-warning">
              <span>Unable to check device registration</span>
              <Button type="button" variant="outline" size="sm" onClick={retryCurrentDevice}>Retry</Button>
            </div>
          ) : currentDevice ? (
            <div className="flex flex-wrap items-center gap-4">
              <div className="grid size-12 place-items-center rounded-xl bg-primary/20 text-primary">
                <PlatformIcon platform={currentDevice.platform} />
              </div>
              <div className="min-w-0 flex-1">
                <p className="font-display text-base font-semibold">
                  {currentDevice.device_name ?? "Unnamed device"}
                </p>
                <p className="mt-1 text-sm text-muted-foreground">
                  You’re using a registered device · {label(currentDevice.platform)}
                </p>
              </div>
              <span className={`rounded-full px-3 py-1 text-xs ${currentDevice.is_active ? "bg-accent/15 text-accent" : "bg-secondary text-muted-foreground"}`}>
                {currentDevice.is_active ? "Active" : "Inactive"}
              </span>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">This browser is not recognised as a registered device.</p>
          )}
        </section>
      )}

      <section aria-labelledby="registered-devices-heading">
        <div className="flex items-center justify-between gap-3">
          <h3 id="registered-devices-heading" className="font-display text-lg font-semibold">Registered devices</h3>
          {!devices.isPending && !devices.isError && <span className="text-sm text-muted-foreground">{devices.data?.length ?? 0} devices</span>}
        </div>

        {devices.isPending ? (
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2"><DeviceSkeleton /><DeviceSkeleton /></div>
        ) : devices.isError ? (
          <div role="alert" className="mt-4 rounded-xl border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
            Unable to load registered devices.
            <Button type="button" variant="link" size="sm" className="ml-2 text-warning" onClick={() => void devices.refetch()}>Retry</Button>
          </div>
        ) : !orderedDevices.length ? (
          <p className="mt-4 rounded-xl border border-border bg-glass p-5 text-sm text-muted-foreground">No devices registered yet.</p>
        ) : (
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {orderedDevices.map((device) => {
              const isCurrent = device.id === currentDevice?.id;
              return (
                <article key={device.id} className={`rounded-2xl border bg-glass p-5 ${isCurrent ? "border-primary/70" : "border-border"}`}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h4 className="truncate font-display text-base font-semibold">{device.device_name ?? "Unnamed device"}</h4>
                      <p className="mt-1 flex items-center gap-2 text-sm text-muted-foreground">
                        <PlatformIcon platform={device.platform} /> {label(device.platform)}
                        {isCurrent && <span>· This device</span>}
                      </p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2.5 py-1 text-xs ${device.is_active ? "bg-accent/15 text-accent" : "bg-secondary text-muted-foreground"}`}>
                      {device.is_active ? "Active" : "Inactive"}
                    </span>
                  </div>
                  <dl className="mt-6 grid grid-cols-2 gap-x-5 gap-y-4 text-sm">
                    <div><dt className="text-xs text-muted-foreground">Trust status</dt><dd className="mt-1">{device.is_trusted ? "Trusted" : "Not yet trusted"}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Trust score</dt><dd className="mt-1">{label(device.trust_score)}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Last seen</dt><dd className="mt-1">{dateLabel(device.last_seen_at)}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Total check-ins</dt><dd className="mt-1">{device.total_checkins ?? "—"}</dd></div>
                    <div><dt className="text-xs text-muted-foreground">Registered</dt><dd className="mt-1">{dateLabel(device.first_seen_at)}</dd></div>
                  </dl>
                  <div className="mt-6 flex items-center justify-between border-t border-border pt-4">
                    <Button type="button" variant="link" size="sm" className="px-0" onClick={() => { setRenameTarget(device); setName(device.device_name ?? ""); setRenameError(""); }}>
                      <Pencil /> Rename
                    </Button>
                    <Button type="button" variant="link" size="sm" className="px-0 text-destructive" onClick={() => setRemoveTarget(device)}>
                      <Trash2 /> Remove device
                    </Button>
                  </div>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <Dialog open={renameTarget !== null} onOpenChange={(open) => { if (!open && !rename.isPending) setRenameTarget(null); }}>
        <DialogContent className="border-border bg-card text-card-foreground">
          <DialogHeader>
            <DialogTitle className="font-display">Rename device</DialogTitle>
            <DialogDescription>Choose a name that helps you recognise this device.</DialogDescription>
          </DialogHeader>
          <form onSubmit={(event) => { event.preventDefault(); const value = name.trim(); if (!renameTarget || !value) { setRenameError("Enter a device name."); return; } rename.mutate({ device: renameTarget, value }); }}>
            <label className="block text-sm text-muted-foreground">
              Device name
              <input autoFocus className={input} value={name} maxLength={255} disabled={rename.isPending} onChange={(event) => { setName(event.target.value); setRenameError(""); }} />
            </label>
            {renameError && <p role="alert" className="mt-2 text-sm text-destructive">{renameError}</p>}
            <DialogFooter className="mt-6">
              <Button type="button" variant="outline" disabled={rename.isPending} onClick={() => setRenameTarget(null)}>Cancel</Button>
              <Button type="submit" disabled={rename.isPending || !name.trim()}>{rename.isPending ? "Saving…" : "Save changes"}</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      <AlertDialog open={removeTarget !== null} onOpenChange={(open) => { if (!open && !remove.isPending) setRemoveTarget(null); }}>
        <AlertDialogContent className="border-border bg-card text-card-foreground">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove device?</AlertDialogTitle>
            <AlertDialogDescription>
              This will remove <strong>{removeTarget?.device_name ?? "this device"}</strong> from active use. Check-in on it will be blocked until you explicitly enable it in the attendance app’s Profile → My devices. Admin approval will then be required again.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={remove.isPending}>Cancel</AlertDialogCancel>
            <AlertDialogAction className="bg-destructive text-destructive-foreground hover:bg-destructive/90" disabled={remove.isPending} onClick={() => { if (removeTarget) remove.mutate(removeTarget); }}>
              {remove.isPending ? "Removing…" : "Remove device"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
