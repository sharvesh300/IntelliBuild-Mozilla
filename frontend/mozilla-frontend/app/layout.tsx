import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";

const outfit = Outfit({
  variable: "--font-outfit",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "IntelliBuild Workspace — Local RAG",
  description: "Interact with local LLMs grounded in your custom knowledge base.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${outfit.variable} h-full antialiased dark`}>
      <body className="h-full bg-[#0c0a12] text-[#f3f4f6] font-sans antialiased flex flex-col">
        {children}
      </body>
    </html>
  );
}
