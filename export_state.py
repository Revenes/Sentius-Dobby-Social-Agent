from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    browser = pw.chromium.launch_persistent_context(
        "./tw_profile",
        headless=False,
        args=["--start-maximized"]
    )
    page = browser.new_page()
    print("✅ Tarayıcı açıldı. X hesabına giriş yaptıysan 10 saniye bekle...")
    page.wait_for_timeout(10000)
    browser.storage_state(path="state.json")
    print("💾 Oturum state.json dosyasına kaydedildi.")
    browser.close()

