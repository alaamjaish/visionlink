import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pi LAN access — required so HMR (hot reload) works when the user
  // visits the dashboard from another machine on the same network
  // (typical setup: dev server on Pi, browser on Windows / Mac / phone).
  allowedDevOrigins: ["192.168.0.31", "localhost"],
};

export default nextConfig;
