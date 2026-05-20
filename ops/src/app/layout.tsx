import type { Metadata } from "next";
import "./globals.css";
import Nav from "@/components/Nav";

export const metadata: Metadata = {
  title: "VisionLink Ops",
  description: "Factory operations dashboard for VisionLink wearable",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        <Nav />
        <main className="flex-1 max-w-[1500px] w-full mx-auto px-8 py-6">
          {children}
        </main>
      </body>
    </html>
  );
}
