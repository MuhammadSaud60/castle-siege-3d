"""Focused check for the Phase 10 river fix: the outer ring now uses a
10-unit grid, so the river channel must stay visible (water above the
ring surface) all the way to the far edge at x = 636, not buried under
coarse ring triangles."""
import json
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []
failed_reqs = []

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("RING TRIANGLES:", page.evaluate("() => window.__castle.world.ringTriangles()"))

    def shoot(name, tx, ty, tz, cx, cy, cz):
        page.evaluate(
            """([tx, ty, tz, cx, cy, cz]) => {
              const c = window.__castle.camera, t = window.__castle.controls;
              t.target.set(tx, ty, tz);
              c.position.set(cx, cy, cz);
              t.update();
            }""",
            [tx, ty, tz, cx, cy, cz],
        )
        page.wait_for_timeout(1200)
        page.screenshot(path=SHOT_DIR + name)
        print("SHOT:", name)

    river_z = page.evaluate("() => window.__castle.world.riverZ(500)")
    shoot("whole-map-river-far.png", 500, 2, river_z, 500, 20, river_z + 45)
    shoot("whole-map-edge-east.png", 300, 2, 0, 300, 130, 190)
    page.mouse.move(640, 400)
    for _ in range(6):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(400)
    page.wait_for_timeout(1500)
    page.screenshot(path=SHOT_DIR + "whole-map-edge-east.png")
    print("EAST MAX-ZOOM:", page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      return { targetR: +Math.hypot(t.target.x, t.target.z).toFixed(1),
               camR: +Math.hypot(c.position.x, c.position.z).toFixed(1) };
    }"""))
    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs) if failed_reqs else "none")
ok = not real_errors and not failed_reqs
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
