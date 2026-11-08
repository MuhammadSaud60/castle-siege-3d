"""King test: one King stands by the keep (gold crown, purple robe, red
cape, scepter), idle-bobs, and is not an enemy. Also re-verifies the full
gameplay loop after the gate removal: build wall/house/farm/tower, wave 1
spawns 3 enemies, the player-built tower shoots and kills."""
import json
import sys
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

    def set_cam(tx, ty, tz, cx, cy, cz):
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

    # --- the King ---------------------------------------------------------
    king = page.evaluate("() => window.__castle.world.king()")
    print("KING:", king)
    check("king stands by the keep", abs(king[0] - 7.5) < 0.01 and abs(king[2] - 7.5) < 0.01,
          json.dumps(king))
    check("king is not an enemy", page.evaluate("() => window.__castle.enemies.length") == 0)

    # Idle bob: sample his height over a few seconds, it must move.
    ys = []
    for _ in range(4):
        ys.append(page.evaluate("() => window.__castle.world.king()[1]"))
        page.wait_for_timeout(1500)
    print("KING Y SAMPLES:", ys)
    check("king idles (bobs)", max(ys) - min(ys) > 0.01, json.dumps(ys))

    # --- screenshots ------------------------------------------------------
    set_cam(7.5, 2.5, 7.5, 17, 7, 17)
    page.screenshot(path=SHOT_DIR + "king-close.png")
    print("SHOT: king-close.png")
    set_cam(0, 8, 0, 90, 70, 90)
    page.screenshot(path=SHOT_DIR + "king-wide.png")
    print("SHOT: king-wide.png")

    # --- gameplay still works ---------------------------------------------
    set_cam(0, 2, 0, 56, 42, 56)

    def click_build(btn, spots, kind, count_fn):
        before = page.evaluate(count_fn)
        for (x, y) in spots:
            page.click(btn)
            page.wait_for_timeout(300)
            page.mouse.click(x, y)
            page.wait_for_timeout(600)
            after = page.evaluate(count_fn)
            if after > before:
                print(f"BUILT {kind} at screen ({x},{y}): {before} -> {after}")
                return True
        print(f"FAILED to build {kind}")
        return False

    wall_ok = click_build("#btn-build-wall",
                          [(640, 620), (700, 600), (580, 600)], "wall",
                          "() => window.__castle.built.filter(b => b.kind === 'wall').length")
    check("wall built with button", wall_ok)
    house_ok = click_build("#btn-build-house",
                           [(430, 500), (400, 520), (470, 480)], "house",
                           "() => window.__castle.state.houseCount")
    check("house built with button", house_ok)
    farm_ok = click_build("#btn-build-farm",
                          [(850, 500), (880, 520), (820, 480)], "farm",
                          "() => window.__castle.state.farmCount")
    check("farm built with button", farm_ok)
    tower_ok = click_build("#btn-build-tower",
                           [(640, 300), (640, 260), (700, 300)], "tower",
                           "() => window.__castle.towers.length")
    check("tower built with button", tower_ok)

    page.click("#btn-next-wave")
    page.wait_for_timeout(3000)
    spawn = page.evaluate("""() => window.__castle.enemies.map(e => ({
      dist: +Math.hypot(e.group.position.x, e.group.position.z).toFixed(1),
      hp: e.hp, speed: e.speed }))""")
    print("SPAWN:", spawn)
    check("wave 1 spawns 3 enemies", len(spawn) == 3, json.dumps(spawn))

    tower_pos = page.evaluate("() => ({ x: window.__castle.towers[0].pos.x, z: window.__castle.towers[0].pos.z })")
    print("BUILT TOWER AT:", tower_pos)
    page.evaluate(
        """([tx, tz]) => {
          const e = window.__castle.enemies[0];
          e.group.position.set(tx + 12, 0, tz);
        }""",
        [tower_pos["x"], tower_pos["z"]],
    )
    killed = False
    for _ in range(90):
        page.wait_for_timeout(1000)
        if page.evaluate("() => window.__castle.state.kills") >= 1:
            killed = True
            break
    kills = page.evaluate("() => window.__castle.state.kills")
    print("KILLS:", kills)
    check("player-built tower kills an enemy", killed, f"kills={kills}")

    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs) if failed_reqs else "none")
check("no console/page errors", not real_errors)
check("no failed requests", not failed_reqs)
ok = all(c[1] for c in checks)
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
