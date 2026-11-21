import type { NextConfig } from "next";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { parseEnv } from "node:util";

function readRootEnv() {
  try {
    return parseEnv(readFileSync(resolve(process.cwd(), "../.env"), "utf8"));
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code !== "ENOENT") throw error;
    return {};
  }
}

const rootEnv = readRootEnv();

const nextConfig: NextConfig = {
  env: {
    MYSPACE_PUBLIC_BACKEND_URL:
      process.env.MYSPACE_PUBLIC_BACKEND_URL ?? rootEnv.MYSPACE_PUBLIC_BACKEND_URL ?? "",
    MYSPACE_PUBLIC_FRONTEND_URL:
      process.env.MYSPACE_PUBLIC_FRONTEND_URL ?? rootEnv.MYSPACE_PUBLIC_FRONTEND_URL ?? "",
  },
};

export default nextConfig;
