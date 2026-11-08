/**
 * Brand motif: three vertical short-video frames fanned out, with stat chips —
 * the product in one picture (vertical video + real numbers). Decorative only.
 */
const FRAMES = [
  { r: -10, x: "0%", y: "14%", g: "from-[#ff3d5a] to-[#ff8a5c]", z: 1 },
  { r: 0, x: "30%", y: "0%", g: "from-[#7c4dff] to-[#ff3d5a]", z: 3 },
  { r: 9, x: "60%", y: "12%", g: "from-[#00a3ff] to-[#7c4dff]", z: 2 },
];

export function ShortsFan({ className = "" }: { className?: string }) {
  return (
    <div aria-hidden className={`pointer-events-none relative aspect-[5/4] select-none ${className}`}>
      {FRAMES.map((f, i) => (
        <div
          key={i}
          className="float-slow absolute w-[38%]"
          style={{ left: f.x, top: f.y, zIndex: f.z, ["--r" as string]: `${f.r}deg`, transform: `rotate(${f.r}deg)`, animationDelay: `${i * -2.3}s` }}
        >
          <div className={`relative aspect-[9/16] overflow-hidden rounded-[22%/12.5%] bg-gradient-to-br ${f.g} shadow-[0_20px_40px_-12px_rgb(22_24_29/0.35)]`}>
            <div className="absolute inset-x-[12%] top-[8%] h-[3%] rounded-full bg-white/35" />
            <svg viewBox="0 0 24 24" className="absolute left-1/2 top-1/2 w-[28%] -translate-x-1/2 -translate-y-1/2 text-white/90"><path d="M8 5.5v13l10.5-6.5z" fill="currentColor" /></svg>
            <div className="absolute inset-x-[12%] bottom-[10%] space-y-[6%]">
              <div className="h-1.5 w-3/4 rounded-full bg-white/50" />
              <div className="h-1.5 w-1/2 rounded-full bg-white/35" />
            </div>
          </div>
        </div>
      ))}
      <div className="float-slow absolute left-[-2%] top-[62%] z-10 rounded-2xl bg-surface px-3 py-2 text-left shadow-lg" style={{ animationDelay: "-1s" }}>
        <p className="text-sm font-extrabold leading-none">1,2 млн</p>
        <p className="mt-1 text-[10px] text-muted">подписчиков</p>
      </div>
      <div className="float-slow absolute right-[-2%] top-[4%] z-10 rounded-2xl bg-surface px-3 py-2 text-left shadow-lg" style={{ animationDelay: "-3.5s" }}>
        <p className="text-sm font-extrabold leading-none">310 тыс.</p>
        <p className="mt-1 text-[10px] text-muted">просмотров на видео</p>
      </div>
      <div className="float-slow absolute bottom-[2%] right-[8%] z-10 rounded-full bg-text px-3 py-1.5 text-[11px] font-semibold text-surface shadow-lg" style={{ animationDelay: "-5s" }}>
        ✓ оплата после проверки
      </div>
    </div>
  );
}
