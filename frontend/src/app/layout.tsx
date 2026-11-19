import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "VYNEXA — Intelligent AI Platform",
  description: "VYNEXA is your intelligent AI companion for deep analysis, documents, and real-time conversation.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="light" style={{ colorScheme: "light" }}>
      <head>
        <link rel="icon" href="/favicon.ico" />
      </head>
      <body className="bg-white text-gray-900 antialiased font-sans select-none">
        {children}
      </body>
    </html>
  );
}
