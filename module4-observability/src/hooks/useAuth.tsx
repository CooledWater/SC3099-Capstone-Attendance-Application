import { useEffect, useState } from "react";
import { api, clearAccessToken, type CurrentUser } from "@/lib/api";

export function useAuth() {
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    api
      .restoreSession()
      .then((session) => {
        if (!cancelled) setUser(session);
      })
      .catch(() => {
        if (!cancelled) {
          clearAccessToken();
          setUser(null);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { session: user, user, loading };
}
