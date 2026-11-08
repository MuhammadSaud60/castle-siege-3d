"""Phase 9 headless test: real landscape (rolling hills, forest, stones, river, animals).
Ground is 640 wide; the mountain ring is gone; the edge must stay hidden
from max zoom-out, panned corners and low angles."""
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
    print("FOG:", json.dumps(fog))
    has_mountains = page.evaluate("() => 'mountains' in window.__castle.horizon")
    print("MOUNTAINS HOOK PRESENT:", has_mountains)
    print("GROUND SIZE:", page.evaluate("() => window.__castle.groundSize()"))
    ground_size = page.evaluate("() => window.__castle.groundSize()")
    world = page.evaluate("() => ({ trees: window.__castle.world.trees(), rocks: window.__castle.world.rocks(), animals: window.__castle.world.animals(), deer: window.__castle.world.deer(), riverPoints: window.__castle.world.riverPoints() })")
    print("WORLD:", json.dumps(world))

    # Water edges must be buried: terrain at the river ribbon's edge (13 out
    # from the centreline) and at the pond rim (30 out) must sit above the
    # water level, so no floating water edge is visible.
    water_check = page.evaluate("""() => {
      const w = window.__castle.world;
      let worstRiver = Infinity, worstRiverAt = null;
      for (let x = -300; x <= 300; x += 10) {
        const lvl = w.riverWaterLevel(x);
        for (const side of [1, -1]) {
          const t = w.terrain(x, w.riverZ(x) + side * 13);
          const m = t - lvl;
          if (m < worstRiver) { worstRiver = m; worstRiverAt = [x, side]; }
        }
      }
      let worstPond = Infinity;
      const pond = w.pond();
      for (let a = 0; a < 12; a++) {
        const ang = (a / 12) * Math.PI * 2;
        const t = w.terrain(pond.x + Math.cos(ang) * 30, pond.z + Math.sin(ang) * 30);
        const m = t - w.pondWaterLevel();
        if (m < worstPond) worstPond = m;
      }
      return { worstRiver: +worstRiver.toFixed(2), worstRiverAt, worstPond: +worstPond.toFixed(2) };
    }""")
    print("WATER EDGES (terrain minus water level, must be > 0):", json.dumps(water_check))

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
    spawn = page.evaluate("""() => window.__castle.enemies.map(e => ({
      dist: Math.round(Math.hypot(e.group.position.x, e.group.position.z)),
      hp: e.hp,
      speed: e.speed,
      hasLimbs: !!e.limbs && !!e.limbs.legL && !!e.limbs.legR,
    }))""")
    print("SPAWN:", json.dumps(spawn))

    # Walk animation: a leg's swing angle must change over time.
    leg_a = page.evaluate("() => window.__castle.enemies[0].limbs.legL.rotation.x")
    page.wait_for_timeout(4000)
    leg_b = page.evaluate("() => window.__castle.enemies[0].limbs.legL.rotation.x")
    print("LEG SWING:", leg_a, "->", leg_b, "changed:", abs(leg_a - leg_b) > 0.05)

    # Deer positions over time: record now, re-check during the kill wait.
    deer0 = page.evaluate("() => window.__castle.world.deerPositions()")
    print("DEER AT START:", json.dumps([[round(x, 1), round(z, 1)] for x, z in deer0]))

    # Towers shoot and kill: move one enemy into a corner tower's range and
    # wait for an arrow kill (game time runs slow under SwiftShader).
    page.evaluate("() => { const e = window.__castle.enemies[0]; e.group.position.x = 26; e.group.position.z = 0; }")
    killed = False
    max_deer_move = 0.0

    def deer_move():
        deer_now = page.evaluate("() => window.__castle.world.deerPositions()")
        move = 0.0
        for (x0, z0), (x1, z1) in zip(deer0, deer_now):
            move = max(move, ((x1 - x0) ** 2 + (z1 - z0) ** 2) ** 0.5)
        return move

    for _ in range(45):
        page.wait_for_timeout(2000)
        max_deer_move = max(max_deer_move, deer_move())
        if page.evaluate("() => window.__castle.state.kills") > 0:
            killed = True
            break
    print("KILLS:", page.evaluate("() => window.__castle.state.kills"), "killed:", killed)
    print("ENEMIES LEFT:", page.evaluate("() => window.__castle.enemies.length"))
    # Deer move on their own slow schedule (game time runs ~7x slower than
    # wall clock under SwiftShader), and the kill wait above can end after
    # just a few seconds, so give them their own observation window: poll
    # up to 90s and stop as soon as any deer has clearly moved.
    if max_deer_move <= 0.5:
        for _ in range(45):
            page.wait_for_timeout(2000)
            max_deer_move = max(max_deer_move, deer_move())
            if max_deer_move > 0.5:
                break
    print("MAX DEER MOVEMENT:", round(max_deer_move, 2))
    print("DEER AT END:", json.dumps([[round(x, 1), round(z, 1)] for x, z in page.evaluate("() => window.__castle.world.deerPositions()")]))

    # Freeze the camera for the shots (no damping drift).
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

    # Wide shot of the whole landscape.
    shoot("phase9-wide.png", 0, 2, 0, 120, 70, 120)
    # Max zoom-out, high NE: the terrain edge must never show.
    shoot("phase9-max-ne.png", 0, 2, 0, 145, 82, 145)
    # Panned corner: target at the clamp edge, camera pushed past its
    # bound (the clamp must pull it back to radius 220).
    shoot("phase9-corner.png", 78, 2, 78, 229, 55, 229)
    cam_r = page.evaluate("() => Math.round(Math.hypot(window.__castle.camera.position.x, window.__castle.camera.position.z))")
    print("CAMERA RADIUS AFTER CLAMP:", cam_r)
    # Low angle across the map, nearly ground level.
    shoot("phase9-low.png", 0, 4, 0, 0, 14, -210)
    # Close shot of the river, framed on its centreline at x = -40.
    river = page.evaluate("() => { const w = window.__castle.world; return { z: w.riverZ(-40) }; }")
    print("RIVER Z AT X=-40:", river["z"])
    shoot("phase9-river.png", -40, 1, river["z"], -40, 16, river["z"] + 38)
    # Close shot of the forest with animals: frame the first deer live.
    # The deer lives outside the camera-target clamp (radius 110), so put
    # the camera on the radial line beyond the deer, looking back toward
    # the castle: the deer sits on the view axis whether the shot catches
    # the frame before or after the clamp pulls the target in.
    deer_pos = page.evaluate("() => { const w = window.__castle.world; const d = w.deerPositions()[0]; return { x: d[0], z: d[1], y: w.terrain(d[0], d[1]) }; }")
    print("DEER[0] FOR FOREST SHOT:", deer_pos)
    _r = (deer_pos["x"] ** 2 + deer_pos["z"] ** 2) ** 0.5
    _s = 195 / _r
    shoot("phase9-forest.png", deer_pos["x"], deer_pos["y"] + 1, deer_pos["z"], deer_pos["x"] * _s, deer_pos["y"] + 5, deer_pos["z"] * _s)
    browser.close()

