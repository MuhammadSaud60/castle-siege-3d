"""Change 1 test: Factory + Barracks.

Factory: 25 Wood + 15 Stone, +2 Stone per tick, HP 40, chimney smoke.
Barracks: 30 Wood + 20 Stone, HP 50, training requires one, +4 army cap each.
Also: enemies attack the new buildings; demolish cleans up (factory stone
income stops, barracks cap drops and training disables again).
"""
import json
from playwright.sync_api import sync_playwright

URL = "http://localhost:4173/"
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

    def ev(expr):
        return page.evaluate(expr)

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
        page.wait_for_timeout(800)

    def screen(x, y, z):
        return page.evaluate("([x, y, z]) => window.__castle.screenPoint(x, y, z)", [x, y, z])

    def ground_click(wx, wz):
        y = ev(f"() => window.__castle.world.terrain({wx}, {wz})")
        xy = screen(wx, y + 0.5, wz)
        assert xy, f"no screen point for ({wx},{wz})"
        page.mouse.click(xy[0], xy[1])
        page.wait_for_timeout(400)

    def built_kinds():
        return ev("() => window.__castle.built.map(b => b.kind)")

    set_cam(0, 2, 0, 56, 42, 56)
    ev("() => { const s = window.__castle.state; s.wood = 500; s.stone = 500; s.gold = 200; }")

    # --- Training is blocked before any Barracks --------------------------
    train_disabled = ev("() => document.getElementById('btn-train-soldier').disabled")
    train_title = ev("() => document.getElementById('btn-train-soldier').title")
    check("train disabled with no Barracks", train_disabled is True, f"title={train_title!r}")
    # A disabled button ignores clicks: dispatch one via JS and confirm nothing trains.
    ev("() => document.getElementById('btn-train-soldier').click()")
    page.wait_for_timeout(400)
    check("no soldier trained without Barracks", ev("() => window.__castle.army().count") == 0)

    # --- Build a Factory at (30, 20) --------------------------------------
    chimneys0 = ev("() => window.__castle.fx.chimneys()")
    page.click("#btn-build-factory")
    page.wait_for_timeout(300)
    ground_click(30, 20)
    check("factory built", "factory" in built_kinds(), str(built_kinds()))
    check("factoryCount 1", ev("() => window.__castle.state.factoryCount") == 1)
    check("stone income +3/tick", ev("() => window.__castle.incomePerTick().stone") == 3)
    check("factory chimney smokes", ev("() => window.__castle.fx.chimneys()") == chimneys0 + 1,
          f"{chimneys0} -> {ev('() => window.__castle.fx.chimneys()')}")

    # --- Build a Barracks at (-30, 20) ------------------------------------
    page.click("#btn-build-barracks")
    page.wait_for_timeout(300)
    ground_click(-30, 20)
    check("barracks built", "barracks" in built_kinds(), str(built_kinds()))
    check("barracksCount 1", ev("() => window.__castle.state.barracksCount") == 1)
    check("army cap 12 with one Barracks", ev("() => window.__castle.army().cap") == 12)
    check("train enabled after Barracks", ev("() => document.getElementById('btn-train-soldier').disabled") is False)

    # --- Train a soldier ----------------------------------------------------
    gold0 = ev("() => window.__castle.state.gold")
    page.click("#btn-train-soldier")
    page.wait_for_timeout(500)
    check("soldier trained", ev("() => window.__castle.army().count") == 1)
    # 20 Gold spent; a 5s income tick (+3 Gold, no houses) may fire between reads.
    gold_after = ev("() => window.__castle.state.gold")
    check("gold -20 (allowing one income tick)", gold0 - gold_after in (17, 20),
          f"{gold0} -> {gold_after}")

    page.screenshot(path=SHOT_DIR + "new-buildings.png")

    # --- Wave 1 + enemies attack the new buildings -------------------------
    page.click("#btn-next-wave")
    page.wait_for_timeout(1500)
    check("wave 1 spawns 3 enemies", ev("() => window.__castle.enemies.length") == 3)
    # Teleport one enemy next to the factory, one next to the barracks.
    # Both go on the far side of their building from the keep, so their
    # walk to the keep crosses the building.
    ev("""() => {
      const es = window.__castle.enemies;
      const t = (x, z) => window.__castle.world.terrain(x, z);
      es[0].group.position.set(38, t(38, 20), 20);
      es[1].group.position.set(-39, t(-39, 20), 20);
      es[0].target = null; es[1].target = null;
    }""")
    factory_hp = None
    barracks_hp = None
    for _ in range(30):
        page.wait_for_timeout(2000)
        factory_hp = ev("() => (window.__castle.built.find(b => b.kind === 'factory') || {}).hp")
        barracks_hp = ev("() => (window.__castle.built.find(b => b.kind === 'barracks') || {}).hp")
        if factory_hp is not None and factory_hp < 40 and barracks_hp is not None and barracks_hp < 50:
            break
    check("enemy attacks factory (HP drops)", factory_hp is not None and factory_hp < 40, f"hp={factory_hp}")
    check("enemy attacks barracks (HP drops)", barracks_hp is not None and barracks_hp < 50, f"hp={barracks_hp}")
    page.screenshot(path=SHOT_DIR + "new-buildings-attacked.png")

    # --- Soldier fights ------------------------------------------------------
    # Teleport the third enemy next to the trained soldier and watch it fight.
    ev("""() => {
      const s = window.__castle.soldiers[0];
      const es = window.__castle.enemies;
      const e = es[es.length - 1];
      e.group.position.set(s.group.position.x + 4, s.group.position.y, s.group.position.z);
      e.target = null;
    }""")
    fought = False
    for _ in range(20):
        page.wait_for_timeout(2000)
        st = ev("() => { const s = window.__castle.soldiers[0]; const e = window.__castle.enemies[window.__castle.enemies.length - 1]; return s ? { t: !!s.target, ehp: e ? e.hp : null } : null; }")
        if st and (st["t"] or (st["ehp"] is not None and st["ehp"] < 2)):
            fought = True
            break
    check("soldier engages/fights enemy", fought, str(st))

    # --- Demolish the Factory ----------------------------------------------
    page.click("#btn-remove")
    page.wait_for_timeout(300)
    ground_click(30, 20)
    check("factory demolished", "factory" not in built_kinds(), str(built_kinds()))
    check("stone income back to +1", ev("() => window.__castle.incomePerTick().stone") == 1)
    check("factory chimney gone", ev("() => window.__castle.fx.chimneys()") == chimneys0,
          f"chimneys={ev('() => window.__castle.fx.chimneys()')}")

    # Make sure one soldier is alive for the "soldiers stay" check below
    # (the first one may have died fighting during the attack phase).
    if ev("() => window.__castle.army().count") == 0:
        ev("() => { window.__castle.state.gold += 50; }")
        page.click("#btn-train-soldier")
        page.wait_for_timeout(500)
    soldiers_before = ev("() => window.__castle.army().count")

    # --- Demolish the Barracks ----------------------------------------------
    ground_click(-30, 20)
    check("barracks demolished", "barracks" not in built_kinds(), str(built_kinds()))
    check("army cap back to 8", ev("() => window.__castle.army().cap") == 8)
    check("train disabled again", ev("() => document.getElementById('btn-train-soldier').disabled") is True)
    check("trained soldier stays", ev("() => window.__castle.army().count") == soldiers_before,
          f"before={soldiers_before} after={ev('() => window.__castle.army().count')}")
    page.keyboard.press("Escape")

    # --- Existing systems still work -----------------------------------------
    check("king still by the keep", ev("() => { const k = window.__castle.world.king(); return Math.hypot(k[0], k[2]) < 20; }"))
    check("no console errors", len(errors) == 0, "; ".join(errors[:5]))
    check("no failed requests", len(failed_reqs) == 0, "; ".join(failed_reqs[:5]))

    print(f"\n{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} checks passed")
    browser.close()
