export const metadata = {
  title: "REACH — Generator",
  description: "List your waste and track your village's quota progress",
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
