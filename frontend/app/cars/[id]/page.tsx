import { notFound } from "next/navigation";
import { Car } from "@/lib/api";
import { SourceBadge } from "@/components/SourceBadge";
import { DetailsPanel } from "@/components/DetailsPanel";
import { BackLink } from "@/components/BackLink";
import { placeholderFor } from "@/lib/placeholder";

// Server Components execute inside the frontend container, where `localhost:8000`
// is the frontend container itself, NOT the backend (a separate container). So
// server-side fetches must use the internal container-to-container URL; the
// browser keeps using NEXT_PUBLIC_API_URL (host port -> backend). Locally
// (next dev, no Docker) both resolve to the same default.
const API =
  process.env.API_URL_INTERNAL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

async function fetchCar(id: string): Promise<Car | null> {
  try {
    const r = await fetch(`${API}/cars/${id}`, { cache: "no-store" });
    if (!r.ok) return null;
    return r.json();
  } catch {
    // Backend unreachable — degrade to 404 instead of an unhandled
    // "server-side exception". The internal-URL fix above is the real cure;
    // this just keeps a transient outage from crashing the whole page.
    return null;
  }
}

export default async function CarProfile({ params }: { params: { id: string } }) {
  const car = await fetchCar(params.id);
  if (!car) notFound();

  return (
    <main className="max-w-3xl mx-auto p-4 space-y-4">
      <BackLink label="← Назад к поиску" />
      <div className="bg-white rounded-lg shadow p-4 flex flex-col md:flex-row gap-4">
        {car.image_url ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={car.image_url} alt={car.title ?? ""} className="w-full md:w-80 h-60 object-cover rounded bg-gray-200" />
        ) : (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={placeholderFor(params.id)} alt={car.title ?? ""} className="w-full md:w-80 h-60 object-cover rounded bg-gray-100" />
        )}
        <div className="flex-1 space-y-2">
          <div className="flex justify-between items-start gap-2">
            <h1 className="text-xl font-bold">{car.title ?? `${car.brand} ${car.model}`}</h1>
            <SourceBadge source={car.source} />
          </div>
          <p className="text-2xl font-bold">{car.price?.toLocaleString("pl-PL")} {car.currency}</p>
          <table className="text-sm w-full">
            <tbody>
              <tr><td className="text-gray-500 pr-4">Год</td><td>{car.year ?? "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">Пробег</td><td>{car.mileage ? `${car.mileage.toLocaleString("pl-PL")} km` : "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">Топливо</td><td>{car.fuel_type ?? "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">КПП</td><td>{car.transmission ?? "—"}</td></tr>
              <tr><td className="text-gray-500 pr-4">Локация</td><td>{car.location ?? "—"}</td></tr>
            </tbody>
          </table>
          <a href={car.url} target="_blank" rel="noreferrer" className="inline-block mt-2 text-sm text-blue-600 hover:underline">
            Открыть оригинал объявления →
          </a>
        </div>
      </div>
      <DetailsPanel carId={params.id} />
    </main>
  );
}
