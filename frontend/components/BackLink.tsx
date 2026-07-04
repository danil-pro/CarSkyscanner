"use client";
import { useRouter } from "next/navigation";

// Browser-back so returning from a car profile lands on the exact page the
// user came from (e.g. /search?<filters>, with results preserved).
export function BackLink({ label = "← Назад" }: { label?: string }) {
  const router = useRouter();
  return (
    <button
      onClick={() => router.back()}
      className="text-sm text-blue-600 hover:underline"
    >
      {label}
    </button>
  );
}
