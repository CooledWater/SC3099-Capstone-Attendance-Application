import { useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { Device } from '@/lib/devices';

type Row = Device & { user_email?: string };
export function DeviceApprovals() {
  const [page, setPage] = useState(0);
  const [error, setError] = useState('');
  const queryClient = useQueryClient();
  const devices = useQuery({ queryKey: ['admin-devices', page], queryFn: () => api.request<{ items: Row[]; total: number }>(`/devices/?limit=25&offset=${page * 25}`), refetchInterval: 30000 });
  const update = useMutation({
    mutationFn: ({ id, trusted }: { id: string; trusted: boolean }) => api.request(`/devices/${encodeURIComponent(id)}`, { method: 'PATCH', body: JSON.stringify({ is_trusted: trusted }) }),
    onSuccess: () => { setError(''); void queryClient.invalidateQueries({ queryKey: ['admin-devices'] }); },
    onError: cause => setError(cause instanceof Error ? cause.message : 'Approval failed'),
  });
  return <section className="rounded-xl border border-border bg-card p-6">
    <h2 className="text-lg font-semibold">Device approvals</h2>
    <p className="my-3 text-sm text-muted-foreground">Verify the student's identity and device through an independent channel before approving. A device name or successful login is not ownership evidence. Pending devices may check in, but their attendance is flagged. Approval affects future check-ins only. A browser verified on multiple student accounts stays flagged even after approval. Each account may have at most two active registrations, including pending devices.</p>
    {(error || devices.isError) && <p role="alert">{error || 'Devices could not be loaded.'}</p>}
    {devices.isLoading && <p>Loading devices…</p>}
    <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead><tr><th className="p-3">Student</th><th className="p-3">Device</th><th className="p-3">Status</th><th className="p-3">Check-ins</th><th className="p-3">Action</th></tr></thead><tbody>
      {devices.data?.items.map(device => <tr className="border-t border-border" key={device.id}><td className="p-3">{device.user_email}</td><td className="p-3">{device.device_name || 'Browser'}<small className="block text-muted-foreground">Approval reference: {(device.browser_fingerprint ?? device.device_fingerprint).slice(0, 16)}</small></td><td className="p-3">{!device.is_active ? 'Disabled' : device.is_trusted ? 'Approved' : 'Pending approval'}{device.shared_browser && <strong className="block text-destructive">Shared browser · check-ins flagged</strong>}</td><td className="p-3">{device.total_checkins}</td><td className="p-3"><button className="rounded border border-border px-3 py-2 disabled:opacity-50" disabled={!device.is_active || update.isPending} onClick={() => { if (window.confirm(device.is_trusted ? 'Revoke trust for this device?' : 'Have you independently verified this student and device? Approve this device?')) update.mutate({ id: device.id, trusted: !device.is_trusted }); }}>{device.is_trusted ? 'Revoke trust' : 'Approve device'}</button></td></tr>)}
    </tbody></table></div>
    <div className="mt-4 flex items-center gap-4"><button disabled={page === 0} onClick={() => setPage(value => value - 1)}>Previous</button><span>Page {page + 1}</span><button disabled={(page + 1) * 25 >= (devices.data?.total ?? 0)} onClick={() => setPage(value => value + 1)}>Next</button><button onClick={() => void devices.refetch()}>Refresh</button></div>
  </section>;
}
