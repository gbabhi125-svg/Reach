export const metadata = {
  title: "REACH — Collector",
  description: "See which villages crossed quota and accept a run",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ fontFamily: "system-ui, sans-serif", margin: 0, background: "#f6f7f4", color: "#1b1b1b" }}>
        {children}
      </body>
    </html>
  );
}
