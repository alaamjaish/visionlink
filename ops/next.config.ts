import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Pi LAN access — required so HMR (hot reload) works when the user
  // visits the dashboard from another machine on the same network
  // (typical setup: dev server on Pi, browser on Windows / Mac / phone).
  // Pi LAN access from another machine (laptop / phone on the same network).
  // Canonical entry point is the mDNS hostname `visionlink.local` — that name
  // resolves no matter what IP the Pi has on a given day, so the team should
  // bookmark visionlink.local:3000 and never hardcode an IP. The IP entries
  // below are fallbacks for direct-IP access on common LAN ranges.
  // See Documentation/2.4g.md for the team resilience plan.
  allowedDevOrigins: [
    "localhost",
    "visionlink.local",   // ← canonical mDNS hostname (prefer this)
    "*.local",            // any other Bonjour-resolvable host on the LAN
    "172.20.10.*",        // iPhone Personal Hotspot subnet
    "192.168.*.*",        // home Wi-Fi / generic LAN
    "10.*.*.*",           // corporate / venue Wi-Fi
  ],
};

export default nextConfig;
