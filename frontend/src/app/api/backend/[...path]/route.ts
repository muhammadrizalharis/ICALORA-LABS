import { NextRequest } from "next/server";

// Proxy same-origin ke backend. Dibuat sebagai Route Handler (bukan rewrites)
// agar tidak terkena batas waktu 30 detik milik proxy rewrite bawaan Next —
// beberapa tool LLM (Daftar Isi, Perbaikan Dokumen, Grader) butuh lebih lama.
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN ?? "http://127.0.0.1:58010";

// Beri waktu lega untuk tugas LLM yang berat (detik).
const PROXY_TIMEOUT_MS = 240_000;

export const maxDuration = 300;

const HOP_BY_HOP = new Set([
  "connection",
  "keep-alive",
  "proxy-authenticate",
  "proxy-authorization",
  "te",
  "trailer",
  "transfer-encoding",
  "upgrade",
  "content-length",
  "host",
]);

async function proxy(req: NextRequest, path: string[]): Promise<Response> {
  const search = req.nextUrl.search;
  const target = `${BACKEND_ORIGIN}/${path.join("/")}${search}`;

  const headers = new Headers();
  req.headers.forEach((value, key) => {
    if (!HOP_BY_HOP.has(key.toLowerCase())) headers.set(key, value);
  });

  const hasBody = req.method !== "GET" && req.method !== "HEAD";
  const body = hasBody ? await req.arrayBuffer() : undefined;

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), PROXY_TIMEOUT_MS);
  try {
    const upstream = await fetch(target, {
      method: req.method,
      headers,
      body,
      signal: controller.signal,
      cache: "no-store",
    });
    const respHeaders = new Headers();
    upstream.headers.forEach((value, key) => {
      if (!HOP_BY_HOP.has(key.toLowerCase())) respHeaders.set(key, value);
    });
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: respHeaders,
    });
  } catch (err) {
    const aborted = err instanceof Error && err.name === "AbortError";
    return new Response(
      JSON.stringify({
        detail: aborted
          ? "Permintaan ke backend melebihi batas waktu. Coba teks lebih pendek."
          : "Gagal menghubungi backend.",
      }),
      { status: aborted ? 504 : 502, headers: { "content-type": "application/json" } },
    );
  } finally {
    clearTimeout(timer);
  }
}

type Ctx = { params: Promise<{ path: string[] }> };

async function handler(req: NextRequest, ctx: Ctx): Promise<Response> {
  const { path } = await ctx.params;
  return proxy(req, path);
}

export {
  handler as GET,
  handler as POST,
  handler as PUT,
  handler as PATCH,
  handler as DELETE,
  handler as HEAD,
  handler as OPTIONS,
};
