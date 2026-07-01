import Link from "next/link";
import { Car } from "@/lib/api";
import { SourceBadge } from "./SourceBadge";

export function CarCard({ car }: { car: Car }) {
  return (
    <Link
      href={`/cars/${car.id}`}
      className="bg-white rounded-lg shadow p-3 flex gap-3 hover:shadow-md transition"
    >
      {car.image_url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={car.image_url}
          alt={car.title ?? `${car.brand} ${car.model}`}
          className="w-32 h-24 object-cover rounded bg-gray-200 shrink-0"
        />
      ) : (
        <div className="w-32 h-24 rounded bg-gray-100 shrink-0 flex items-center justify-center text-gray-400 text-xs text-center px-1">
          Нет фото
        </div>
      )}
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
      </div>
    </Link>
  );
}
