const COLORS = ["#ff3d5a", "#7c4dff", "#00a3ff", "#00b894", "#ff9f1a", "#e84393", "#2d3436"];

/** Letter avatar with a stable colour per user (no photo uploads yet). */
export function Avatar({ id, name, size = 48 }: { id: string; name: string; size?: number }) {
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
