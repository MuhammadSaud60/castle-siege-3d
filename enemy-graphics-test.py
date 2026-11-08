"""Enemy graphics test: the three enemy types were rebuilt with much more
detail (proportions, faces/helmets, trim, emblems, weapons, a real horse,
a menacing brute). Visuals only: speeds, HP, damage, wave mix, attack
behaviour and king movement must be EXACTLY as before. Also re-verifies
the full gameplay loop: build wall/house/farm/tower, wave 1 spawns 3
soldiers, the player-built tower shoots and kills, all types stop and
attack buildings, and the King still walks when ordered."""
import json
import math
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

    def front_cam(e, dist=11, h=7):
        # Camera on the keep side, looking at the enemy's front (enemies
        # walk toward the keep, so their front faces the origin).
        r = math.hypot(e["x"], e["z"]) or 1
        ux, uz = e["x"] / r, e["z"] / r
        set_cam(e["x"], 2.2, e["z"], e["x"] - ux * dist, h, e["z"] - uz * dist)

    def wave_comp():
        return page.evaluate("""() => window.__castle.enemies.map(e => ({
          type: e.type, hp: e.hp, speed: e.speed, damage: e.damage, reach: e.reach,
          x: +e.group.position.x.toFixed(1), z: +e.group.position.z.toFixed(1) }))""")

    def mesh_count(i):
        return page.evaluate(
            """(i) => { let n = 0; window.__castle.enemies[i].group.traverse(o => { if (o.isMesh) n++; }); return n; }""",
            i,
        )

    def start_wave(n):
        page.evaluate(
            """(n) => { const s = window.__castle.state; s.wave = n - 1; s.waveActive = false; }""",
            n,
        )
        page.click("#btn-next-wave")
        page.wait_for_timeout(2500)
        comp = wave_comp()
        print(f"WAVE {n}:", Counter([e["type"] for e in comp]), json.dumps(comp))
        return comp

    def clear_wave():
        page.evaluate("() => { const w = window.__castle; w.enemies.slice().forEach(e => { w.state.kills += 1; const i = w.enemies.indexOf(e); if (i >= 0) { w.enemies[i].group.removeFromParent(); w.enemies.splice(i, 1); } }); }")
        page.wait_for_timeout(1500)

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

    # --- wave 1: soldiers only, stats unchanged ----------------------------
    w1 = start_wave(1)
    check("wave 1 spawns 3 enemies", len(w1) == 3, json.dumps(w1))
    check("wave 1 is soldiers only", all(e["type"] == "soldier" for e in w1))
    check("soldier stats unchanged", all(e["hp"] == 2 and e["damage"] == 5 and e["reach"] == 0 for e in w1),
          json.dumps([(e["hp"], e["speed"], e["damage"]) for e in w1]))
    # Detail level: the old soldier was ~15 meshes; the new one must carry
    # visibly more geometry (tapered torso, skirt, pads, tabard, shield
    # emblem, weapon details, helmet crest, eyes).
    n_soldier = mesh_count(0)
    print("SOLDIER meshes:", n_soldier)
    check("soldier is more detailed than before", n_soldier >= 25, f"meshes={n_soldier}")
    front_cam(w1[0])
    page.screenshot(path=SHOT_DIR + "soldier-close-v2.png")
    print("SHOT: soldier-close-v2.png")

    # The player-built tower kills one (teleport an enemy into range).
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
    clear_wave()
    check("wave 1 cleared", page.evaluate("() => window.__castle.state.waveActive") is False)

    # --- wave 2: cavalry joins, stats unchanged ----------------------------
    w2 = start_wave(2)
    c2 = Counter([e["type"] for e in w2])
    check("wave 2 spawns 5 enemies", len(w2) == 5, json.dumps(w2))
    check("wave 2 has 1 cavalry", c2.get("cavalry", 0) == 1, json.dumps(dict(c2)))
    cav = [e for e in w2 if e["type"] == "cavalry"][0]
    check("cavalry stats unchanged", cav["hp"] == 4 and cav["damage"] == 15 and abs(cav["speed"] - 4.2) < 0.01, json.dumps(cav))
    cav_idx = [i for i, e in enumerate(w2) if e["type"] == "cavalry"][0]
    n_cav = mesh_count(cav_idx)
    print("CAVALRY meshes:", n_cav)
    check("cavalry is more detailed than before", n_cav >= 35, f"meshes={n_cav}")
    front_cam(cav)
    page.screenshot(path=SHOT_DIR + "cavalry-close-v2.png")
    print("SHOT: cavalry-close-v2.png")
    clear_wave()

    # --- wave 3: brutes join, stats unchanged ------------------------------
    w3 = start_wave(3)
    c3 = Counter([e["type"] for e in w3])
    check("wave 3 spawns 7 enemies", len(w3) == 7, json.dumps(w3))
    check("wave 3 has 2 cavalry", c3.get("cavalry", 0) == 2, json.dumps(dict(c3)))
    check("wave 3 has 1 brute", c3.get("brute", 0) == 1, json.dumps(dict(c3)))
    br = [e for e in w3 if e["type"] == "brute"][0]
    check("brute stats unchanged", br["hp"] == 6 and br["damage"] == 20 and abs(br["speed"] - 1.9) < 0.01, json.dumps(br))
    br_idx = [i for i, e in enumerate(w3) if e["type"] == "brute"][0]
    n_brute = mesh_count(br_idx)
    print("BRUTE meshes:", n_brute)
    check("brute is more detailed than before", n_brute >= 30, f"meshes={n_brute}")
    front_cam(br)
    page.screenshot(path=SHOT_DIR + "brute-close-v2.png")
    print("SHOT: brute-close-v2.png")
    set_cam(0, 8, 0, 90, 70, 90)
    page.screenshot(path=SHOT_DIR + "wave3-mixed-v2.png")
    print("SHOT: wave3-mixed-v2.png")

    # --- all types still stop and attack buildings --------------------------
    wall = page.evaluate("() => window.__castle.built.find(b => b.kind === 'wall')")
    print("WALL:", wall)
    wall_hp_before = page.evaluate("() => window.__castle.built.find(b => b.kind === 'wall').hp")
    page.evaluate(
        """(w) => {
          const c = window.__castle;
          const ax = Math.cos(w.angle), az = -Math.sin(w.angle);
          const kl = Math.hypot(w.x, w.z) || 1;
          const kx = -w.x / kl, kz = -w.z / kl;
          const cav = c.enemies.find(e => e.type === 'cavalry');
          const br = c.enemies.find(e => e.type === 'brute');
          if (cav) { cav.group.position.set(w.x + kx * 1.5 + ax, 0, w.z + kz * 1.5 + az); cav.target = null; }
          if (br) { br.group.position.set(w.x + kx * 1.5 - ax, 0, w.z + kz * 1.5 - az); br.target = null; }
        }""",
        wall,
    )
    lowest_hp = wall_hp_before
    attacked = False
    for _ in range(30):
        page.wait_for_timeout(1000)
        hp = page.evaluate("() => { const b = window.__castle.built.find(b => b.kind === 'wall'); return b ? b.hp : 0; }")
        status = page.evaluate("() => document.getElementById('wave-status').textContent")
        if hp < lowest_hp:
            lowest_hp = hp
        if "attacking" in status:
            attacked = True
        if hp <= 0:
            attacked = True  # wall destroyed = it was attacked
            break
    print(f"WALL HP: {wall_hp_before} -> lowest seen {lowest_hp}, attacked={attacked}")
    check("enemies still stop and attack the wall", attacked and lowest_hp < wall_hp_before,
          f"hp {wall_hp_before}->{lowest_hp}")

    # --- the King still stands by the keep and walks when ordered ----------
    set_cam(7.5, 2, 7.5, 20, 10, 20)
    k = page.evaluate("() => window.__castle.world.king()")
    print("KING:", k)
    check("king still by the keep", abs(k[0] - 7.5) < 30 and abs(k[2] - 7.5) < 30, json.dumps(k))
    ks = page.evaluate("([x, y, z]) => window.__castle.screenPoint(x, y, z)", [k[0], k[1] + 2.0, k[2]])
    if ks and 0 <= ks[0] <= 1280 and 0 <= ks[1] <= 800:
        page.mouse.click(ks[0], ks[1])
        page.wait_for_timeout(500)
        sel = page.evaluate("() => window.__castle.kingMove()")
        check("king selects on click", sel["selected"], json.dumps(sel))
        # Order him to a distant ground point: wide camera so both the King
        # and the target are on screen (same as king-move-test.py).
        set_cam(25, 2, -5, 75, 65, 75)
        tx, tz = 40, -25
        ty = page.evaluate("([x, z]) => window.__castle.world.terrain(x, z)", [tx, tz])
        gs = page.evaluate("([x, y, z]) => window.__castle.screenPoint(x, y, z)", [tx, ty + 0.5, tz])
        if gs and 0 <= gs[0] <= 1280 and 0 <= gs[1] <= 800:
            page.mouse.click(gs[0], gs[1])
            page.wait_for_timeout(500)
            mv = page.evaluate("() => window.__castle.kingMove()")
            check("king accepts a move order", mv["moving"] and mv["target"] is not None, json.dumps(mv))
            check("move target is the clicked point",
                  abs(mv["target"]["x"] - tx) < 3 and abs(mv["target"]["z"] - tz) < 3, json.dumps(mv["target"]))
            # Headless game time runs much slower than wall clock, so poll
            # for up to 60s for him to cover ground toward the target.
            k0 = page.evaluate("() => window.__castle.world.king()")
            d0 = math.hypot(k0[0] - tx, k0[2] - tz)
            moved_ok = False
            for _ in range(60):
                page.wait_for_timeout(1000)
                k1 = page.evaluate("() => window.__castle.world.king()")
                if math.hypot(k1[0] - tx, k1[2] - tz) < d0 - 5:
                    moved_ok = True
                    break
            print(f"KING dist to target: {d0:.1f} -> {math.hypot(k1[0] - tx, k1[2] - tz):.1f}")
            check("king walks toward the ordered point", moved_ok, f"start dist={d0:.1f}")
        else:
            check("king accepts a move order", False, "ground point off screen")
    else:
        check("king selects on click", False, f"king off screen: {ks}")

    # --- errors ---------------------------------------------------------------
    print("ERRORS:", json.dumps(errors, indent=1) if errors else "none")
    print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")
    check("zero console/page errors", len(errors) == 0, json.dumps(errors))
    check("zero failed requests", len(failed_reqs) == 0, json.dumps(failed_reqs))

    failed = [c for c in checks if not c[1]]
    print(f"\n{len(checks) - len(failed)}/{len(checks)} checks passed")
    if failed:
        print("FAILED:", [c[0] for c in failed])
    browser.close()
    sys.exit(1 if failed else 0)
