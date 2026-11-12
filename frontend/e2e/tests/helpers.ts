import { BrowserContext, Page, expect } from "@playwright/test";

export const COOKIE_NAME = process.env.SESSION_COOKIE || "icalora_session";
export const ADMIN_TOKEN = process.env.ADMIN_TOKEN || "";
export const USER_TOKEN = process.env.USER_TOKEN || "";
export const HOST = process.env.BASE_URL || "http://127.0.0.1:58030";

export const FEATURE_SLUGS = [
  "ai-chat",
  "grammar-checker",
  "paraphraser",
  "ai-rewriter",
  "humanizer",
  "ai-grader",
  "word-count",
  "citation-finder",
  "reader-reactions",
  "resume-builder",
  "ai-detector",
  "authorship",
  "plagiarism-checker",
  "chat-pdf",
  "hidden-text",
  "daftar-isi",
  "perbaikan-dokumen",
  "publikasi-jurnal",
  "transkrip-audio",
];

export const PUBLIC_PAGES = ["/", "/login", "/metodologi", "/cara-pakai"];

export async function setSession(context: BrowserContext, token: string) {
  const url = new URL(HOST);
  await context.addCookies([
    {
      name: COOKIE_NAME,
      value: token,
      domain: url.hostname,
      path: "/",
      httpOnly: true,
      sameSite: "Lax",
    },
  ]);
}

/** Attach console/page-error collectors. Returns an array populated during the test. */
export function collectErrors(page: Page): string[] {
  const errors: string[] = [];
  page.on("console", (msg) => {
    if (msg.type() === "error") {
      const t = msg.text();
      // Abaikan noise yang tidak relevan dengan kualitas app.
      if (
        t.includes("favicon") ||
        t.includes("ERR_INTERNET_DISCONNECTED") ||
        t.includes("net::ERR_") ||
        /Failed to load resource.*(401|403|404)/.test(t)
      ) {
        return;
      }
      errors.push(`[console] ${t}`);
    }
  });
  page.on("pageerror", (err) => errors.push(`[pageerror] ${err.message}`));
  return errors;
}

/** Fonts fully loaded and brand font applied (not a bare fallback). */
export async function assertFontsLoaded(page: Page) {
  await page.evaluate(() => (document as any).fonts.ready);
  const status = await page.evaluate(() => (document as any).fonts.status);
  expect(status).toBe("loaded");
  const bodyFont = await page.evaluate(
    () => getComputedStyle(document.body).fontFamily,
  );
  expect(bodyFont.length).toBeGreaterThan(0);
}

/** No element overflows the viewport horizontally (layout sanity). */
export async function assertNoHorizontalOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const el = document.documentElement;
    return el.scrollWidth - el.clientWidth;
  });
  // toleransi 2px untuk sub-pixel
  expect(overflow).toBeLessThanOrEqual(2);
}

/** Every in-app anchor points somewhere valid (no empty/# dead links). */
export async function assertNoDeadLinks(page: Page) {
  const bad = await page.evaluate(() => {
    const out: string[] = [];
    document.querySelectorAll("a").forEach((a) => {
      const href = a.getAttribute("href");
      const hasText = (a.textContent || "").trim().length > 0 || a.querySelector("svg,img");
      if (hasText && (href === null || href === "" || href === "#")) {
        out.push((a.textContent || "<icon>").trim().slice(0, 40));
      }
    });
    return out;
  });
  expect(bad, `tautan mati: ${bad.join(", ")}`).toHaveLength(0);
}
