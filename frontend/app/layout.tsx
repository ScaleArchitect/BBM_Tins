import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "TIN Collection Portal",
  description: "White-label UAE TIN collection portal",
};

// English-first; the structure is RTL-ready (lang/dir become dynamic per locale
// in a later sprint — docs/architecture/05 §12.7, IA-04).
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" dir="ltr">
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased">
        {children}
      </body>
    </html>
  );
}
