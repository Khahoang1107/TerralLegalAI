import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: false,
  output: "standalone",
  devIndicators: false,
  allowedDevOrigins: ["trolyphaplydatdai.online"],
  async redirects() {
    return [
      {
        source: "/app.html",
        destination: "/",
        permanent: false,
      },
    ];
  },
};

export default nextConfig;
