"""King movement test: select the King, click a distant ground point, and
he walks there (Stronghold-style RTS control) with a destination marker;
Esc deselects him. Also re-verifies the King still idles by the keep and
that a drag still orbits the camera while he is selected."""
import json
import math
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
        page.wait_for_timeout(1000)

    def king_pos():
        return page.evaluate("() => window.__castle.world.king()")

    def screen_of(x, y, z):
        return page.evaluate(
            "([x, y, z]) => window.__castle.screenPoint(x, y, z)", [x, y, z])

    # --- select the King ---------------------------------------------------
    # Camera close on the keep, King at (7.5, 7.5) facing the default view.
    set_cam(7.5, 2, 7.5, 20, 10, 20)
    k = king_pos()
    print("KING START:", k)
    ks = screen_of(k[0], k[1] + 2.0, k[2])
    print("KING SCREEN:", ks)
    check("king projects on screen", ks is not None and 0 <= ks[0] <= 1280 and 0 <= ks[1] <= 800, json.dumps(ks))
    page.mouse.click(ks[0], ks[1])
    page.wait_for_timeout(500)
    sel = page.evaluate("() => window.__castle.kingMove()")
    print("AFTER KING CLICK:", sel)
    check("king is selected", sel["selected"] is True, json.dumps(sel))
    check("selection ring visible", sel["ringVisible"] is True)
    check("selected label says The King",
          page.evaluate("() => document.getElementById('selected-name').textContent") == "Selected: The King")

    # --- order him to a distant ground point -------------------------------
    # Wide camera so both the King and the target are on screen.
    set_cam(25, 2, -5, 75, 65, 75)
    # Target: (40, -25) on the open meadow, ~37 units away.
    tx, tz = 40, -25
    ty = page.evaluate("([x, z]) => window.__castle.world.terrain(x, z)", [tx, tz])
    ts = screen_of(tx, ty + 0.5, tz)
    print("TARGET SCREEN:", ts)
    check("target projects on screen", ts is not None and 0 <= ts[0] <= 1280 and 0 <= ts[1] <= 800, json.dumps(ts))
    start = king_pos()
    page.mouse.click(ts[0], ts[1])
    page.wait_for_timeout(500)
    mv = page.evaluate("() => window.__castle.kingMove()")
    print("AFTER GROUND CLICK:", mv)
    check("move order accepted", mv["moving"] is True and mv["target"] is not None, json.dumps(mv))
    check("target is the clicked point",
          abs(mv["target"]["x"] - tx) < 3 and abs(mv["target"]["z"] - tz) < 3, json.dumps(mv["target"]))
    check("destination marker visible", mv["markerVisible"] is True)
    check("king still selected after order", mv["selected"] is True)

    # --- he walks there -----------------------------------------------------
    page.screenshot(path=SHOT_DIR + "king-walking.png")
    print("SHOT: king-walking.png")
    positions = [king_pos()]
    for _ in range(10):
        page.wait_for_timeout(1000)
        positions.append(king_pos())
    print("KING PATH:", [(round(p[0], 1), round(p[2], 1)) for p in positions])
    d_start = math.hypot(start[0] - tx, start[2] - tz)
    d_end = math.hypot(positions[-1][0] - tx, positions[-1][2] - tz)
    check("king walked toward the target", d_end < d_start - 5,
          f"dist {d_start:.1f} -> {d_end:.1f}")
    check("king moved at a walking pace (not a teleport)",
          d_start - d_end < 60, f"covered {d_start - d_end:.1f} in ~10s")
    # Walk animation: his height must bob while walking.
    ys = [p[1] for p in positions]
    check("king bobs while walking", max(ys) - min(ys) > 0.02, json.dumps([round(y, 3) for y in ys]))

    # Wait until he arrives (37 units at 4 u/s is ~9s of game time, but
    # headless game time runs much slower than wall clock, so poll for
    # up to 150s instead of assuming real-time ticks).
    arrived = False
    for _ in range(150):
        page.wait_for_timeout(1000)
        mv = page.evaluate("() => window.__castle.kingMove()")
        if not mv["moving"]:
            arrived = True
            break
    end = king_pos()
    print("KING END:", end, "ARRIVED:", arrived)
    check("king arrives at the target", arrived, json.dumps(mv))
    check("king ends at the target",
          math.hypot(end[0] - tx, end[2] - tz) < 1.5,
          f"dist {math.hypot(end[0] - tx, end[2] - tz):.2f}")
    check("destination marker hides on arrival",
          page.evaluate("() => window.__castle.kingMove().markerVisible") is False)

    page.screenshot(path=SHOT_DIR + "king-arrived.png")
    print("SHOT: king-arrived.png")

    # --- a drag still orbits while he is selected ---------------------------
    az_before = page.evaluate("() => window.__castle.controls.getAzimuthalAngle()")
    page.mouse.move(640, 400)
    page.mouse.down()
    page.mouse.move(840, 400, steps=10)
    page.mouse.up()
    page.wait_for_timeout(500)
    az_after = page.evaluate("() => window.__castle.controls.getAzimuthalAngle()")
    check("drag still orbits while king selected", abs(az_after - az_before) > 0.1,
          f"az {az_before:.2f} -> {az_after:.2f}")
    check("king stays selected after orbit drag",
          page.evaluate("() => window.__castle.kingMove().selected") is True)

    # --- Esc deselects --------------------------------------------------------
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    check("Esc deselects the King",
          page.evaluate("() => window.__castle.kingMove().selected") is False)
    check("selection ring hides after Esc",
          page.evaluate("() => window.__castle.kingMove().ringVisible") is False)
    check("label back to default",
          page.evaluate("() => document.getElementById('selected-name').textContent") == "Click a building to select it")

    # --- clicking the King again also deselects -------------------------------
    k2 = king_pos()
    ks2 = screen_of(k2[0], k2[1] + 2.0, k2[2])
    page.mouse.click(ks2[0], ks2[1])
    page.wait_for_timeout(400)
    check("king selects again", page.evaluate("() => window.__castle.kingMove().selected") is True)
    page.mouse.click(ks2[0], ks2[1])
    page.wait_for_timeout(400)
    check("clicking the selected King deselects him",
          page.evaluate("() => window.__castle.kingMove().selected") is False)

    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs) if failed_reqs else "none")
check("no console/page errors", not real_errors)
check("no failed requests", not failed_reqs)
ok = all(c[1] for c in checks)
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
