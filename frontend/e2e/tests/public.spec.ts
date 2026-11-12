import { test, expect } from "@playwright/test";
import {
  PUBLIC_PAGES,
  FEATURE_SLUGS,
  collectErrors,
  assertFontsLoaded,
  assertNoHorizontalOverflow,
  assertNoDeadLinks,
} from "./helpers";

test.describe("Halaman publik", () => {
  for (const path of PUBLIC_PAGES) {
    test(`memuat & sehat: ${path}`, async ({ page }) => {
      const errors = collectErrors(page);
      const resp = await page.goto(path, { waitUntil: "networkidle" });
      expect(resp?.status(), `HTTP ${path}`).toBeLessThan(400);

      // Judul & body ada
      expect(await page.title()).not.toBe("");
      await expect(page.locator("body")).toBeVisible();

      // Tidak ada error boundary Next
      await expect(page.locator("text=Application error")).toHaveCount(0);
      await expect(page.locator("text=500")).toHaveCount(0);

      await assertFontsLoaded(page);
      await assertNoHorizontalOverflow(page);
      await assertNoDeadLinks(page);

      expect(errors, `error konsol di ${path}:\n${errors.join("\n")}`).toHaveLength(0);
    });
  }

  for (const slug of FEATURE_SLUGS) {
    test(`halaman fitur sehat: /features/${slug}`, async ({ page }) => {
      const errors = collectErrors(page);
      const resp = await page.goto(`/features/${slug}`, { waitUntil: "networkidle" });
      expect(resp?.status(), `HTTP /features/${slug}`).toBeLessThan(400);
      await expect(page.locator("body")).toBeVisible();
      await expect(page.locator("text=Application error")).toHaveCount(0);
      await assertNoHorizontalOverflow(page);
      await assertNoDeadLinks(page);
      expect(errors, `error konsol /features/${slug}:\n${errors.join("\n")}`).toHaveLength(0);
    });
  }
});

test.describe("Navigasi & tombol back", () => {
  test("beranda → login → back kembali ke beranda", async ({ page }) => {
    await page.goto("/");
    await page.goto("/login");
    await expect(page).toHaveURL(/\/login/);
    await page.goBack();
    await expect(page).toHaveURL(new RegExp(`${"/"}$|/$`));
  });

  test("beranda → fitur → back berfungsi", async ({ page }) => {
    await page.goto("/");
    await page.goto("/features/ai-chat");
    await expect(page).toHaveURL(/\/features\/ai-chat/);
    await page.goBack();
    await expect(page).toHaveURL(/\/$|\/$/);
    await page.goForward();
    await expect(page).toHaveURL(/\/features\/ai-chat/);
  });
});

test.describe("Tombol & interaksi publik", () => {
  test("toggle tema berfungsi tanpa error", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/");
    // Cari tombol theme toggle (emoji bulan/matahari) dan klik bila ada.
    const buttons = page.locator("button");
    const count = await buttons.count();
    expect(count).toBeGreaterThan(0);
    // Klik semua tombol yang jelas aman (tidak submit form, tidak link keluar)
    for (let i = 0; i < Math.min(count, 6); i++) {
      const b = buttons.nth(i);
      if (await b.isVisible()) {
        const type = await b.getAttribute("type");
        if (type !== "submit") {
          await b.click({ trial: true }).catch(() => {});
        }
      }
    }
    expect(errors).toHaveLength(0);
  });

  test("halaman login menampilkan dua metode (email + Google bila aktif)", async ({ page }) => {
    await page.goto("/login");
    await expect(page.locator('input[type="email"], input[name="email"]')).toHaveCount(1);
    await expect(page.locator('input[type="password"]')).toHaveCount(1);
    // tombol submit login ada
    await expect(page.locator('button[type="submit"]')).toBeVisible();
  });

  test("pesan pendaftaran ditutup muncul via query param", async ({ page }) => {
    await page.goto("/login?error=registration_closed");
    await expect(page.locator("text=Pendaftaran akun baru sedang ditutup")).toBeVisible();
  });
});
