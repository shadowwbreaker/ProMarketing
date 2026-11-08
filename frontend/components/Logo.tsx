/**
 * ProMarketing mark: a 9:16 short-video frame with a play notch and a rising bar —
 * "ads inside vertical video". Own identity, no third-party shapes.
 */
export function LogoMark({ size = 28 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <defs>
        <linearGradient id="pm-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#ff3d5a" />
          <stop offset="1" stopColor="#7c4dff" />
        </linearGradient>
      </defs>
      <rect x="8" y="2" width="16" height="28" rx="5" fill="url(#pm-g)" />
      <path d="M13.5 11.5v9l7-4.5z" fill="#fff" />
      <rect x="11" y="24" width="10" height="2" rx="1" fill="#fff" opacity=".55" />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2">
      <LogoMark />
      <span className="hidden text-lg font-extrabold tracking-tight min-[420px]:inline">
        Pro<span className="bg-gradient-to-r from-accent to-[#7c4dff] bg-clip-text text-transparent">Marketing</span>
      </span>
    </span>
  );
}
