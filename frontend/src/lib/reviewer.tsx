"use client";
import { createContext, useContext, useEffect, useState } from "react";

const KEY = "chainsleuth.reviewer";
const Ctx = createContext<[string, (v: string) => void]>(["", () => {}]);

export function ReviewerProvider({ children }: { children: React.ReactNode }) {
  const [name, setName] = useState("");
  useEffect(() => setName(localStorage.getItem(KEY) || "auditor.demo"), []);
  const update = (v: string) => {
    setName(v);
    localStorage.setItem(KEY, v);
  };
  return <Ctx.Provider value={[name, update]}>{children}</Ctx.Provider>;
}

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
