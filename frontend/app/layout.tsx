import type { Metadata } from "next";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { ToastProvider } from "@/components/ui/Toast";

export const metadata: Metadata = {
  title: "ProMarketing — реклама у авторов коротких видео",
  description: "Маркетплейс рекламы в TikTok и YouTube Shorts с защитой сделок",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ru">
      <body className="font-sans antialiased">
        <ToastProvider>
          <SiteHeader />
          <main className="mx-auto max-w-6xl px-4 py-8">{children}</main>
        </ToastProvider>
      </body>
    </html>
  );
}
