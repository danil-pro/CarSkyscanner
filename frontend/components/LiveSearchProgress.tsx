"use client";
import type { LiveSearchJob } from "@/lib/api";

const LABELS: Record<string, string> = {
  ok: "✓", blocked: "⛔", error: "✗",
  "session-invalid": "🔒", "session-not-configured": "🔒",
  "no-results": "⚠", pending: "…",
};

export function LiveSearchProgress({ job }: { job: LiveSearchJob }) {
  return (
    <div className="bg-white rounded-lg shadow p-3 text-sm space-y-1">
      <div className="font-semibold">
        Живой поиск… {job.status === "running" ? "собираем данные" : job.status}
      </div>
      {Object.entries(job.per_source).map(([src, p]) => (
        <div key={src} className="flex justify-between text-gray-700">
          <span>{src.toUpperCase()} {LABELS[p.status] ?? ""}</span>
          <span className="text-gray-500">
            {p.status === "ok"
              ? p.saved != null && p.saved < p.found
                ? `сохранено ${p.saved}/${p.found}`
                : `найдено ${p.found}`
              : p.reason || p.status}
          </span>
        </div>
      ))}
    </div>
  );
}
