import type { Metadata } from "next";
import type { ReactNode } from "react";

import { AppHeader } from "@/shared/components/app-header";
import "@/shared/styles/index.css";

export const metadata: Metadata = {
  title: "Digital Expert Agents",
  description: "Human-verified corporate loan assessment workspace",
};

type RootLayoutProps = Readonly<{
  children: ReactNode;
}>;

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="vi">
      <body>
        <div className="min-h-screen">
          <AppHeader />
          {children}
        </div>
      </body>
    </html>
  );
}
