"use client";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Car, Filters, getCars, filtersToQuery, startLiveSearch } from "@/lib/api";
import { SearchForm } from "@/components/SearchForm";
import { ScrapePanel } from "@/components/ScrapePanel";
import { ResultsList } from "@/components/ResultsList";

export default function Page() {
  const router = useRouter();
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);

  // Main page: browse cached cars from the DB. Live search happens on /search.
  useEffect(() => {
    getCars().then((r) => setCars(r.items)).catch(() => setCars([])).finally(() => setLoading(false));
  }, []);

  // Kick off a live search, then hand its job id to /search so the results
  // page can show progress and (on return from a car) the saved cars.
  const go = (f: Filters) =>
    startLiveSearch(f)
      .then(({ job_id }) => router.push(`/search?${filtersToQuery(f)}&job=${job_id}`))
      .catch(() => router.push(`/search?${filtersToQuery(f)}`));

  return (
    <main className="max-w-5xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">CarSkyscanner 🚗</h1>
      <SearchForm onSearch={go} />
      <ScrapePanel />
      <ResultsList cars={cars} loading={loading} />
    </main>
  );
}
