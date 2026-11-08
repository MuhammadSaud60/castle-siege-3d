"""Quick FPS probe: load a URL, wait, measure rAF rate over 4 seconds."""
import sys
from playwright.sync_api import sync_playwright

url = sys.argv[1]
with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    fps = page.evaluate("""() => new Promise((res) => {
      let n = 0; const t0 = performance.now();
      function f() { n++; if (performance.now() - t0 < 4000) requestAnimationFrame(f); else res((n / 4).toFixed(1)); }
      requestAnimationFrame(f);
    })""")
    print(f"{url} FPS: {fps}")
    browser.close()
