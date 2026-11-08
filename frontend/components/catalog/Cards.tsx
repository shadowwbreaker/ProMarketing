import Link from "next/link";
import type { SellerBrief } from "@/lib/api/public";

export function SellerLine({ s }: { s: SellerBrief }) {
  return (
    <Link href={`/sellers/${s.id}`} className="text-xs text-muted hover:text-accent">
      {s.display_name} · {s.rating != null ? `★ ${s.rating.toFixed(1)} (${s.reviews_count})` : "нет отзывов"}
    </Link>
  );
}

export function Metric({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div>
      <p className="text-[11px] uppercase tracking-wide text-muted">{label}</p>
      <p className="text-lg font-bold leading-tight">{value}</p>
      {sub && <p className="text-[11px] text-muted">{sub}</p>}
    </div>
  );
}

