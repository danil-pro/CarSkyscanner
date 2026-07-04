"use client";
import { useEffect, useState } from "react";
import { CarDetails, getCarDetails } from "@/lib/api";

export function DetailsPanel({ carId }: { carId: string }) {
  const [d, setD] = useState<CarDetails | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let alive = true;
    getCarDetails(carId)
      .then((r) => alive && setD(r))
      .catch(() => alive && setD(null))
      .finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [carId]);

  if (loading) return <p className="text-sm text-gray-500">Загрузка деталей…</p>;
  if (!d || d.status !== "ok") {
    // graceful degradation: nothing to show; the base profile + "open original" still work
    return <p className="text-sm text-gray-400">Детали недоступны — см. оригинал объявления.</p>;
  }
  return (
    <div className="space-y-3">
      {Object.keys(d.specs).length > 0 && (
        <div>
          <h2 className="font-semibold mb-1">Характеристики</h2>
          <table className="text-sm w-full">
            <tbody>
              {Object.entries(d.specs).map(([k, v]) => (
                <tr key={k}>
                  <td className="text-gray-500 pr-4 align-top w-1/3">{k}</td>
                  <td>{v}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {d.description && (
        <div>
          <h2 className="font-semibold mb-1">Описание</h2>
          <p className="text-sm text-gray-700 whitespace-pre-line">{d.description}</p>
        </div>
      )}
      {d.images.length > 0 && (
        <div>
          <h2 className="font-semibold mb-1">Фото</h2>
          <div className="grid grid-cols-3 gap-2">
            {d.images.slice(0, 12).map((src) => (
              // eslint-disable-next-line @next/next/no-img-element
              <img key={src} src={src} alt="" className="w-full h-24 object-cover rounded bg-gray-200" />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
