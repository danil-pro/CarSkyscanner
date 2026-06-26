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
export const searchCars = (f: Filters) =>
  req<SearchResponse>("/search", { method: "POST", body: JSON.stringify(f) });
export const runScrape = () => req<{ job_id: string; status: string }>("/scrape/run", { method: "POST" });
export const getScrapeStatus = () => req<ScrapeStatus>("/scrape/status");
