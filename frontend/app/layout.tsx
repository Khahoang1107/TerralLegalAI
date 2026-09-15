import type { Metadata } from "next";
import { Plus_Jakarta_Sans } from "next/font/google";
import "./globals.css";

const jakarta = Plus_Jakarta_Sans({
  subsets: ["latin", "vietnamese"],
  display: "swap",
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: "TerraLegalAI - Trợ lý pháp lý thủ tục đất đai",
  description: "Hệ thống thông tin và tra cứu thủ tục pháp lý đất đai thông minh",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="vi" className={`h-full antialiased ${jakarta.variable}`}>
      <body className={`min-h-full flex flex-col font-sans ${jakarta.className}`}>{children}</body>
    </html>
  );
}

