"""Camera fix test: with damping off, a drag must move the camera IMMEDIATELY
(azimuth recorded in-page at the moment of mouse release), wheel zoom and
right-drag pan must work, WASD keys must move the view away from the castle,
and the camera must stay inside its bounds with no terrain edge visible."""
import json
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []
failed_reqs = []
ok = True

def cam(page):
    return page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      const d = Math.hypot(c.position.x - t.target.x, c.position.y - t.target.y, c.position.z - t.target.z);
      return {
        pos: c.position.toArray().map(v => +v.toFixed(2)),
        target: t.target.toArray().map(v => +v.toFixed(2)),
        targetR: +Math.hypot(t.target.x, t.target.z).toFixed(2),
        camR: +Math.hypot(c.position.x, c.position.z).toFixed(2),
        distance: +d.toFixed(2),
        azimuth: +t.getAzimuthalAngle().toFixed(3),
        polar: +t.getPolarAngle().toFixed(3),
        enableDamping: t.enableDamping,
      };
    }""")

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("DAMPING OFF:", cam(page)["enableDamping"] is False)

    # In-page probe: record the azimuth on the main thread at mouse release.
    page.evaluate("""() => {
      window.__azAtUp = null;
      document.querySelector('#app canvas').addEventListener('pointerup', () => {
        window.__azAtUp = +window.__castle.controls.getAzimuthalAngle().toFixed(3);
      });
    }""")
    before = cam(page)
    print("BEFORE DRAG:", json.dumps(before))
    page.screenshot(path=SHOT_DIR + "camera-fix-before.png")

    # 1. Left-drag rotate; azimuth must already have moved at mouse release.
    page.mouse.move(640, 400)
    page.mouse.down()
    for i in range(1, 21):
        page.mouse.move(640 + i * 15, 400 - i * 5)
        page.wait_for_timeout(40)
    page.mouse.up()
    az_at_up = page.evaluate("() => window.__azAtUp")
    after_drag = cam(page)
    print("AZIMUTH AT MOUSE.UP (in-page):", az_at_up, " start:", before["azimuth"])
    print("AFTER LEFT-DRAG:", json.dumps(after_drag))
    page.screenshot(path=SHOT_DIR + "camera-fix-after-drag.png")
    if az_at_up is None or abs(az_at_up - before["azimuth"]) < 0.5:
        print("FAIL: camera did not move during the drag (still lagging)"); ok = False
    if abs(after_drag["azimuth"] - before["azimuth"]) < 0.5:
        print("FAIL: left-drag did not rotate the camera"); ok = False

    # 2. Wheel zoom.
    before_zoom = cam(page)
    page.mouse.move(640, 400)
    page.mouse.wheel(0, -900)
    page.wait_for_timeout(1500)
    after_zoom = cam(page)
    print("ZOOM distance:", before_zoom["distance"], "->", after_zoom["distance"])
    if abs(after_zoom["distance"] - before_zoom["distance"]) < 0.5:
        print("FAIL: wheel did not change camera distance"); ok = False

    # 3. Right-drag pan.
    before_pan = cam(page)
    page.mouse.move(640, 400)
    page.mouse.down(button="right")
    for i in range(1, 21):
        page.mouse.move(640 - i * 10, 400)
        page.wait_for_timeout(40)
    page.mouse.up(button="right")
    page.wait_for_timeout(1500)
    after_pan = cam(page)
    pan_delta = ((after_pan["target"][0] - before_pan["target"][0]) ** 2 +
                 (after_pan["target"][2] - before_pan["target"][2]) ** 2) ** 0.5
    print("PAN target delta:", round(pan_delta, 2))
    if pan_delta < 0.5:
        print("FAIL: right-drag did not pan the target"); ok = False

    # 4. Keyboard pan: hold D for 3s, the target must move away from the castle.
    before_key = cam(page)
    page.keyboard.down("d")
    page.wait_for_timeout(3000)
    page.keyboard.up("d")
    page.wait_for_timeout(1000)
    after_key = cam(page)
    key_delta = ((after_key["target"][0] - before_key["target"][0]) ** 2 +
                 (after_key["target"][2] - before_key["target"][2]) ** 2) ** 0.5
    print("KEYBOARD PAN (D, 3s) target:", before_key["target"], "->", after_key["target"], "delta:", round(key_delta, 2))
    if key_delta < 2:
        print("FAIL: WASD did not move the camera target"); ok = False

    # 5. Bounds: pan to the edge with keys, zoom all the way out, check the
    # clamps still hold and take a max zoom-out shot (edge must stay hidden).
    page.keyboard.down("d")
    page.wait_for_timeout(5000)
    page.keyboard.up("d")
    page.mouse.move(640, 400)
    page.mouse.wheel(0, 2400)
    page.wait_for_timeout(2000)
    edge = cam(page)
    print("AT EDGE (max zoom-out, panned):", json.dumps(edge))
    if edge["targetR"] > 110.5:
        print("FAIL: target escaped its bound, radius", edge["targetR"]); ok = False
    if edge["camR"] > 220.5:
        print("FAIL: camera escaped its bound, radius", edge["camR"]); ok = False
    page.screenshot(path=SHOT_DIR + "camera-fix-max-out.png")

    # Gameplay still works after the camera changes: place a farm, wave 1.
    page.mouse.click(640, 400)
    page.wait_for_timeout(500)
    page.click("#btn-build-farm")
    page.wait_for_timeout(500)
    page.click("#btn-next-wave")
    page.wait_for_timeout(4000)
    wave = page.evaluate("() => ({ wave: window.__castle.state.wave, enemies: window.__castle.enemies.length })")
    print("WAVE CHECK:", json.dumps(wave))
    if wave["enemies"] < 1:
        print("FAIL: wave did not spawn enemies"); ok = False

    print("ERRORS:", errors if errors else "none")
    print("FAILED REQUESTS:", failed_reqs if failed_reqs else "none")
    if errors or failed_reqs:
        ok = False
    print("RESULT:", "PASS" if ok else "FAIL")
    browser.close()
    sys.exit(0 if ok else 1)
