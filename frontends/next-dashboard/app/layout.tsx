import type { Metadata } from "next";
import { headers } from "next/headers";
import { Inter } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import DisplayPreferenceSync from "@/components/settings/display-preference-sync";
import { CopilotProvider } from "@/lib/copilotkit/provider";
import { WorkbenchProvider } from "@/lib/workbench-context";
import { DEV_HYDRATION_WATCHDOG_SCRIPT } from "@/lib/dev-hydration-watchdog";
import "./globals.css";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "Companion X",
  description: "AI-first interface for Companion X",
};

export const dynamic = "force-dynamic";

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const nonce = (await headers()).get("x-nonce") ?? undefined;

  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.className} min-h-screen antialiased bg-background`}>
        {process.env.NODE_ENV !== "production" && (
          <script
            nonce={nonce}
            // Runs during HTML parse, before the client bundle: it is the only
            // reporter available when hydration itself never starts (GH #142).
            dangerouslySetInnerHTML={{ __html: DEV_HYDRATION_WATCHDOG_SCRIPT }}
          />
        )}
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
          nonce={nonce}
        >
          <DisplayPreferenceSync />
          <WorkbenchProvider>
            <CopilotProvider>{children}</CopilotProvider>
          </WorkbenchProvider>
          <Toaster richColors position="bottom-right" />
        </ThemeProvider>
      </body>
    </html>
  );
}
