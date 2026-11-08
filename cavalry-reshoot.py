"""Re-shoot the cavalry close-up at a 3/4 front angle: teleport the rider
to open ground, put the camera front-left of him, screenshot fast before
he rides far (cavalry moves 4.2 u/s)."""
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.evaluate("() => { const s = window.__castle.state; s.wave = 1; s.waveActive = false; }")
    page.click("#btn-next-wave")
    page.wait_for_timeout(2500)
    cav = page.evaluate("() => { const e = window.__castle.enemies.find(e => e.type === 'cavalry'); return e ? { x: e.group.position.x, z: e.group.position.z } : null; }")
    print("CAVALRY:", cav)
    if not cav:
        print("no cavalry found")
        sys.exit(1)
    # Teleport to (30, 30) and set a 3/4 front-left camera in one evaluate,
    # then shoot fast.
    page.evaluate(
        """() => {
          const c = window.__castle;
          const cav = c.enemies.find(e => e.type === 'cavalry');
          cav.group.position.set(30, c.world.terrain(30, 30), 30);
          cav.target = null;
          // Horse at (30,30) faces the keep: facing ~(-0.707,-0.707).
          // Camera front-left: facing*12 + side*8, y 7.
          c.controls.target.set(30, 2.2, 30);
          c.camera.position.set(27.2, 7, 15.8);
          c.controls.update();
        }"""
    )
    page.wait_for_timeout(400)
    page.screenshot(path=SHOT_DIR + "cavalry-close-v2.png")
    print("SHOT: cavalry-close-v2.png")
    print("ERRORS:", errors if errors else "none")
    browser.close()
