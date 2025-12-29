from playwright.sync_api import sync_playwright
print('PLAYWRIGHT_TEST_START')
with sync_playwright() as p:
    b = p.chromium.launch(headless=True)
    b.close()
print('PLAYWRIGHT_TEST_OK')
