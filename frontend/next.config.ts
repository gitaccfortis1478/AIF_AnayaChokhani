import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  env: {
    MYSPACE_PUBLIC_BACKEND_URL: process.env.MYSPACE_PUBLIC_BACKEND_URL ?? "",
    MYSPACE_PUBLIC_FRONTEND_URL: process.env.MYSPACE_PUBLIC_FRONTEND_URL ?? "",
  },
};

export default nextConfig;
