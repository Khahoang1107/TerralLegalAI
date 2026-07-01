import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
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
