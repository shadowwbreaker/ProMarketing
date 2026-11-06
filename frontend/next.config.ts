import type { NextConfig } from "next";

const api = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// Baseline CSP. Next.js needs inline scripts/styles for hydration; tighten with nonces before production (Phase 15).
const csp = [
  "default-src 'self'",
  `connect-src 'self' ${api}`,
  `img-src 'self' data: blob: ${api}`,
  "style-src 'self' 'unsafe-inline'",
  "script-src 'self' 'unsafe-inline'",
  "font-src 'self' data:",
  "frame-ancestors 'none'",
  "base-uri 'self'",
  "form-action 'self'",
  "object-src 'none'",
].join("; ");

const nextConfig: NextConfig = {
  poweredByHeader: false,
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "Content-Security-Policy", value: csp },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default nextConfig;
