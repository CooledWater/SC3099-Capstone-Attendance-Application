import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type AppRole } from "@/lib/api";
import { fetchUsers, updateAdminUser, type AdminUser } from "@/lib/admin";
import { useDebouncedValue } from "@/hooks/useDebouncedValue";
import { newPasswordError, PASSWORD_REQUIREMENTS } from "@/lib/password-policy";

const roles: AppRole[] = ["student", "ta", "instructor", "admin"];
const input =
  "min-w-0 max-w-full rounded-lg border border-border bg-secondary/40 px-3 py-2 text-sm";
const button = `${input} disabled:opacity-50`;

export function AdminUsers({ userId }: { userId: string }) {
  const qc = useQueryClient();
  const [search, setSearch] = useState("");
  const term = useDebouncedValue(search, 300);
  const [role, setRole] = useState("");
  const [active, setActive] = useState("all");
  const [page, setPage] = useState(0);
  const [creating, setCreating] = useState(false);
  const users = useQuery({
    queryKey: ["admin-users", userId, term, role, active, page],
    queryFn: ({ signal }) => {
      const params = new URLSearchParams({
        search: term.trim(),
        limit: "25",
        offset: String(page * 25),
      });
      if (role) params.set("role", role);
      if (active !== "all") params.set("is_active", active);
      return fetchUsers(params, signal);
    },
  });
  const change = useMutation({
    mutationFn: ({
      target,
      updates,
    }: {
      target: AdminUser;
      updates: { role?: AppRole; is_active?: boolean };
    }) => updateAdminUser(target.id, updates),
    onSuccess: async () => {
      await Promise.all([
        qc.invalidateQueries({ queryKey: ["admin-users"] }),
        qc.invalidateQueries({ queryKey: ["admin-staff"] }),
        qc.invalidateQueries({ queryKey: ["admin-course-tas"] }),
        qc.invalidateQueries({ queryKey: ["courses"] }),
      ]);
    },
  });
  return (
    <section className="space-y-4 rounded-2xl border border-border bg-card p-5">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="mr-auto text-lg font-semibold">Users</h2>
        <button
          className="rounded-lg bg-gradient-to-r from-primary to-accent px-3 py-2 text-sm font-medium text-primary-foreground transition hover:brightness-110"
          onClick={() => setCreating(!creating)}
        >
          Create user
        </button>
      </div>
      {creating && (
        <CreateUser
          onSaved={() => {
            setCreating(false);
            void qc.invalidateQueries({ queryKey: ["admin-users"] });
            void qc.invalidateQueries({ queryKey: ["admin-staff"] });
          }}
        />
      )}
      <div className="flex flex-wrap gap-3">
        <label className="grid min-w-0 gap-1 text-sm">
          Search users
          <input
            className={input}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            placeholder="Name or email"
          />
        </label>
        <label className="grid min-w-0 gap-1 text-sm">
          Role
          <select
            className={input}
            value={role}
            onChange={(e) => {
              setRole(e.target.value);
              setPage(0);
            }}
          >
            <option value="">All roles</option>
            {roles.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className="grid min-w-0 gap-1 text-sm">
          Account status
          <select
            className={input}
            value={active}
            onChange={(e) => {
              setActive(e.target.value);
              setPage(0);
            }}
          >
            <option value="all">All accounts</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </select>
        </label>
      </div>
      {users.isPending && <p role="status">Loading users…</p>}
      {users.isError && (
        <p role="alert">
          Could not load users.{" "}
          <button className={button} onClick={() => void users.refetch()}>
            Retry
          </button>
        </p>
      )}
      {change.isError && (
        <p role="alert" className="text-destructive">
          {change.error.message}
        </p>
      )}
      {change.isSuccess && <p role="status">User updated.</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead>
            <tr>
              <th className="p-3">User</th>
              <th className="p-3">Role</th>
              <th className="p-3">Status</th>
              <th className="p-3">Action</th>
            </tr>
          </thead>
          <tbody>
            {users.data?.items.map((user) => (
              <tr key={user.id} className="border-t border-border">
                <td className="p-3">
                  {user.full_name}
                  <span className="block text-muted-foreground">
                    {user.email}
                    {user.id === userId && " (you)"}
                  </span>
                </td>
                <td className="p-3">
                  <select
                    aria-label={`Role for ${user.email}`}
                    className={input}
                    value={user.role}
                    disabled={change.isPending || user.id === userId}
                    onChange={(e) => {
                      const next = e.target.value as AppRole;
                      if (
                        window.confirm(
                          `Change ${user.email} from ${user.role} to ${next}? Their access changes immediately.`,
                        )
                      )
                        change.mutate({ target: user, updates: { role: next } });
                    }}
                  >
                    {roles.map((item) => (
                      <option key={item}>{item}</option>
                    ))}
                  </select>
                </td>
                <td className="p-3">
                  <span
                    className={`rounded-full px-2 py-1 text-xs ${user.is_active ? "bg-accent/10 text-accent" : "bg-destructive/10 text-destructive"}`}
                  >
                    {user.is_active ? "Active" : "Inactive"}
                  </span>
                </td>
                <td className="p-3">
                  <button
                    className={user.is_active
                      ? "border-0 bg-transparent p-0 text-xs text-destructive underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-destructive disabled:opacity-50"
                      : button}
                    disabled={change.isPending || user.id === userId}
                    onClick={() => {
                      if (
                        window.confirm(
                          `${user.is_active ? "Deactivate" : "Activate"} ${user.email}?`,
                        )
                      )
                        change.mutate({ target: user, updates: { is_active: !user.is_active } });
                    }}
                  >
                    {user.is_active ? "Deactivate" : "Activate"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {users.isSuccess && !users.data.items.length && <p>No matching users.</p>}
      <p className="text-xs text-muted-foreground">
        Your own role and account status are protected here to keep this admin session usable.
      </p>
      <div className="flex items-center gap-3">
        <button
          className={button}
          disabled={page === 0 || users.isFetching}
          onClick={() => setPage(page - 1)}
        >
          Previous
        </button>
        <span>
          Page {page + 1} · {users.data?.total ?? 0} users
        </span>
        <button
          className={button}
          disabled={!users.data || (page + 1) * 25 >= users.data.total || users.isFetching}
          onClick={() => setPage(page + 1)}
        >
          Next
        </button>
      </div>
    </section>
  );
}

function CreateUser({ onSaved }: { onSaved: () => void }) {
  const [draft, setDraft] = useState({
    email: "",
    full_name: "",
    password: "",
    role: "student" as AppRole,
  });
  const passwordError = newPasswordError(draft.password);
  const create = useMutation({
    mutationFn: async () => {
      const result = await api.request<{ created: number; errors: { error?: string }[] }>(
        "/admin/users/bulk",
        {
          method: "POST",
          body: JSON.stringify({
            users: [{ ...draft, email: draft.email.trim(), full_name: draft.full_name.trim() }],
          }),
        },
      );
      if (result.created !== 1)
        throw new Error(result.errors[0]?.error ?? "Could not create user.");
    },
    onSuccess: onSaved,
  });
  return (
    <form
      className="grid gap-3 rounded-xl border border-border p-4 sm:grid-cols-2"
      onSubmit={(e) => {
        e.preventDefault();
        create.mutate();
      }}
    >
      <label className="grid min-w-0 gap-1">
        Name
        <input
          className={input}
          autoComplete="off"
          required
          value={draft.full_name}
          onChange={(e) => setDraft({ ...draft, full_name: e.target.value })}
        />
      </label>
      <label className="grid min-w-0 gap-1">
        Email
        <input
          className={input}
          type="email"
          autoComplete="off"
          required
          value={draft.email}
          onChange={(e) => setDraft({ ...draft, email: e.target.value })}
        />
      </label>
      <label className="grid min-w-0 gap-1">
        Password
        <input
          className={input}
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          maxLength={72}
          value={draft.password}
          onChange={(e) => setDraft({ ...draft, password: e.target.value })}
        />
        <span className="text-xs text-muted-foreground">{PASSWORD_REQUIREMENTS}</span>
      </label>
      <label className="grid min-w-0 gap-1">
        Role
        <select
          className={input}
          value={draft.role}
          onChange={(e) => setDraft({ ...draft, role: e.target.value as AppRole })}
        >
          {roles.map((item) => (
            <option key={item}>{item}</option>
          ))}
        </select>
      </label>
      {create.isError && (
        <p role="alert" className="text-destructive">
          {create.error.message}
        </p>
      )}
      <button
        className={button}
        disabled={create.isPending || !draft.full_name.trim() || Boolean(passwordError)}
      >
        Save user
      </button>
    </form>
  );
}