# Filter the harmless SwiftShader ReadPixels warnings.
real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")

ok = True
if ground_size != 640:
    print("FAIL: ground is not 640 wide, got", ground_size); ok = False
if fog["near"] != 230 or fog["far"] != 420:
    print("FAIL: fog is", fog); ok = False
if has_mountains:
    print("FAIL: mountain hook still present"); ok = False
if cam_r > 221:
    print("FAIL: camera escaped the bound, radius", cam_r); ok = False
if world["trees"] < 80:
    print("FAIL: expected 80+ trees, got", world["trees"]); ok = False
if world["animals"] != 14:
    print("FAIL: expected 14 animals, got", world["animals"]); ok = False
if world["deer"] != 5:
    print("FAIL: expected 5 deer, got", world["deer"]); ok = False
if world["riverPoints"] <= 100:
    print("FAIL: expected 100+ river points, got", world["riverPoints"]); ok = False
if water_check["worstRiver"] <= -0.05:
    print("FAIL: river edge floats at", water_check["worstRiverAt"], water_check["worstRiver"]); ok = False
if water_check["worstPond"] <= -0.05:
    print("FAIL: pond edge floats", water_check["worstPond"]); ok = False
if farm_count != 1:
    print("FAIL: farm not placed, count", farm_count); ok = False
if len(spawn) != 3:
    print("FAIL: expected 3 enemies, got", len(spawn)); ok = False
for s in spawn:
    if not (120 <= s["dist"] <= 140):
        print("FAIL: enemy spawned at wrong distance", s); ok = False
    if s["hp"] != 2 or not s["hasLimbs"]:
        print("FAIL: enemy model wrong", s); ok = False
if abs(leg_a - leg_b) <= 0.05:
    print("FAIL: leg swing did not change"); ok = False
if not killed:
    print("FAIL: no tower kill within 90s"); ok = False
if max_deer_move <= 0.5:
    print("FAIL: deer did not move, max", max_deer_move); ok = False
if real_errors or failed_reqs:
    print("FAIL: errors or failed requests present"); ok = False
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
