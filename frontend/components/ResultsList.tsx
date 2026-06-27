import { Car } from "@/lib/api";
import { CarCard } from "./CarCard";

export function ResultsList({
  cars,
  loading,
}: {
  cars: Car[];
  loading: boolean;
}) {
  if (loading) return <p className="text-gray-500">Загрузка…</p>;
  if (!cars.length)
    return <p className="text-gray-500">Ничего не найдено.</p>;
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {cars.map((c) => (
        <CarCard key={c.id} car={c} />
      ))}
    </div>
  );
}
