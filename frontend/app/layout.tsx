import type { Metadata } from "next";
import "./globals.css";
import { SiteFooter } from "@/components/SiteFooter";
import { SiteHeader } from "@/components/SiteHeader";
import { ToastProvider } from "@/components/ui/Toast";
import { AuthProvider } from "@/lib/auth/AuthProvider";

export const metadata: Metadata = {
  title: "ProMarketing — реклама у авторов коротких видео",
  description: "Маркетплейс рекламы в TikTok и YouTube Shorts с защитой сделок",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="font-sans antialiased">
        <ToastProvider>
          <AuthProvider>
            <SiteHeader />
            <main className="mx-auto min-h-[70dvh] max-w-6xl px-4 py-8">{children}</main>
            <SiteFooter />
          </AuthProvider>
        </ToastProvider>
      </body>
    </html>
  );
}
