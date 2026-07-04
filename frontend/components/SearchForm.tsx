"use client";
import { Filters } from "@/lib/api";

const INPUT_CLASS =
  "border border-gray-300 rounded px-2 py-1 focus:outline-none focus:ring-1 focus:ring-blue-400";

export function SearchForm({
  onSearch,
  defaults = {},
}: {
  onSearch: (f: Filters) => void;
  defaults?: Partial<Filters>;
}) {
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        const fd = new FormData(e.currentTarget);
        const str = (k: string) => (fd.get(k) as string) || undefined;
        const num = (k: string) =>
          str(k) ? Number(str(k)) : undefined;
        onSearch({
          brand: str("brand"),
          model: str("model"),
          year_min: num("year_min"),
          year_max: num("year_max"),
          price_min: num("price_min"),
          price_max: num("price_max"),
          mileage_max: num("mileage_max"),
          fuel_type: str("fuel_type"),
          transmission: str("transmission"),
        });
      }}
      className="bg-white rounded-lg shadow p-4 grid grid-cols-2 md:grid-cols-3 gap-3"
    >
      <input name="brand" placeholder="Марка" defaultValue={defaults.brand ?? ""} className={INPUT_CLASS} />
      <input name="model" placeholder="Модель" defaultValue={defaults.model ?? ""} className={INPUT_CLASS} />
      <input name="year_min" type="number" placeholder="Год от" defaultValue={defaults.year_min ?? ""} className={INPUT_CLASS} />
      <input name="year_max" type="number" placeholder="Год до" defaultValue={defaults.year_max ?? ""} className={INPUT_CLASS} />
      <input name="price_min" type="number" placeholder="Цена от" defaultValue={defaults.price_min ?? ""} className={INPUT_CLASS} />
      <input name="price_max" type="number" placeholder="Цена до" defaultValue={defaults.price_max ?? ""} className={INPUT_CLASS} />
      <input name="mileage_max" type="number" placeholder="Пробег до (км)" defaultValue={defaults.mileage_max ?? ""} className={INPUT_CLASS} />
      <select name="fuel_type" className={INPUT_CLASS} defaultValue={defaults.fuel_type ?? ""}>
        <option value="">Топливо</option>
        <option value="petrol">Бензин</option>
        <option value="diesel">Дизель</option>
        <option value="hybrid">Гибрид</option>
        <option value="electric">Электро</option>
        <option value="lpg">LPG</option>
      </select>
      <select name="transmission" className={INPUT_CLASS} defaultValue={defaults.transmission ?? ""}>
        <option value="">КПП</option>
        <option value="manual">Механика</option>
        <option value="automatic">Автомат</option>
      </select>
      <button className="col-span-2 md:col-span-3 bg-blue-600 text-white rounded py-2 hover:bg-blue-700">
        Найти
      </button>
    </form>
  );
}
