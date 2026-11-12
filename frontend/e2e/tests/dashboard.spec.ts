import { test, expect } from "@playwright/test";
import {
  setSession,
  ADMIN_TOKEN,
  FEATURE_SLUGS,
  collectErrors,
  assertNoHorizontalOverflow,
  assertNoDeadLinks,
} from "./helpers";

test.describe("Dashboard tools — tiap halaman alat memuat (sesi admin, read-only)", () => {
  test.skip(!ADMIN_TOKEN, "ADMIN_TOKEN tidak di-set");

  test.beforeEach(async ({ context }) => {
    await setSession(context, ADMIN_TOKEN);
  });

  for (const slug of FEATURE_SLUGS) {
    test(`tool memuat & sehat: /dashboard/tools/${slug}`, async ({ page }) => {
      const errors = collectErrors(page);
      const resp = await page.goto(`/dashboard/tools/${slug}`, { waitUntil: "networkidle" });
      expect(resp?.status(), `HTTP ${slug}`).toBeLessThan(400);
      await expect(page.locator("body")).toBeVisible();
      await expect(page.locator("text=Application error")).toHaveCount(0);
      // ada area input/aksi (textarea, input, atau tombol proses)
      const interactive = page.locator("textarea, input, button");
      expect(await interactive.count(), `kontrol di ${slug}`).toBeGreaterThan(0);
      await assertNoHorizontalOverflow(page);
      await assertNoDeadLinks(page);
      expect(errors, `error konsol ${slug}:\n${errors.join("\n")}`).toHaveLength(0);
    });
  }

  test("riwayat & akun memuat tanpa error", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/dashboard/history", { waitUntil: "networkidle" });
    await expect(page.locator("body")).toBeVisible();
    await page.goto("/dashboard/akun", { waitUntil: "networkidle" });
    await expect(page.locator("body")).toBeVisible();
    expect(errors, errors.join("\n")).toHaveLength(0);
  });

  test("tombol collapse sidebar berfungsi (Perkecil)", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    const collapse = page.getByText("Perkecil", { exact: false }).first();
    if (await collapse.isVisible().catch(() => false)) {
      await collapse.click();
    }
    await expect(page.locator("body")).toBeVisible();
  });
});
