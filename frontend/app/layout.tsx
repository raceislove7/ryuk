import { headers } from "next/headers";
import type { Metadata } from "next";
import "./globals.css";
import { SandboxNotice } from "../components/presentation";

export const metadata: Metadata = {
  title: "Ryuk — Intent before payment",
  description:
    "AI can choose. You stay in control. Evidence-backed commerce with deterministic financial authority.",
};

export default async function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  const nonce = (await headers()).get("x-nonce") || undefined;
  return (
    <html lang="en">
      <head><meta name="csp-nonce" content={nonce} /></head>
      <body><SandboxNotice />{children}</body>
    </html>
  );
}
