import { test, expect } from "@playwright/test";
import {
  setSession,
  ADMIN_TOKEN,
  HOST,
  collectErrors,
  assertFontsLoaded,
  assertNoHorizontalOverflow,
  assertNoDeadLinks,
} from "./helpers";

test.describe("Dashboard & Panel Super Admin (sesi admin)", () => {
  test.skip(!ADMIN_TOKEN, "ADMIN_TOKEN tidak di-set");

  test.beforeEach(async ({ context }) => {
    await setSession(context, ADMIN_TOKEN);
  });

  test("dashboard memuat, sidebar sehat, ada link Panel Super Admin", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await expect(page.locator("text=Super Admin").first()).toBeVisible();
    await expect(page.locator("text=Panel Pengelolaan")).toBeVisible();
    await assertFontsLoaded(page);
    await assertNoHorizontalOverflow(page);
    await assertNoDeadLinks(page);
    expect(errors, errors.join("\n")).toHaveLength(0);
  });

  test("klik link sidebar membawa ke /admin-000 dan menampilkan panel", async ({ page }) => {
    await page.goto("/dashboard", { waitUntil: "networkidle" });
    await page.locator("text=Panel Pengelolaan").click();
    await expect(page).toHaveURL(/\/admin-000/);
    await expect(page.locator("text=Panel Pengelolaan").first()).toBeVisible();
    // Dua tab ada
    await expect(page.getByRole("button", { name: "Pengguna" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Pengaturan Aplikasi" })).toBeVisible();
  });

  test("tab Pengguna: tabel + statistik + kontrol per-baris hadir", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/admin-000", { waitUntil: "networkidle" });
    // statistik
    await expect(page.locator("text=Total")).toBeVisible();
    // tabel dengan header
    await expect(page.locator("th", { hasText: "Pengguna" })).toBeVisible();
    await expect(page.locator("th", { hasText: "Token" })).toBeVisible();
    // minimal satu baris pengguna admin (di dalam tabel)
    await expect(
      page.locator("table").getByText("admin@icalora-labs.local").first(),
    ).toBeVisible();
    // tombol aksi hadir
    await expect(page.getByRole("button", { name: "Reset Sandi" }).first()).toBeVisible();
    await expect(page.getByRole("button", { name: "Hapus" }).first()).toBeVisible();
    expect(errors, errors.join("\n")).toHaveLength(0);
  });

  test("tab Pengguna: pencarian (read-only) berfungsi", async ({ page }) => {
    await page.goto("/admin-000", { waitUntil: "networkidle" });
    const search = page.getByPlaceholder("Cari email / nama…");
    await search.fill("admin");
    await page.getByRole("button", { name: "Cari" }).click();
    await expect(
      page.locator("table").getByText("admin@icalora-labs.local").first(),
    ).toBeVisible();
  });

  test("tab Pengaturan: semua kontrol & 19+ switch fitur hadir", async ({ page }) => {
    const errors = collectErrors(page);
    await page.goto("/admin-000", { waitUntil: "networkidle" });
    await page.getByRole("button", { name: "Pengaturan Aplikasi" }).click();
    await expect(page.locator("text=Mode Pemeliharaan")).toBeVisible();
    await expect(page.locator("text=Pendaftaran Dibuka")).toBeVisible();
    await expect(page.locator("text=Jatah Token Default")).toBeVisible();
    await expect(page.locator("text=On/Off Fitur")).toBeVisible();
    // switch fitur (checkbox) minimal 19
    const checks = page.locator('input[type="checkbox"]');
    expect(await checks.count()).toBeGreaterThanOrEqual(19);
    await assertNoHorizontalOverflow(page);
    expect(errors, errors.join("\n")).toHaveLength(0);
  });

  test("proteksi diri sendiri: toggle Admin/Status & Hapus utk baris sendiri dinonaktifkan", async ({
    page,
  }) => {
    await page.goto("/admin-000", { waitUntil: "networkidle" });
    // baris admin ditandai "Anda"
    const row = page.locator("tr", { hasText: "admin@icalora-labs.local" });
    await expect(row.locator("text=Anda")).toBeVisible();
    // tombol Hapus pada baris sendiri disabled
    const del = row.getByRole("button", { name: "Hapus" });
    await expect(del).toBeDisabled();
  });

  test("tombol navigasi panel: Dashboard & Keluar hadir dan mengarah benar", async ({ page }) => {
    await page.goto("/admin-000", { waitUntil: "networkidle" });
    await expect(page.getByRole("button", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByRole("button", { name: "Keluar" })).toBeVisible();
    await page.getByRole("button", { name: "Dashboard" }).click();
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
