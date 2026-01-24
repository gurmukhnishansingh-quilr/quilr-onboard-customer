import "./globals.css";
import { ThemeProvider } from "../lib/ThemeContext";

export const metadata = {
  title: "Quilr Onboarding Portal",
  description: "Customer onboarding and instance management",
  icons: {
    icon: "/icons/logo.ico",
    shortcut: "/icons/logo.ico",
    apple: "/icons/logo_128x128.png",
    other: [
      {
        rel: "icon",
        url: "/icons/logo_32x32.png",
        sizes: "32x32",
        type: "image/png"
      },
      {
        rel: "icon",
        url: "/icons/logo_16x16.png",
        sizes: "16x16",
        type: "image/png"
      }
    ]
  }
};

export default function RootLayout({
  children
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <ThemeProvider>{children}</ThemeProvider>
      </body>
    </html>
  );
}
