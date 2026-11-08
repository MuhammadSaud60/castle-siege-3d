"""Phase 8 headless test: endless horizon (fog + mountain ring + skirt)."""
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
    print("CANVAS:", page.evaluate("() => !!document.querySelector('#app canvas')"))
    fog = page.evaluate("() => window.__castle.horizon.fog()")
    print("HORIZON:", json.dumps(fog))
    mountains = page.evaluate("() => window.__castle.horizon.mountains()")
    print("MOUNTAINS:", mountains)
    print("GROUND SIZE:", page.evaluate("() => window.__castle.groundSize()"))

    # Frame rate over 3 seconds (SwiftShader, so this is a floor).
    fps = page.evaluate("""() => new Promise((res) => {
      let n = 0; const t0 = performance.now();
      function f() { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(f); else res((n / 3).toFixed(1)); }
      requestAnimationFrame(f);
    })""")
    print("FPS (headless SwiftShader):", fps)

    # Gameplay still works: place a farm, start wave 1.
    page.mouse.click(640, 400)
    page.wait_for_timeout(800)
    page.click("#btn-build-farm")
    page.mouse.click(640, 620)
    page.wait_for_timeout(600)
    farm_count = page.evaluate("() => window.__castle.state.farmCount")
    print("FARM COUNT:", farm_count)
    page.click("#btn-next-wave")
    page.wait_for_timeout(800)
    enemy_count = page.evaluate("() => window.__castle.enemies.length")
    print("ENEMIES:", enemy_count)

    # Freeze the camera for the worst-angle shots (no damping drift).
    page.evaluate("() => { window.__castle.controls.enableDamping = false; }")

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
        page.wait_for_timeout(1000)
        page.screenshot(path=SHOT_DIR + name)
        print("SHOT:", name)

    # Max zoom-out (220) in three directions: high NE, low SW, mid SE.
    shoot("phase8-shot-max-ne.png", 0, 2, 0, 145, 82, 145)
    shoot("phase8-shot-max-sw-low.png", 0, 2, 0, -155, 21, -155)
    shoot("phase8-shot-max-se.png", 0, 2, 0, 152, 48, -152)
    # Camera panned to a map corner, looking back across the map. The
    # target clamp (radius 110) and camera clamp (radius 220) keep the
    # camera inside the mountain ring, so no peak ends up between the
    # camera and the castle. The test sets the camera past the bound to
    # prove the clamp engages.
    shoot("phase8-shot-corner.png", 78, 2, 78, 229, 55, 229)
    cam_r = page.evaluate("() => Math.round(Math.hypot(window.__castle.camera.position.x, window.__castle.camera.position.z))")
    print("CAMERA RADIUS AFTER CLAMP:", cam_r)
    # Low angle across the map, nearly ground level.
    shoot("phase8-shot-low.png", 0, 4, 0, 0, 14, -210)
    browser.close()

# Filter the harmless SwiftShader ReadPixels warnings.
real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")

ok = True
if fog["near"] != 250 or fog["far"] != 430:
    print("FAIL: fog is", fog); ok = False
if mountains < 30:
    print("FAIL: expected 30+ mountains, got", mountains); ok = False
if farm_count != 1:
    print("FAIL: farm not placed, count", farm_count); ok = False
if enemy_count != 3:
    print("FAIL: expected 3 enemies, got", enemy_count); ok = False
if cam_r > 221:
    print("FAIL: camera escaped the ring, radius", cam_r); ok = False
if real_errors or failed_reqs:
    print("FAIL: errors or failed requests present"); ok = False
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
