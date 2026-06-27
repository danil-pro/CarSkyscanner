import { Car } from "@/lib/api";
import { SourceBadge } from "./SourceBadge";

export function CarCard({ car }: { car: Car }) {
  return (
    <div className="bg-white rounded-lg shadow p-3 flex gap-3">
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={car.image_url ?? ""}
        alt={car.title ?? `${car.brand} ${car.model}`}
        className="w-32 h-24 object-cover rounded bg-gray-200 shrink-0"
      />
      <div className="flex-1 min-w-0">
        <div className="flex justify-between items-start gap-2">
          <h3 className="font-semibold truncate">
            {car.title ?? `${car.brand} ${car.model}`}
          </h3>
          <SourceBadge source={car.source} />
        </div>
        <p className="text-lg font-bold">
          {car.price?.toLocaleString("pl-PL")} {car.currency}
        </p>
        <p className="text-sm text-gray-600">
          {car.year} • {car.mileage?.toLocaleString("pl-PL")} km •{" "}
          {car.fuel_type} • {car.transmission}
        </p>
        <p className="text-sm text-gray-500">{car.location}</p>
        <a
          href={car.url}
          target="_blank"
          rel="noreferrer"
          className="inline-block mt-2 text-sm text-blue-600 hover:underline"
        >
          Открыть объявление →
        </a>
      </div>
    </div>
  );
}
