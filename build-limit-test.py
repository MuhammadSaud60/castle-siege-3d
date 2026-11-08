"""Build-limit test: buildings may only be placed within BUILD_RADIUS (75)
of the keep. Inside the limit placement works; outside it the ghost turns
red, the status says 'Too far from the keep', and nothing is placed. The
amber boundary ring is visible on the ground. Also re-checks drag-to-build
across the boundary and that a player-built tower still shoots."""
import json
import math
import sys
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []
failed_reqs = []
checks = []

def check(name, ok, detail=""):
    checks.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail else ""))

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.evaluate("() => { window.__castle.state.stone = 500; window.__castle.state.wood = 500; }")

    # High top-down view over the keep.
    page.evaluate(
        """() => {
          const c = window.__castle.camera, t = window.__castle.controls;
          t.target.set(0, 2, 0);
          c.position.set(0, 110, 70);
          t.update();
        }"""
    )
    page.wait_for_timeout(1200)

    radius = page.evaluate("() => window.__castle.buildRadius()")
    print("BUILD RADIUS:", radius)
    check("build radius is 75", radius == 75, f"radius={radius}")
    check("keep is in the build area", page.evaluate("() => window.__castle.inBuildArea(0, 0)"))
    check("point at 100,0 is outside", not page.evaluate("() => window.__castle.inBuildArea(100, 0)"))
    check("point at 74,0 is inside", page.evaluate("() => window.__castle.inBuildArea(74, 0)"))

    # Wide shot: the amber boundary ring should be visible around the keep.
    page.evaluate(
        """() => {
          const c = window.__castle.camera, t = window.__castle.controls;
          t.target.set(0, 2, 0);
          c.position.set(0, 190, 150);
          t.update();
        }"""
    )
    page.wait_for_timeout(1200)
    page.screenshot(path=SHOT_DIR + "build-limit-ring.png")
    print("SHOT: build-limit-ring.png")
    page.evaluate(
        """() => {
          const c = window.__castle.camera, t = window.__castle.controls;
          t.target.set(0, 2, 0);
          c.position.set(0, 110, 70);
          t.update();
        }"""
    )
    page.wait_for_timeout(1200)

    # Inside the limit: a click places a house.
    page.click("#btn-build-house")
    page.wait_for_timeout(400)
    page.mouse.move(640, 520)
    page.wait_for_timeout(500)
    ghost = page.evaluate("() => window.__castle.placing()")
    print("INSIDE GHOST:", json.dumps(ghost))
    check("ghost green inside the limit", ghost["ghostColor"] == "#7ec850", ghost["ghostColor"])
    before = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'house').length")
    page.mouse.click(640, 520)
    page.wait_for_timeout(600)
    after = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'house').length")
    check("house placed inside the limit", after - before == 1, f"{before} -> {after}")

    # Outside the limit: hover far from the keep (screen corner maps well
    # beyond radius 75). Ghost must be red, status must say so, and a
    # click must place nothing.
    page.mouse.move(80, 200)
    page.wait_for_timeout(500)
    ghost = page.evaluate("() => window.__castle.placing()")
    status = page.inner_text("#wave-status")
    print("OUTSIDE GHOST:", json.dumps(ghost), "STATUS:", status)
    check("ghost red outside the limit", ghost["ghostColor"] == "#d23b2e", ghost["ghostColor"])
    check("status says too far from the keep", status == "Too far from the keep", status)
    page.screenshot(path=SHOT_DIR + "build-limit-outside.png")
    print("SHOT: build-limit-outside.png")
    before = page.evaluate("() => window.__castle.built.length")
    page.mouse.click(80, 200)
    page.wait_for_timeout(600)
    after = page.evaluate("() => window.__castle.built.length")
    check("nothing placed outside the limit", after == before, f"{before} -> {after}")
    page.click("#btn-build-house")  # leave placing mode
    page.wait_for_timeout(300)

    # Drag-to-build across the boundary: only the in-range segments land.
    page.click("#btn-build-wall")
    page.wait_for_timeout(400)
    page.mouse.move(640, 520)
    page.wait_for_timeout(300)
    page.mouse.down()
    for x in range(600, 81, -40):
        page.mouse.move(x, 520)
        page.wait_for_timeout(120)
    page.mouse.up()
    page.wait_for_timeout(800)
    walls = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall')")
    print("WALLS AFTER BOUNDARY DRAG:", json.dumps(walls))
    check("drag across boundary placed some segments", len(walls) >= 3, f"count={len(walls)}")
    check("no dragged segment outside the limit",
          all(math.hypot(w["x"], w["z"]) <= 75 for w in walls),
          f"max r={max((math.hypot(w['x'], w['z']) for w in walls), default=0):.1f}")
    page.screenshot(path=SHOT_DIR + "build-limit-drag.png")
    print("SHOT: build-limit-drag.png")
    page.click("#btn-build-wall")
    page.wait_for_timeout(300)

    # Tower still shoots: place a tower, start wave 1, teleport one enemy
    # into its range (headless game time runs far slower than wall clock,
    # so waiting for it to walk in would take minutes), then watch for
    # arrows or a kill.
    page.click("#btn-build-tower")
    page.wait_for_timeout(400)
    page.mouse.move(700, 560)
    page.wait_for_timeout(400)
    page.mouse.click(700, 560)
    page.wait_for_timeout(600)
    tower = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'tower').slice(-1)[0]")
    print("TOWER:", json.dumps(tower))
    check("tower placed inside the limit", tower is not None, json.dumps(tower))
    page.click("#btn-build-tower")
    page.wait_for_timeout(300)
    page.click("#btn-next-wave")
    page.wait_for_timeout(5000)
    n = page.evaluate("() => window.__castle.enemies.length")
    check("wave 1 spawns 3 enemies", n == 3, f"enemies={n}")
    if tower:
        page.evaluate(
            """([tx, tz]) => {
              const e = window.__castle.enemies[0];
              e.group.position.set(tx + 12, e.group.position.y, tz);
            }""",
            [tower["x"], tower["z"]],
        )
        fired = False
        kills_before = page.evaluate("() => window.__castle.state.kills")
        deadline = time.time() + 90
        while time.time() < deadline:
            page.wait_for_timeout(3000)
            arrows = page.evaluate("() => window.__castle.arrows.length")
            kills = page.evaluate("() => window.__castle.state.kills")
            if arrows > 0 or kills > kills_before:
                fired = True
                print(f"TOWER FIRED: arrows={arrows} kills={kills} (was {kills_before})")
                break
        check("player-built tower shoots", fired)

    # The King is still standing by the keep.
    king = page.evaluate("() => window.__castle.world.king()")
    print("KING:", json.dumps(king))
    check("king still by the keep", abs(king[0]) < 30 and abs(king[2]) < 30, json.dumps(king))
    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs) if failed_reqs else "none")
check("no console/page errors", not real_errors)
check("no failed requests", not failed_reqs)
ok = all(c[1] for c in checks)
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
