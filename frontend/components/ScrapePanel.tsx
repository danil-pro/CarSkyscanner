"use client";
import { useEffect, useRef, useState } from "react";
import { runScrape, getScrapeStatus, ScrapeStatus } from "@/lib/api";

export function ScrapePanel() {
  const [status, setStatus] = useState<ScrapeStatus | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const poll = () => getScrapeStatus().then(setStatus).catch(() => {});

  // Stop the poller once a terminal status is observed.
  const stopIfDone = (s: ScrapeStatus | null) => {
    if (s && (s.status === "done" || s.status === "error") && timer.current) {
      clearInterval(timer.current);
      timer.current = null;
    }
  };

  useEffect(() => {
    poll();
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, []);

  const start = async () => {
    try {
      await runScrape();
    } catch (e: unknown) {
      // 409 = a scrape is already running; ignore, keep polling.
      if (!String(e).includes("409")) alert(e);
    }
    if (timer.current) clearInterval(timer.current);
    timer.current = setInterval(async () => {
      const s = await getScrapeStatus()
        .then((r) => {
          setStatus(r);
          return r;
        })
        .catch(() => null);
      stopIfDone(s);
    }, 2000);
  };

  return (
    <div className="bg-white rounded-lg shadow p-4">
      <div className="flex items-center gap-3">
        <button
          onClick={start}
          className="bg-green-600 text-white rounded px-3 py-1 hover:bg-green-700"
        >
          Запустить скрейп
        </button>
        <span className="text-sm">
          Статус: <b>{status?.status ?? "—"}</b>
        </span>
      </div>
      {status && (
        <table className="mt-3 text-sm w-full">
          <thead>
            <tr>
              <th align="left">Источник</th>
              <th>Найдено</th>
              <th>Сохранено</th>
              <th>Блок</th>
              <th>Ошибки</th>
            </tr>
          </thead>
          <tbody>
            {Object.entries(status.per_source).map(([k, v]) => (
              <tr key={k}>
                <td>{k}</td>
                <td align="center">{v.found}</td>
                <td align="center">{v.saved}</td>
                <td align="center">{v.blocked}</td>
                <td align="center">{v.errors}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
