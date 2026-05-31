"use client";

import { useEffect, useState } from "react";
import { apiGet } from "@/lib/api";

type Status = "checking" | "ok" | "error";

// Sprint 0 smoke check: confirms the frontend can reach the backend health
// endpoint through the proxy.
export function ApiHealth() {
  const [status, setStatus] = useState<Status>("checking");

  useEffect(() => {
    apiGet<{ status: string }>("/health")
      .then((r) => setStatus(r.status === "ok" ? "ok" : "error"))
      .catch(() => setStatus("error"));
  }, []);

  const label =
    status === "checking"
      ? "Checking API…"
      : status === "ok"
        ? "API reachable"
        : "API unreachable";
  const dot =
    status === "ok"
      ? "bg-green-500"
      : status === "error"
        ? "bg-red-500"
        : "bg-amber-400";

  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 text-sm">
      <span className={`h-2.5 w-2.5 rounded-full ${dot}`} />
      {label}
    </div>
  );
}
