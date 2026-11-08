"""Measure the true decay curve: rAF frame count + azimuth sampled during and
after a drag, plus the live dampingFactor. Settles whether damping is the lag."""
import json
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("DAMPING:", page.evaluate("() => ({ enableDamping: window.__castle.controls.enableDamping, dampingFactor: window.__castle.controls.dampingFactor, rotateSpeed: window.__castle.controls.rotateSpeed })"))
    page.evaluate("""() => {
      window.__frames = 0;
      window.__azLog = [];
      window.__t0 = performance.now();
      function tick() {
        window.__frames++;
        window.__azLog.push([Math.round(performance.now() - window.__t0), +window.__castle.controls.getAzimuthalAngle().toFixed(3)]);
        requestAnimationFrame(tick);
      }
      requestAnimationFrame(tick);
    }""")
    page.wait_for_timeout(1000)
    page.mouse.move(640, 400)
    page.mouse.down()
    for i in range(1, 21):
        page.mouse.move(640 + i * 15, 400 - i * 5)
        page.wait_for_timeout(40)
    page.mouse.up()
    page.wait_for_timeout(4000)
    log = page.evaluate("() => ({ frames: window.__frames, log: window.__azLog })")
    print("FRAMES in ~6s:", log["frames"])
    # Print azimuth at ~0.5s buckets.
    buckets = {}
    for t, az in log["log"]:
        buckets.setdefault(int(t // 500), az)
    for b in sorted(buckets):
        print(f"t={b*500}ms az={buckets[b]}")
    browser.close()
