import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Income Verification Expert - SHB",
  description: "AI-powered Income Verification Workspace",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body className={`${inter.className} bg-slate-50 min-h-screen text-slate-900 flex flex-col`}>
        <header className="bg-[#003b71] text-white py-3 px-6 shadow-md flex justify-between items-center sticky top-0 z-50">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-orange-500 rounded font-bold flex items-center justify-center text-sm">SHB</div>
            <h1 className="text-xl font-semibold tracking-wide">Income Verification Expert</h1>
          </div>
          <div className="text-sm font-medium opacity-90 flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            LT-01 | Linh Trần (Underwriter)
          </div>
        </header>
        <main className="flex-1 w-full max-w-[1600px] mx-auto p-6">
          {children}
        </main>
      </body>
    </html>
  );
}
