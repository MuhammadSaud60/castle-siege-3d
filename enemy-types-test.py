"""Enemy types test: wave 1 is foot soldiers only; wave 2 mixes in cavalry
(a rider on a horse, faster and tougher); wave 3 adds brutes (big
armoured fighters, slow, very tough, heavy hits). All types stop and
attack buildings like foot soldiers. Also re-verifies the full gameplay
loop: build wall/house/farm/tower, wave 1 spawns 3 enemies, the
player-built tower shoots and kills."""
import json
import sys
from collections import Counter
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
        page.wait_for_timeout(1000)

    def wave_comp():
        return page.evaluate("""() => window.__castle.enemies.map(e => ({
          type: e.type, hp: e.hp, speed: e.speed, damage: e.damage, reach: e.reach,
          x: +e.group.position.x.toFixed(1), z: +e.group.position.z.toFixed(1) }))""")

    def start_wave(n):
        # Test-only shortcut through the debug handle: set the wave number
        # directly, then press the wave button (it only works when no wave
        # is active). This avoids waiting through earlier waves in real time.
        page.evaluate(
            """(n) => { const s = window.__castle.state; s.wave = n - 1; s.waveActive = false; }""",
            n,
        )
        page.click("#btn-next-wave")
        page.wait_for_timeout(2500)
        comp = wave_comp()
        print(f"WAVE {n}:", Counter([e["type"] for e in comp]), json.dumps(comp))
        return comp

    # --- gameplay still works: build everything, then wave 1 --------------
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

    # --- wave 1: soldiers only ----------------------------------------------
    w1 = start_wave(1)
    check("wave 1 spawns 3 enemies", len(w1) == 3, json.dumps(w1))
    check("wave 1 is soldiers only", all(e["type"] == "soldier" for e in w1))
    check("soldier stats", all(e["hp"] == 2 and e["damage"] == 5 for e in w1),
          json.dumps([(e["hp"], e["speed"], e["damage"]) for e in w1]))

    # The player-built tower kills one (teleport an enemy into range, as in king-test).
    tower_pos = page.evaluate("() => ({ x: window.__castle.towers[0].pos.x, z: window.__castle.towers[0].pos.z })")
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
    check("player-built tower kills an enemy", killed,
          f"kills={page.evaluate('() => window.__castle.state.kills')}")

    # Clear the rest of wave 1 so wave 2 can start (test-only: remove them).
    page.evaluate("() => { const w = window.__castle; w.enemies.slice().forEach(e => { w.state.kills += 1; const i = w.enemies.indexOf(e); if (i >= 0) { w.enemies[i].group.removeFromParent(); w.enemies.splice(i, 1); } }); }")
    page.wait_for_timeout(1500)
    check("wave 1 cleared", page.evaluate("() => window.__castle.state.waveActive") is False)

    # --- wave 2: cavalry joins ----------------------------------------------
    w2 = start_wave(2)
    c2 = Counter([e["type"] for e in w2])
    check("wave 2 spawns 5 enemies", len(w2) == 5, json.dumps(w2))
    check("wave 2 has 1 cavalry", c2.get("cavalry", 0) == 1, json.dumps(dict(c2)))
    check("wave 2 rest are soldiers", c2.get("soldier", 0) == 4, json.dumps(dict(c2)))
    cav = [e for e in w2 if e["type"] == "cavalry"][0]
    check("cavalry is faster (4.2)", abs(cav["speed"] - 4.2) < 0.01, json.dumps(cav))
    check("cavalry is tougher (4 HP, 15 damage)", cav["hp"] == 4 and cav["damage"] == 15, json.dumps(cav))

    # Cavalry close-up screenshot.
    set_cam(cav["x"], 2, cav["z"], cav["x"] + 12, 7, cav["z"] + 12)
    page.screenshot(path=SHOT_DIR + "cavalry-close.png")
    print("SHOT: cavalry-close.png")

    # Cavalry moves faster than soldiers: sample positions over time.
    p0 = page.evaluate("() => window.__castle.enemies.filter(e => e.type === 'cavalry').map(e => [e.group.position.x, e.group.position.z])")
    s0 = page.evaluate("() => window.__castle.enemies.filter(e => e.type === 'soldier').map(e => [e.group.position.x, e.group.position.z])")
    page.wait_for_timeout(5000)
    p1 = page.evaluate("() => window.__castle.enemies.filter(e => e.type === 'cavalry').map(e => [e.group.position.x, e.group.position.z])")
    s1 = page.evaluate("() => window.__castle.enemies.filter(e => e.type === 'soldier').map(e => [e.group.position.x, e.group.position.z])")
    import math
    cav_moved = math.hypot(p1[0][0] - p0[0][0], p1[0][1] - p0[0][1]) if p0 and p1 else 0
    sol_moved = max([math.hypot(a[0] - b[0], a[1] - b[1]) for a, b in zip(s1, s0)] or [0])
    print(f"MOVED in 5s: cavalry {cav_moved:.1f}, fastest soldier {sol_moved:.1f}")
    check("cavalry outruns soldiers", cav_moved > sol_moved * 1.3,
          f"cavalry {cav_moved:.1f} vs soldier {sol_moved:.1f}")

    # Clear wave 2 the same way.
    page.evaluate("() => { const w = window.__castle; w.enemies.slice().forEach(e => { w.state.kills += 1; const i = w.enemies.indexOf(e); if (i >= 0) { w.enemies[i].group.removeFromParent(); w.enemies.splice(i, 1); } }); }")
    page.wait_for_timeout(1500)

    # --- wave 3: brutes join --------------------------------------------------
    w3 = start_wave(3)
    c3 = Counter([e["type"] for e in w3])
    check("wave 3 spawns 7 enemies", len(w3) == 7, json.dumps(w3))
    check("wave 3 has 2 cavalry", c3.get("cavalry", 0) == 2, json.dumps(dict(c3)))
    check("wave 3 has 1 brute", c3.get("brute", 0) == 1, json.dumps(dict(c3)))
    check("wave 3 rest are soldiers", c3.get("soldier", 0) == 4, json.dumps(dict(c3)))
    br = [e for e in w3 if e["type"] == "brute"][0]
    check("brute is slow (1.9)", abs(br["speed"] - 1.9) < 0.01, json.dumps(br))
    check("brute is very tough (6 HP, 20 damage)", br["hp"] == 6 and br["damage"] == 20, json.dumps(br))

    # Brute close-up screenshot.
    set_cam(br["x"], 2, br["z"], br["x"] + 12, 7, br["z"] + 12)
    page.screenshot(path=SHOT_DIR + "brute-close.png")
    print("SHOT: brute-close.png")
    # Wide shot of the mixed wave.
    set_cam(0, 8, 0, 90, 70, 90)
    page.screenshot(path=SHOT_DIR + "wave3-mixed.png")
    print("SHOT: wave3-mixed.png")

    # --- all types stop and attack buildings ----------------------------------
    # Teleport one cavalry and the brute to just outside a wall (1.5 units
    # from its centre, on the keep side, offset along the wall axis so they
    # do not overlap), then poll: with 15 + 20 damage per swing the 50 HP
    # wall can fall fast, so record whether they EVER targeted it and the
    # lowest wall HP seen.
    wall = page.evaluate("() => window.__castle.built.find(b => b.kind === 'wall')")
    print("WALL:", wall)
    page.evaluate(
        """(w) => {
          const c = window.__castle;
          const ax = Math.cos(w.angle), az = -Math.sin(w.angle); // wall axis
          const kl = Math.hypot(w.x, w.z) || 1;
          const kx = -w.x / kl, kz = -w.z / kl; // toward the keep
          const cav = c.enemies.find(e => e.type === 'cavalry');
          const br = c.enemies.find(e => e.type === 'brute');
          if (cav) { cav.group.position.set(w.x + kx * 1.5 + ax, 0, w.z + kz * 1.5 + az); cav.target = null; }
          if (br) { br.group.position.set(w.x + kx * 1.5 - ax, 0, w.z + kz * 1.5 - az); br.target = null; }
        }""",
        wall,
    )
    hp_before = page.evaluate("() => window.__castle.built.find(b => b.kind === 'wall').hp")
    seen_cav = seen_brute = False
    hp_low = hp_before
    for _ in range(12):
        page.wait_for_timeout(1000)
        atk = page.evaluate("""() => window.__castle.enemies
          .filter(e => e.type !== 'soldier')
          .map(e => ({ type: e.type, target: e.target ? (e.target === 'keep' ? 'keep' : e.target.kind) : null }))""")
        if any(a["type"] == "cavalry" and a["target"] == "wall" for a in atk):
            seen_cav = True
        if any(a["type"] == "brute" and a["target"] == "wall" for a in atk):
            seen_brute = True
        hp_now = page.evaluate("() => { const b = window.__castle.built.find(b => b.kind === 'wall'); return b ? b.hp : 0; }")
        hp_low = min(hp_low, hp_now)
        if seen_cav and seen_brute and hp_low < hp_before:
            break
    print(f"WALL HP: {hp_before} -> lowest seen {hp_low}; cav attacked: {seen_cav}, brute attacked: {seen_brute}")
    check("cavalry stops at the wall and attacks it", seen_cav)
    check("brute stops at the wall and attacks it", seen_brute)
    check("wall HP drops from the attacks", hp_low < hp_before, f"{hp_before} -> {hp_low}")

    # The King is still standing by the keep and was never targeted.
    king = page.evaluate("() => window.__castle.world.king()")
    check("king still by the keep", abs(king[0] - 7.5) < 0.01 and abs(king[2] - 7.5) < 0.01, json.dumps(king))
    check("no enemy targets the King",
          page.evaluate("() => window.__castle.enemies.every(e => e.target !== 'king')"))

    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs) if failed_reqs else "none")
check("no console/page errors", not real_errors)
check("no failed requests", not failed_reqs)
ok = all(c[1] for c in checks)
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
