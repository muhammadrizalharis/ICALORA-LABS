import { test, expect } from "@playwright/test";
import { setSession, ADMIN_TOKEN, USER_TOKEN, HOST, collectErrors } from "./helpers";

const API = (p: string) => `${HOST}/api/backend${p}`;

test.describe("Keamanan — kontrol akses URL kritikal", () => {
  test("/dashboard tanpa login → diarahkan ke /login", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });

  test("/admin-000 tanpa login → tampil form login, TANPA data admin", async ({ page }) => {
    await page.goto("/admin-000");
    await expect(page.locator("text=Masuk Super Admin")).toBeVisible();
    // Tidak boleh ada data panel bocor di DOM
    await expect(page.locator("text=Panel Pengelolaan")).toHaveCount(0);
    await expect(page.locator("text=@icalora-labs.local")).toHaveCount(0);
    const html = await page.content();
    expect(html).not.toContain("token_balance");
  });

  test("API admin tanpa cookie → 401", async ({ request }) => {
    for (const p of ["/auth/admin/users", "/auth/admin/settings"]) {
      const r = await request.get(API(p));
      expect(r.status(), p).toBe(401);
    }
  });

  test("API admin dengan cookie palsu → 401", async ({ request }) => {
    const r = await request.get(API("/auth/admin/users"), {
      headers: { cookie: "icalora_session=palsu.ngawur.123" },
    });
    expect(r.status()).toBe(401);
  });

  test("API admin mutasi (PATCH/PUT body valid) tanpa login → 401, tidak mengubah apa pun", async ({
    request,
  }) => {
    const patch = await request.patch(API("/auth/admin/users/1"), {
      headers: { "content-type": "application/json" },
      data: { token_balance: 999999 },
    });
    expect(patch.status()).toBe(401);
    const put = await request.put(API("/auth/admin/settings"), {
      headers: { "content-type": "application/json" },
      data: { maintenance_mode: true },
    });
    expect(put.status()).toBe(401);
  });
});

test.describe("Keamanan — user biasa (non-admin)", () => {
  test.skip(!USER_TOKEN, "USER_TOKEN tidak di-set");

  test("non-admin buka /admin-000 → tetap form login, bukan panel", async ({ browser }) => {
    const ctx = await browser.newContext();
    await setSession(ctx, USER_TOKEN);
    const page = await ctx.newPage();
    await page.goto(`${HOST}/admin-000`);
    await expect(page.locator("text=Masuk Super Admin")).toBeVisible();
    await expect(page.locator("text=Panel Pengelolaan")).toHaveCount(0);
    await ctx.close();
  });

  test("non-admin API admin → 403 (users, settings)", async ({ request }) => {
    for (const p of ["/auth/admin/users", "/auth/admin/settings"]) {
      const r = await request.get(API(p), {
        headers: { cookie: `icalora_session=${USER_TOKEN}` },
      });
      expect(r.status(), p).toBe(403);
    }
  });

  test("non-admin PATCH user lain (body valid) → 403, tidak mengubah data", async ({ request }) => {
    const r = await request.patch(API("/auth/admin/users/1"), {
      headers: { "content-type": "application/json", cookie: `icalora_session=${USER_TOKEN}` },
      data: { token_balance: 999999 },
    });
    expect(r.status()).toBe(403);
  });

  test("non-admin sidebar TIDAK menampilkan link Panel Super Admin", async ({ browser }) => {
    const ctx = await browser.newContext();
    await setSession(ctx, USER_TOKEN);
    const page = await ctx.newPage();
    await page.goto(`${HOST}/dashboard`);
    await expect(page.locator("text=Panel Pengelolaan")).toHaveCount(0);
    await ctx.close();
  });
});

test.describe("Keamanan — konfirmasi tidak ada mutasi akibat uji di atas", () => {
  test.skip(!ADMIN_TOKEN, "ADMIN_TOKEN tidak di-set");

  test("maintenance_mode tetap false & token user id=1 tidak jadi 999999", async ({ request }) => {
    const s = await request.get(API("/auth/admin/settings"), {
      headers: { cookie: `icalora_session=${ADMIN_TOKEN}` },
    });
    expect(s.status()).toBe(200);
    const body = await s.json();
    expect(body.maintenance_mode).toBe(false);

    const u = await request.get(API("/auth/admin/users?q=1"), {
      headers: { cookie: `icalora_session=${ADMIN_TOKEN}` },
    });
    const users = (await u.json()).users as Array<{ id: number; token_balance: number }>;
    const u1 = users.find((x) => x.id === 1);
    if (u1) expect(u1.token_balance).not.toBe(999999);
  });
});
