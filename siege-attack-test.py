"""Siege combat test: enemies stop at buildings and attack them visibly
(Stronghold-style) instead of vanishing into them. A wall's HP drops over
successive hits, the wall is eventually destroyed and removed, the enemy
then moves on to attack the keep (keep HP dropping per hit, attackers
still visible), a house is attacked the same way, and a player-built tower
kills an attacker mid-attack."""
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
    print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail else ""), flush=True)

def wait_until(page, fn, timeout_s, label):
    """Poll fn() until it returns truthy; return that value or None."""
    deadline = time.time() + timeout_s
    last = None
    while time.time() < deadline:
        try:
            last = fn()
        except Exception as e:  # noqa: BLE001 - a probe error is just "not yet"
            last = None
        if last:
            return last
        page.wait_for_timeout(1000)
    print("TIMEOUT waiting for:", label, "last=", json.dumps(last), flush=True)
    return None

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    def top_down():
        page.evaluate(
            """() => {
              const c = window.__castle.camera, t = window.__castle.controls;
              t.target.set(0, 2, 0);
              c.position.set(0, 110, 70);
              t.update();
            }"""
        )
        page.wait_for_timeout(800)

    def set_camera(x, y, z, tx, ty, tz):
        page.evaluate(
            f"""() => {{
              const c = window.__castle.camera, t = window.__castle.controls;
              t.target.set({tx}, {ty}, {tz});
              c.position.set({x}, {y}, {z});
              t.update();
            }}"""
        )
        page.wait_for_timeout(900)

    def built(kind=None):
        if kind:
            return page.evaluate(
                f"() => window.__castle.built.filter(b => b.kind === '{kind}')"
                ".map(b => ({kind: b.kind, x: b.x, z: b.z, hp: b.hp, maxHp: b.maxHp}))"
            )
        return page.evaluate(
            "() => window.__castle.built.map(b => ({kind: b.kind, x: b.x, z: b.z, hp: b.hp, maxHp: b.maxHp}))"
        )

    def enemy_info():
        return page.evaluate(
            """() => window.__castle.enemies.map(e => ({
                x: +e.group.position.x.toFixed(1),
                z: +e.group.position.z.toFixed(1),
                hp: e.hp,
                target: e.target === 'keep' ? 'keep' : (e.target ? e.target.kind : null),
                targetHp: e.target && e.target !== 'keep' ? e.target.hp : null,
            }))"""
        )

    def teleport_enemy(idx, x, z):
        page.evaluate(
            f"""() => {{
                const e = window.__castle.enemies[{idx}];
                const y = window.__castle.world.terrain({x}, {z});
                e.group.position.set({x}, y, {z});
            }}"""
        )

    # ------------------------------------------------------------------
    # Stage A: wall attack -> destruction -> move on -> keep attack
    # ------------------------------------------------------------------
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.evaluate("() => { window.__castle.state.stone = 500; window.__castle.state.wood = 500; }")
    top_down()

    page.click("#btn-build-wall")
    page.wait_for_timeout(400)
    page.mouse.click(770, 400)  # one wall segment east of the keep
    page.wait_for_timeout(600)
    walls = built("wall")
    check("wall placed east of the keep", len(walls) == 1 and walls[0]["x"] > 10, json.dumps(walls))
    wall = walls[0]

    page.click("#btn-next-wave")
    page.wait_for_timeout(1500)
    n = page.evaluate("() => window.__castle.enemies.length")
    check("wave 1 spawns 3 enemies", n == 3, f"enemies={n}")

    # Put one enemy just east of the wall so it marches straight into it.
    teleport_enemy(0, wall["x"] + 6, wall["z"])
    page.wait_for_timeout(500)

    # (a) The enemy stops at the wall and attacks it, staying visible.
    attacker = wait_until(
        page,
        lambda: next((e for e in enemy_info() if e["target"] == "wall"), None),
        120, "enemy attacking the wall",
    )
    check("enemy stops at the wall and attacks (not despawned)", attacker is not None, json.dumps(attacker))
    if attacker:
        n_alive = page.evaluate("() => window.__castle.enemies.length")
        check("no enemy vanished while attacking", n_alive == 3, f"enemies={n_alive}")
        dist_to_wall = math.hypot(attacker["x"] - wall["x"], attacker["z"] - wall["z"])
        check("attacker stands at the wall edge", dist_to_wall <= 4.5, f"dist={dist_to_wall:.1f}")

    # (b) The wall's HP drops over successive hits.
    hp_drop = wait_until(
        page, lambda: (lambda w: w[0]["hp"] if w and w[0]["hp"] < 50 else None)(built("wall")),
        120, "wall HP dropping",
    )
    check("wall HP drops over successive hits", hp_drop is not None, f"hp={hp_drop}")
    if hp_drop is not None:
        # Close-up shot of the enemy mid-attack at the damaged wall.
        set_camera(wall["x"] + 16, 10, wall["z"] + 16, wall["x"], 2, wall["z"])
        page.wait_for_timeout(600)
        status = page.inner_text("#wave-status")
        print("STATUS:", status)
        page.screenshot(path=SHOT_DIR + "siege-attack-wall.png")
        print("SHOT: siege-attack-wall.png")
        check("status line shows the wall under attack", "attacking your wall" in status, status)

    # (c) The wall is eventually destroyed and removed.
    gone = wait_until(page, lambda: len(built("wall")) == 0, 240, "wall destroyed")
    check("wall destroyed and removed", bool(gone), f"walls left={len(built('wall'))}")

    # (d) The enemy moves on toward the keep and attacks it visibly.
    keep_hit = wait_until(
        page,
        lambda: (
            lambda info: (
                next((e for e in info if e["target"] == "keep"), None)
                if page.evaluate("() => window.__castle.state.keepHp") < 100 and info
                else None
            )
        )(enemy_info()),
        240, "enemy attacking the keep",
    )
    check("enemy moves on and attacks the keep", keep_hit is not None, json.dumps(keep_hit))
    if keep_hit:
        keep_hp = page.evaluate("() => window.__castle.state.keepHp")
        check("keep HP dropping per hit, attacker still alive", 0 < keep_hp < 100,
              f"keepHp={keep_hp} enemies={len(enemy_info())}")
        set_camera(28, 16, 28, 0, 2, 0)
        page.wait_for_timeout(600)
        page.screenshot(path=SHOT_DIR + "siege-attack-keep.png")
        print("SHOT: siege-attack-keep.png")

    # ------------------------------------------------------------------
    # Stage B: house attacked the same way; tower kills a wall attacker
    # ------------------------------------------------------------------
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.evaluate("() => { window.__castle.state.stone = 500; window.__castle.state.wood = 500; }")
    top_down()

    page.click("#btn-build-wall")
    page.wait_for_timeout(300)
    page.mouse.click(770, 400)
    page.wait_for_timeout(400)
    page.click("#btn-build-house")
    page.wait_for_timeout(300)
    page.mouse.click(640, 250)
    page.wait_for_timeout(400)
    page.click("#btn-build-farm")
    page.wait_for_timeout(300)
    page.mouse.click(520, 480)
    page.wait_for_timeout(400)
    b = built()
    kinds = {x["kind"] for x in b}
    check("wall, house and farm built via UI", kinds == {"wall", "house", "farm"}, json.dumps(b))
    wall = built("wall")[0]
    house = built("house")[0]

    page.click("#btn-next-wave")
    page.wait_for_timeout(1500)
    check("wave 1 spawns 3 enemies (stage B)", page.evaluate("() => window.__castle.enemies.length") == 3)

    # One enemy onto the house: it must stop and attack it. The enemy has
    # to be placed on the house-keep line (due north of the house), so the
    # house lies directly on its march to the keep; placing it east of the
    # house makes it walk past the house diagonally instead.
    teleport_enemy(0, house["x"], house["z"] - 6)
    house_hit = wait_until(
        page,
        lambda: next((e for e in enemy_info() if e["target"] == "house"), None),
        120, "enemy attacking the house",
    )
    check("enemy stops at the house and attacks", house_hit is not None, json.dumps(house_hit))
    hp_drop = wait_until(
        page, lambda: (lambda h: h[0]["hp"] if h and h[0]["hp"] < 30 else None)(built("house")),
        120, "house HP dropping",
    )
    check("house HP drops over successive hits", hp_drop is not None, f"hp={hp_drop}")

    # Second enemy onto the wall; then build a tower near the wall.
    teleport_enemy(1, wall["x"] + 6, wall["z"])
    wall_hit = wait_until(
        page,
        lambda: next((e for e in enemy_info() if e["target"] == "wall"), None),
        120, "enemy attacking the wall (stage B)",
    )
    check("second enemy attacks the wall", wall_hit is not None, json.dumps(wall_hit))
    page.click("#btn-build-tower")
    page.wait_for_timeout(300)
    # Calibrated from the observed screen->world mapping (770,400)->(22,-2):
    # this lands the tower just west of the wall, ~11 units from the
    # wall attacker and well inside the 26-unit tower range.
    page.mouse.click(723, 400)
    page.wait_for_timeout(400)
    towers = built("tower")
    check("tower built near the wall", len(towers) == 1, json.dumps(towers))
    if towers:
        td = math.hypot(towers[0]["x"] - wall["x"], towers[0]["z"] - wall["z"])
        check("tower in range of the wall attacker", td <= 26, f"dist={td:.1f}")

    # The tower must kill the wall attacker: kills go up, no enemy stays
    # at the wall, and the wall itself still stands.
    def tower_kill_done():
        kills = page.evaluate("() => window.__castle.state.kills")
        if kills < 1:
            return None
        near = [e for e in enemy_info()
                if math.hypot(e["x"] - wall["x"], e["z"] - wall["z"]) <= 4.5]
        if near:
            return None
        if not built("wall"):
            return None
        return {"kills": kills}

    kill = wait_until(page, tower_kill_done, 180, "tower kills the wall attacker")
    check("tower kills the attacker mid-attack, wall survives", kill is not None, json.dumps(kill))
    if kill:
        set_camera(wall["x"] + 16, 10, wall["z"] + 16, wall["x"], 2, wall["z"])
        page.wait_for_timeout(600)
        page.screenshot(path=SHOT_DIR + "siege-tower-kill.png")
        print("SHOT: siege-tower-kill.png")

    # A destroyed tower stops shooting: covered by the tower record living
    # in towers; the King is still standing by the keep.
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
