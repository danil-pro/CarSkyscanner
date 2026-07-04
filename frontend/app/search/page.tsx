"use client";
import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import {
  Car, Filters, LiveSearchJob,
  searchCars, startLiveSearch, getLiveSearch,
  filtersToQuery, queryToFilters,
} from "@/lib/api";
import { SearchForm } from "@/components/SearchForm";
import { ResultsList } from "@/components/ResultsList";
import { LiveSearchProgress } from "@/components/LiveSearchProgress";

function SearchInner() {
  const sp = useSearchParams();
  const router = useRouter();
  const filters = queryToFilters(sp);
  const jobId = sp.get("job");
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);
  const [job, setJob] = useState<LiveSearchJob | null>(null);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = () => {
    if (timer.current) { clearInterval(timer.current); timer.current = null; }
  };
  const refresh = () => searchCars(filters).then((r) => setCars(r.items)).catch(() => {});

  // The results list is URL-driven: derived from the DB by the current filters,
  // so it survives navigation/refresh (no more vanishing on back).
  useEffect(() => {
    setLoading(true);
    refresh().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filtersToQuery(filters)]);

  // Live-search progress is driven by the job id in the URL — arriving with a
  // job id shows progress; returning from a car just re-shows the saved cars.
  useEffect(() => {
    if (!jobId) { setJob(null); stopPolling(); return; }
    stopPolling();
    timer.current = setInterval(() => {
      getLiveSearch(jobId)
        .then((j) => {
          setJob(j);
          refresh();
          if (j.status !== "running") stopPolling();
        })
        .catch(() => stopPolling());
    }, 2000);
    return () => stopPolling();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const startNew = (f: Filters) =>
    startLiveSearch(f)
      .then(({ job_id }) => router.push(`/search?${filtersToQuery(f)}&job=${job_id}`))
      .catch(() => router.push(`/search?${filtersToQuery(f)}`));

  return (
    <main className="max-w-5xl mx-auto p-4 space-y-4">
      <a href="/" className="text-sm text-blue-600 hover:underline">← Главная</a>
      <SearchForm defaults={filters} onSearch={startNew} />
      <div className="flex items-center gap-3">
        <button
          onClick={() => startNew(filters)}
          className="bg-green-600 text-white rounded px-3 py-1 hover:bg-green-700"
        >
          🔄 Живой поиск
        </button>
        <span className="text-sm text-gray-500">
          {job?.status === "running" ? "собираем данные…" : (job?.status ?? "")}
        </span>
      </div>
      {job && <LiveSearchProgress job={job} />}
      <ResultsList cars={cars} loading={loading} />
    </main>
  );
}

export default function SearchPage() {
  return (
    <Suspense fallback={<p className="max-w-5xl mx-auto p-4 text-gray-500">Загрузка…</p>}>
      <SearchInner />
    </Suspense>
  );
}
