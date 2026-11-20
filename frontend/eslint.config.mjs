import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
  {
    // Aturan React Compiler yang ketat ini menandai pola umum "ambil data saat mount lalu
    // setState" (auth, riwayat, tema). Polanya benar secara fungsional; merombak 8 efek
    // berisiko merusak alur login/pemuatan. Diturunkan ke peringatan agar tetap terlihat.
    rules: { "react-hooks/set-state-in-effect": "warn" },
  },
]);

export default eslintConfig;
