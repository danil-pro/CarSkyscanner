const COLORS: Record<string, string> = {
  otomoto: "bg-orange-100 text-orange-800",
  olx: "bg-blue-100 text-blue-800",
  facebook: "bg-indigo-100 text-indigo-800",
};

export function SourceBadge({ source }: { source: string }) {
  return (
    <span
      className={`px-2 py-0.5 rounded text-xs font-semibold ${
        COLORS[source] ?? "bg-gray-200 text-gray-800"
      }`}
    >
      {source.toUpperCase()}
    </span>
  );
}
