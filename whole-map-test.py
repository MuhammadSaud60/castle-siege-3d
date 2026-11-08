"""Phase 10 headless test: the camera can travel the WHOLE map.
Target clamp 300, camera clamp 340, zoom-scaled WASD pan, outer terrain
ring out to 1280 so the terrain edge stays beyond the fog from every
camera angle. Game time runs ~10x slower than wall clock under
SwiftShader (delta is clamped to 0.1s), so key holds are long."""
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
        enableDamping: t.enableDamping,
      };
    }""")

def set_view(page, tx, ty, tz, cx, cy, cz):
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

def hold_key(page, keys, seconds):
    for k in keys:
        page.keyboard.down(k)
    page.wait_for_timeout(seconds * 1000)
    for k in keys:
        page.keyboard.up(k)
    page.wait_for_timeout(1200)

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("GROUND SIZE:", page.evaluate("() => window.__castle.groundSize()"))
    print("FOG:", json.dumps(page.evaluate("() => window.__castle.horizon.fog()")))
    print("RING TRIANGLES:", page.evaluate("() => window.__castle.world.ringTriangles()"))
    print("RIVER POINTS:", page.evaluate("() => window.__castle.world.riverPoints()"))
    print("DAMPING OFF:", cam(page)["enableDamping"] is False)

    # The extended river's edges must stay buried along its full length.
    water_check = page.evaluate("""() => {
      const w = window.__castle.world;
      let worstRiver = Infinity, worstRiverAt = null;
      for (let x = -630; x <= 630; x += 10) {
        const lvl = w.riverWaterLevel(x);
        for (const side of [1, -1]) {
          const t = w.terrain(x, w.riverZ(x) + side * 13);
          const m = t - lvl;
          if (m < worstRiver) { worstRiver = m; worstRiverAt = [x, side]; }
        }
      }
      return { worstRiver: +worstRiver.toFixed(2), worstRiverAt };
    }""")
    print("WATER EDGES (must be > 0):", json.dumps(water_check))

    # 1. Wheel zoom out to max distance (~220).
    page.mouse.move(640, 400)
    for _ in range(6):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(400)
    page.wait_for_timeout(1500)
    zoomed = cam(page)
    print("MAX ZOOM distance:", zoomed["distance"])
    if zoomed["distance"] < 200:
        print("FAIL: could not zoom out to max distance"); ok = False

    # 2. Pan speed must scale with zoom: far zoom moves much further than
    # close zoom for the same key hold.
    set_view(page, 0, 2, 0, 0, 95, 190)  # distance ~211, fast pan
    before_far = cam(page)
    hold_key(page, ["d"], 10)
    after_far = cam(page)
    far_delta = ((after_far["target"][0] - before_far["target"][0]) ** 2 +
                 (after_far["target"][2] - before_far["target"][2]) ** 2) ** 0.5
    set_view(page, 0, 2, 0, 14, 8, 14)  # distance ~21, slow precise pan
    before_near = cam(page)
    hold_key(page, ["d"], 10)
    after_near = cam(page)
    near_delta = ((after_near["target"][0] - before_near["target"][0]) ** 2 +
                  (after_near["target"][2] - before_near["target"][2]) ** 2) ** 0.5
    print("PAN SPEED far zoom (10s hold):", round(far_delta, 1), " near zoom:", round(near_delta, 1))
    if far_delta < 60:
        print("FAIL: far-zoom pan too slow, delta", far_delta); ok = False
    if near_delta > 40:
        print("FAIL: near-zoom pan not precise, delta", near_delta); ok = False
    if far_delta < near_delta * 3:
        print("FAIL: pan speed does not scale with zoom"); ok = False

    # 3. Cardinal pans to the map edges. Camera due south of the target
    # (0, 95, 190) makes W = north, S = south, D = east, A = west.
    edges = {}
    for key, name in [("w", "north"), ("s", "south"), ("d", "east"), ("a", "west")]:
        set_view(page, 0, 2, 0, 0, 95, 190)
        hold_key(page, [key], 30)
        state = cam(page)
        edges[name] = state
        print(f"EDGE {name.upper()} (key {key}, 30s):", json.dumps(state))
        if state["targetR"] < 290:
            print(f"FAIL: {name} edge not reached, target radius", state["targetR"]); ok = False
        if state["targetR"] > 301:
            print(f"FAIL: target escaped its bound at {name}, radius", state["targetR"]); ok = False
        if state["camR"] > 521:
            print(f"FAIL: camera escaped its bound at {name}, radius", state["camR"]); ok = False

    # 4. Corner: W+D together must reach the clamp circle diagonally.
    set_view(page, 0, 2, 0, 0, 95, 190)
    hold_key(page, ["w", "d"], 30)
    corner = cam(page)
    print("CORNER (W+D, 30s):", json.dumps(corner))
    if corner["targetR"] < 290:
        print("FAIL: corner not reached, target radius", corner["targetR"]); ok = False
    if abs(corner["target"][0]) < 150 or abs(corner["target"][2]) < 150:
        print("FAIL: corner target not diagonal", corner["target"]); ok = False
    if corner["targetR"] > 301 or corner["camR"] > 521:
        print("FAIL: bounds escaped at corner", corner); ok = False

    # 5. Right-drag pan still works.
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
    print("RIGHT-DRAG PAN delta:", round(pan_delta, 2))
    if pan_delta < 0.5:
        print("FAIL: right-drag did not pan the target"); ok = False

    # 6. Gameplay still works: place a farm, start wave 1, tower kill.
    set_view(page, 0, 2, 0, 56, 42, 56)
    page.mouse.click(640, 400)
    page.wait_for_timeout(800)
    page.click("#btn-build-farm")
    page.mouse.click(640, 620)
    page.wait_for_timeout(600)
    farm_count = page.evaluate("() => window.__castle.state.farmCount")
    print("FARM COUNT:", farm_count)
    page.click("#btn-next-wave")
    page.wait_for_timeout(800)
    spawn = page.evaluate("""() => window.__castle.enemies.map(e => ({
      dist: Math.round(Math.hypot(e.group.position.x, e.group.position.z)),
      hp: e.hp,
      speed: e.speed,
    }))""")
    print("SPAWN:", json.dumps(spawn))
    page.evaluate("() => { const e = window.__castle.enemies[0]; e.group.position.x = 26; e.group.position.z = 0; }")
    killed = False
    for _ in range(45):
        page.wait_for_timeout(2000)
        if page.evaluate("() => window.__castle.state.kills") > 0:
            killed = True
            break
    print("KILLS:", page.evaluate("() => window.__castle.state.kills"), "killed:", killed)
    if farm_count != 1:
        print("FAIL: farm not placed, count", farm_count); ok = False
    if len(spawn) != 3:
        print("FAIL: expected 3 enemies, got", len(spawn)); ok = False
    if not killed:
        print("FAIL: no tower kill within 90s"); ok = False

    # 7. Screenshots from the extremes. The camera is placed past its
    # bound on purpose in the corner shot: the clamp must pull it back
    # to radius 520.
    def shoot(name, tx, ty, tz, cx, cy, cz):
        set_view(page, tx, ty, tz, cx, cy, cz)
        page.screenshot(path=SHOT_DIR + name)
        print("SHOT:", name, json.dumps(cam(page)))

    # East edge, max zoom-out: camera south-east of the target, wheel out.
    shoot("whole-map-edge-east.png", 300, 2, 0, 300, 130, 190)
    page.mouse.move(640, 400)
    for _ in range(6):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(400)
    page.wait_for_timeout(1500)
    print("EAST MAX-ZOOM:", json.dumps(cam(page)))
    page.screenshot(path=SHOT_DIR + "whole-map-edge-east.png")
    # West edge, max zoom-out.
    shoot("whole-map-edge-west.png", -300, 2, 0, -300, 130, 190)
    page.mouse.move(640, 400)
    for _ in range(6):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(400)
    page.wait_for_timeout(1500)
    print("WEST MAX-ZOOM:", json.dumps(cam(page)))
    page.screenshot(path=SHOT_DIR + "whole-map-edge-west.png")
    # North edge, max zoom-out (camera south of the target, looking north).
    shoot("whole-map-edge-north.png", 0, 2, -300, 0, 130, -110)
    page.mouse.move(640, 400)
    for _ in range(6):
        page.mouse.wheel(0, 1200)
        page.wait_for_timeout(400)
    page.wait_for_timeout(1500)
    print("NORTH MAX-ZOOM:", json.dumps(cam(page)))
    page.screenshot(path=SHOT_DIR + "whole-map-edge-north.png")
    # Corner, low angle: target at the clamp circle, camera low and close.
    shoot("whole-map-corner-low.png", 212, 2, 212, 252, 10, 252)
    # Corner with the camera pushed far past its bound: the clamp must
    # pull it back to radius 520.
    set_view(page, 212, 2, 212, 400, 60, 400)
    clamped = cam(page)
    print("CAMERA RADIUS AFTER CLAMP:", clamped["camR"])
    if clamped["camR"] > 521:
        print("FAIL: camera escaped the bound, radius", clamped["camR"]); ok = False
    # River far east: the water must run on to the far edge, not end
    # visibly at the old 316 boundary.
    river_z = page.evaluate("() => window.__castle.world.riverZ(500)")
    shoot("whole-map-river-far.png", 500, 2, river_z, 500, 20, river_z + 45)
    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")
if real_errors or failed_reqs:
    print("FAIL: errors or failed requests present"); ok = False
if water_check["worstRiver"] <= -0.05:
    print("FAIL: river edge floats at", water_check["worstRiverAt"], water_check["worstRiver"]); ok = False
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
