"use client";
import { useEffect, useState } from "react";
import { Car, Filters, getCars, searchCars } from "@/lib/api";
import { SearchForm } from "@/components/SearchForm";
import { ResultsList } from "@/components/ResultsList";
import { ScrapePanel } from "@/components/ScrapePanel";

export default function Page() {
  const [cars, setCars] = useState<Car[]>([]);
  const [loading, setLoading] = useState(true);

  const load = (f?: Filters) => {
    setLoading(true);
    const hasFilters = f && Object.values(f).some(Boolean);
    const p = hasFilters ? searchCars(f!) : getCars();
    p.then((r) => setCars(r.items))
      .catch(() => setCars([]))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, []);

  // Periodically refresh results so newly-scraped cars appear.
  useEffect(() => {
    const t = setInterval(
      () =>
        getCars()
          .then((r) => setCars(r.items))
          .catch(() => {}),
      10000,
    );
    return () => clearInterval(t);
  }, []);

  return (
    <main className="max-w-5xl mx-auto p-4 space-y-4">
      <h1 className="text-2xl font-bold">CarSkyscanner 🚗</h1>
      <SearchForm onSearch={(f) => load(f)} />
      <ScrapePanel />
      <ResultsList cars={cars} loading={loading} />
    </main>
  );
}
