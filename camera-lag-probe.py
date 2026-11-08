"""Prove the damping lag: measure azimuth the instant the drag ends (no settle
wait) versus after 3s of settling. At low FPS, damping applies only 8% of the
pending rotation per rendered frame, so the camera barely moves during a drag."""
import json
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"

def az(page):
    return page.evaluate("() => ({ az: +window.__castle.controls.getAzimuthalAngle().toFixed(3), "
                         "pos: window.__castle.camera.position.toArray().map(v => +v.toFixed(1)) })")

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    fps = page.evaluate("""() => new Promise((res) => {
      let n = 0; const t0 = performance.now();
      function f() { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(f); else res((n / 3).toFixed(1)); }
      requestAnimationFrame(f);
    })""")
    print("FPS (headless SwiftShader):", fps)
    start = az(page)
    print("START:", json.dumps(start))
    page.mouse.move(640, 400)
    page.mouse.down()
    for i in range(1, 21):
        page.mouse.move(640 + i * 15, 400 - i * 5)
        page.wait_for_timeout(40)
    page.mouse.up()
    at_up = az(page)
    print("AT MOUSE.UP (no wait):", json.dumps(at_up))
    print("DELTA AT MOUSE.UP:", round(abs(at_up["az"] - start["az"]), 3))
    page.wait_for_timeout(3000)
    settled = az(page)
    print("AFTER 3s SETTLE:", json.dumps(settled))
    print("DELTA AFTER SETTLE:", round(abs(settled["az"] - start["az"]), 3))
    browser.close()
