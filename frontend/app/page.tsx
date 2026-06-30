"use client";
import { useEffect, useRef, useState } from "react";
import { Car, Filters, getCars, startLiveSearch, getLiveSearch, LiveSearchJob } from "@/lib/api";
import { SearchForm } from "@/components/SearchForm";
import { ResultsList } from "@/components/ResultsList";
import { ScrapePanel } from "@/components/ScrapePanel";
import { LiveSearchProgress } from "@/components/LiveSearchProgress";

export default function Page() {
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);
  const [job, setJob] = useState<LiveSearchJob | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
  };

  const runLive = (f: Filters) => {
    setLoading(true);
    setJob(null);
    setCars([]);
    stopPolling();
    startLiveSearch(f)
      .then(({ job_id }) => {
        timer.current = setInterval(() => {
          getLiveSearch(job_id)
            .then((j) => {
              setJob(j);
              if (j.status !== "running") {
                stopPolling();
                setCars(j.results ?? []);
                setLoading(false);
              }
            })
            .catch(() => { stopPolling(); setLoading(false); });
        }, 2000);
      })
      .catch(() => setLoading(false));
  };

  useEffect(() => {
    // initial load from DB (cached); live search drives updates thereafter
    getCars().then((r) => setCars(r.items)).catch(() => setCars([])).finally(() => setLoading(false));
    return () => stopPolling();
  }, []);

  return (
    <main className="max-w-5xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">CarSkyscanner 🚗</h1>
      <SearchForm onSearch={(f) => runLive(f)} />
      <ScrapePanel />
      {job && <LiveSearchProgress job={job} />}
      <ResultsList cars={cars} loading={loading} />
    </main>
  );
}
