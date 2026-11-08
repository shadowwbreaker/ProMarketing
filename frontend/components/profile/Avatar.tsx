import { API_URL } from "@/lib/api/client";

const COLORS = ["#ff3d5a", "#7c4dff", "#00a3ff", "#00b894", "#ff9f1a", "#e84393", "#2d3436"];

/** Profile photo if uploaded, otherwise a letter avatar with a stable colour per user. */
export function Avatar({ id, name, size = 48, src }: { id: string; name: string; size?: number; src?: string | null }) {
  if (src) {
    return (
      // eslint-disable-next-line @next/next/no-img-element -- served by our API, already 256x256
      <img src={`${API_URL}${src}`} alt="" width={size} height={size} className="shrink-0 rounded-full object-cover" style={{ width: size, height: size }} />
    );
  }
  const sum = [...id].reduce((a, c) => a + c.charCodeAt(0), 0);
  return (
    <span
      aria-hidden
      className="inline-flex shrink-0 select-none items-center justify-center rounded-full font-extrabold text-white"
      style={{ width: size, height: size, fontSize: size * 0.42, background: COLORS[sum % COLORS.length] }}
    >
      {(name.trim()[0] ?? "?").toUpperCase()}
    </span>
  );
}
