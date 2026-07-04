const PLACEHOLDERS = [
  "/placeholders/car-1.svg",
  "/placeholders/car-2.svg",
  "/placeholders/car-3.svg",
  "/placeholders/car-4.svg",
];

// Deterministic per-car pick (hash of id) so each listing keeps a stable image
// instead of flickering between renders.
export function placeholderFor(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i++) h = (h * 31 + id.charCodeAt(i)) | 0;
  return PLACEHOLDERS[Math.abs(h) % PLACEHOLDERS.length];
}
