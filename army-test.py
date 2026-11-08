"""Army test: the King's soldiers (Change 3) plus re-checks of the
selection fix (Change 1) and the demolish tool (Change 2).

Soldiers: Train button costs 20 Gold, cap 8, HP 30, 1 damage per
1-second swing, speed 3.2, engage range 30. They sally out to enemies,
fight in melee, and walk back to their post by the keep when the wave
is over. Enemies fight back, so a soldier can be killed.
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

    def army():
        return page.evaluate("() => window.__castle.army()")

    def state():
        return page.evaluate("() => ({ gold: window.__castle.state.gold, kills: window.__castle.state.kills, wave: window.__castle.state.wave })")

    set_cam(0, 2, 0, 56, 42, 56)

    # --- Change 1 re-check: King selectable (ring), wall not --------------
    kp = page.evaluate("() => window.__castle.world.king()")
    kxy = screen(kp[0], kp[1] + 1.5, kp[2])
    page.mouse.click(kxy[0], kxy[1])
    page.wait_for_timeout(400)
    check("king selected, ring visible", page.evaluate("() => window.__castle.kingMove().selected") is True
          and page.evaluate("() => window.__castle.kingMove().ringVisible") is True)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    page.click("#btn-build-wall")
    page.wait_for_timeout(300)
    page.mouse.click(640, 620)
    page.wait_for_timeout(500)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    w = page.evaluate("() => window.__castle.built[0]")
    wxy = screen(w["x"], 2.0, w["z"])
    page.mouse.click(wxy[0], wxy[1])
    page.wait_for_timeout(400)
    check("clicking a wall selects nothing", page.evaluate("() => window.__castle.selected()") is None)

    # --- Change 2 re-check: demolish the wall ------------------------------
    page.click("#btn-remove")
    page.wait_for_timeout(300)
    page.mouse.click(wxy[0], wxy[1])
    page.wait_for_timeout(500)
    check("wall demolished", page.evaluate("() => window.__castle.built.length") == 0)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # --- Change 3: train soldiers ------------------------------------------
    check("train label starts 20 Gold, 0/8",
          page.inner_text("#btn-train-soldier .btn-label") == "20 Gold · 0/8",
          page.inner_text("#btn-train-soldier .btn-label"))
    page.click("#btn-train-soldier")
    page.wait_for_timeout(400)
    page.click("#btn-train-soldier")
    page.wait_for_timeout(400)
    a = army()
    check("two soldiers trained", a["count"] == 2, str(a))
    check("gold spent 40 (50 -> 10)", state()["gold"] == 10, str(state()))
    check("label shows 2/8", page.inner_text("#btn-train-soldier .btn-label") == "20 Gold · 2/8")
    check("soldiers stand by the keep", all((s["x"] ** 2 + s["z"] ** 2) ** 0.5 < 20 for s in a["list"]), str(a["list"]))
    page.screenshot(path=SHOT_DIR + "soldiers-at-keep.png")

    # Soldiers are not selectable and not demolishable.
    s0 = army()["list"][0]
    sxy = screen(s0["x"], 1.5, s0["z"])
    page.mouse.click(sxy[0], sxy[1])
    page.wait_for_timeout(400)
    check("clicking a soldier selects nothing", page.evaluate("() => window.__castle.selected()") is None)
    page.click("#btn-remove")
    page.wait_for_timeout(300)
    page.mouse.click(sxy[0], sxy[1])
    page.wait_for_timeout(400)
    check("clicking a soldier with remove armed removes nothing", army()["count"] == 2)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)

    # --- Wave 1: soldiers fight, no towers built, so any kill is theirs ----
    page.evaluate("() => { const s = window.__castle.state; s.wave = 0; s.waveActive = false; }")
    page.click("#btn-next-wave")
    page.wait_for_timeout(2500)
    # Teleport the wave-1 enemies closer so the fight starts quickly.
    page.evaluate("""() => {
      for (const e of window.__castle.enemies) {
        const a = Math.atan2(e.group.position.z, e.group.position.x);
        const x = Math.cos(a) * 35, z = Math.sin(a) * 35;
        e.group.position.set(x, window.__castle.world.terrain(x, z), z);
      }
    }""")
    page.wait_for_timeout(1000)
    page.screenshot(path=SHOT_DIR + "soldiers-fighting.png")
    kills_before = state()["kills"]
    engaged = False
    killed_by_soldiers = False
    for _ in range(40):
        page.wait_for_timeout(2000)
        a = army()
        if any(s["target"] for s in a["list"]):
            engaged = True
        if state()["kills"] > kills_before:
            killed_by_soldiers = True
            break
    check("soldiers engaged an enemy", engaged, str(army()["list"]))
    check("a soldier killed an enemy (no towers built)", killed_by_soldiers,
          f"kills {kills_before} -> {state()['kills']}")
    page.screenshot(path=SHOT_DIR + "soldiers-fighting.png")

    # --- Wave 3: a brute kills a soldier ------------------------------------
    page.evaluate("() => { const s = window.__castle.state; s.wave = 2; s.waveActive = false; s.gold = 500; }")
    page.click("#btn-next-wave")
    page.wait_for_timeout(2500)
    comp = page.evaluate("() => window.__castle.enemies.map(e => e.type)")
    print("WAVE 3 comp:", comp)
    check("wave 3 has a brute", "brute" in comp, str(comp))
    # Teleport the brute next to the first soldier.
    page.evaluate("""() => {
      const s = window.__castle.army().list[0];
      const b = window.__castle.enemies.find(e => e.type === 'brute');
      if (b) {
        const x = s.x + 2, z = s.z;
        b.group.position.set(x, window.__castle.world.terrain(x, z), z);
      }
    }""")
    hp_before = army()["list"][0]["hp"]
    soldier_died = False
    brute_hurt = False
    for _ in range(30):
        page.wait_for_timeout(2000)
        a = army()
        if a["count"] < 2:
            soldier_died = True
            break
        if a["list"] and a["list"][0]["hp"] < hp_before:
            brute_hurt = True  # the soldier took hits; keep watching for the kill
        b = page.evaluate("() => { const e = window.__castle.enemies.find(e => e.type === 'brute'); return e ? e.hp : null; }")
        if b is not None and b < 6:
            brute_hurt = True
    check("brute hurt the soldier (hp dropped)", brute_hurt or soldier_died,
          f"hp {hp_before} -> {army()['list']}")
    check("an enemy killed a soldier", soldier_died, f"army now {army()['count']}")
    page.screenshot(path=SHOT_DIR + "soldier-falls.png")

    # --- Army cap: train to 8, the 9th is refused ---------------------------
    for _ in range(10):
        page.click("#btn-train-soldier")
        page.wait_for_timeout(300)
    a = army()
    check("army capped at 8", a["count"] == 8, str(a))
    check("9th train refused, count stays 8", a["count"] == 8
          and "full strength" in page.inner_text("#wave-status"),
          page.inner_text("#wave-status"))

    # --- Soldiers return home once the wave is cleared ----------------------
    page.evaluate("() => { for (const e of [...window.__castle.enemies]) { const i = window.__castle.enemies.indexOf(e); window.__castle.enemies.splice(i, 1); } }")
    # (test shortcut: clear the field so the wave ends; the soldiers'
    #  own walk-home logic is what is being checked, not the kills.)
    page.wait_for_timeout(1000)
    homes = page.evaluate("""() => window.__castle.army().list.map(s => {
      const dx = s.x, dz = s.z;
      return Math.hypot(dx, dz);
    })""")
    print("soldier distances from keep right after clear:", homes)
    home_ok = False
    for _ in range(30):
        page.wait_for_timeout(2000)
        ds = page.evaluate("""() => {
          // distance of each soldier to its own post is not exposed;
          // use distance to the keep centre: posts sit on a ring at 16.
          return window.__castle.army().list.map(s => Math.hypot(s.x, s.z));
        }""")
        if ds and max(ds) < 20:
            home_ok = True
            break
    check("soldiers walked back to the keep after the wave", home_ok, f"distances {ds}")

    print("CONSOLE ERRORS:", errors)
    print("FAILED REQUESTS:", failed_reqs)
    bad = [c for c in checks if not c[1]]
    print(f"RESULT: {len(checks) - len(bad)}/{len(checks)} checks passed")
    browser.close()
    raise SystemExit(0 if not bad and not errors and not failed_reqs else 1)
