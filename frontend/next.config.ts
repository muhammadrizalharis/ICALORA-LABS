import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  /* config options here */
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  // Proxy same-origin ke backend ditangani oleh Route Handler
  // (src/app/api/backend/[...path]/route.ts) agar tidak terkena batas
  // waktu 30 detik milik rewrites bawaan Next untuk tugas LLM yang berat.
};

export default nextConfig;
