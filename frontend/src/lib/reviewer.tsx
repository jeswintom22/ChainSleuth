"use client";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { api, clearToken, getToken, setToken } from "@/lib/api";

export type SessionUser = { name: string; role: string };
type Session = { user: SessionUser | null; error: string | null; signIn: (token: string) => Promise<void>; signOut: () => void };
const Ctx = createContext<Session>({ user: null, error: null, signIn: async () => {}, signOut: () => {} });

export function ReviewerProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [error, setError] = useState<string | null>(null);
  const refresh = useCallback(async () => {
    if (!getToken()) { setUser(null); return; }
    try { setUser(await api.me()); setError(null); }
    catch (e) { clearToken(); setUser(null); setError(String(e)); }
  }, []);
  useEffect(() => { refresh(); }, [refresh]);
  const signIn = async (token: string) => { setToken(token.trim()); await refresh(); };
  const signOut = () => { clearToken(); setUser(null); };
  return <Ctx.Provider value={{ user, error, signIn, signOut }}>{children}</Ctx.Provider>;
}

/** The signed-in reviewer. Identity is derived server-side from the API token. */
export const useReviewer = () => useContext(Ctx);

export const SEVERITY_COLOR: Record<string, "default" | "info" | "warning" | "error" | "success"> = {
  low: "info",
  medium: "warning",
  high: "error",
  critical: "error",
};

export const STATUS_COLOR: Record<string, "default" | "info" | "warning" | "error" | "success"> = {
  open: "default",
  needs_review: "warning",
  confirmed: "error",
  dismissed: "success",
  in_review: "warning",
  closed: "success",
};
