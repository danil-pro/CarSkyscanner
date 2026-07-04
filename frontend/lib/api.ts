const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Car {
  id: string; title: string | null; brand: string; model: string;
  year: number | null; price: number | null; currency: string;
  mileage: number | null; fuel_type: string | null; transmission: string | null;
  location: string | null; source: string; url: string; image_url: string | null;
  created_at: string;
}

export interface Filters {
  brand?: string; model?: string; year_min?: number; year_max?: number;
  price_min?: number; price_max?: number; mileage_max?: number;
  fuel_type?: string; transmission?: string;
}

export interface SearchResponse { items: Car[]; total: number; limit: number; offset: number; }
export interface SourceResult { found: number; saved: number; blocked: number; errors: number; }
export interface ScrapeStatus {
  status: string; job_id: string | null; started_at: string | null;
  finished_at: string | null; total_saved: number; per_source: Record<string, SourceResult>;
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...init });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

export const getCars = (limit = 100, offset = 0) =>
  req<SearchResponse>(`/cars?limit=${limit}&offset=${offset}`);
export interface CarDetails { description: string | null; images: string[]; specs: Record<string, string>; status: string; fetched_at: string | null; }
export const getCar = (id: string) => req<Car>(`/cars/${id}`);
export const getCarDetails = (id: string) => req<CarDetails>(`/cars/${id}/details`);
export const searchCars = (f: Filters) =>
  req<SearchResponse>("/search", { method: "POST", body: JSON.stringify(f) });

// Filters <-> URL query, so the /search page is URL-driven and survives
// navigation/refresh (search results no longer vanish when you open a car).
export function filtersToQuery(f: Filters): string {
  const p = new URLSearchParams();
  for (const [k, v] of Object.entries(f))
    if (v !== undefined && v !== null && v !== "") p.set(k, String(v));
  return p.toString();
}
export function queryToFilters(sp: URLSearchParams): Filters {
  const s = (k: string) => sp.get(k) || undefined;
  const n = (k: string) => (sp.get(k) ? Number(sp.get(k)) : undefined);
  return {
    brand: s("brand"), model: s("model"), year_min: n("year_min"), year_max: n("year_max"),
    price_min: n("price_min"), price_max: n("price_max"), mileage_max: n("mileage_max"),
    fuel_type: s("fuel_type"), transmission: s("transmission"),
  };
}
export const runScrape = () => req<{ job_id: string; status: string }>("/scrape/run", { method: "POST" });
export const getScrapeStatus = () => req<ScrapeStatus>("/scrape/status");

export interface ProviderProgress { status: string; found: number; reason: string | null; saved?: number | null; }
export interface LiveSearchJob {
  job_id: string; status: string;
  per_source: Record<string, ProviderProgress>;
  results: Car[] | null; error?: string | null;
}

export const startLiveSearch = (f: Filters) =>
  req<{ job_id: string; status: string }>("/search/live", { method: "POST", body: JSON.stringify(f) });
export const getLiveSearch = (jobId: string) => req<LiveSearchJob>(`/search/live/${jobId}`);
