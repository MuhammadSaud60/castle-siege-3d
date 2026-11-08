"""Drag-to-build wall test: with the wall tool selected, a left-drag on the
ground draws a straight line of wall segments (Stronghold-style); a plain
click still places one segment; the camera must not orbit during the drag;
segments face the camera, as before."""
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

def ang_diff(a, b):
    d = (a - b + math.pi) % (2 * math.pi) - math.pi
    return abs(d)

def max_deviation(pts):
    """Max perpendicular distance of points from the best-fit line."""
    if len(pts) < 3:
        return 0.0
    xs = [p[0] for p in pts]
    zs = [p[1] for p in pts]
    mx = sum(xs) / len(xs)
    mz = sum(zs) / len(zs)
    sxx = sum((x - mx) ** 2 for x in xs)
    sxz = sum((x - mx) * (z - mz) for x, z in zip(xs, zs))
    szz = sum((z - mz) ** 2 for z in zs)
    # Principal axis of the point cloud.
    theta = 0.5 * math.atan2(2 * sxz, sxx - szz)
    nx, nz = -math.sin(theta), math.cos(theta)
    return max(abs((x - mx) * nx + (z - mz) * nz) for x, z in zip(xs, zs))

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)

    # Plenty of stone so a long line is affordable (10 per segment).
    page.evaluate("() => { window.__castle.state.stone = 500; }")
    # A high, mostly top-down view over the keep, so screen drags map to
    # clean ground lines.
    page.evaluate(
        """() => {
          const c = window.__castle.camera, t = window.__castle.controls;
          t.target.set(0, 2, 0);
          c.position.set(0, 110, 70);
          t.update();
        }"""
    )
    page.wait_for_timeout(1200)
    az_before = page.evaluate("() => window.__castle.controls.getAzimuthalAngle()")

    page.click("#btn-build-wall")
    page.wait_for_timeout(400)
    hint = page.inner_text("#hint")
    print("HINT:", hint)
    check("wall hint explains drag-to-build", "drag" in hint.lower())
    left_btn = page.evaluate("() => window.__castle.controls.mouseButtons.LEFT")
    check("left-drag unmapped while wall tool active", left_btn is None, f"LEFT={left_btn}")

    # Drag a horizontal line across the middle of the screen.
    page.mouse.move(440, 520)
    page.wait_for_timeout(300)
    page.mouse.down()
    for x in range(480, 841, 40):
        page.mouse.move(x, 520)
        page.wait_for_timeout(120)
    drag = page.evaluate("() => window.__castle.placing().wallDrag")
    print("MID-DRAG:", json.dumps(drag))
    check("drag preview active mid-drag", drag is not None and drag["segments"] >= 5,
          json.dumps(drag))
    page.mouse.up()
    page.wait_for_timeout(800)
    az_after = page.evaluate("() => window.__castle.controls.getAzimuthalAngle()")
    check("camera did not orbit during the drag", ang_diff(az_before, az_after) < 0.05,
          f"before={az_before:.3f} after={az_after:.3f}")

    walls = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall')")
    print("WALLS AFTER DRAG:", json.dumps(walls))
    pts = [(w["x"], w["z"]) for w in walls]
    check("drag placed a row of segments", len(walls) >= 5, f"count={len(walls)}")
    if len(walls) >= 3:
        dev = max_deviation(pts)
        check("dragged wall is straight", dev <= 3.0, f"max deviation={dev:.2f}")
        # Even spacing along the line (4 units, snapped to the 2-grid).
        dists = sorted(
            math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
            for i in range(len(pts) - 1)
        )
        print("SEGMENT SPACING:", [round(d, 1) for d in dists])
        check("segments evenly spaced", all(2.0 <= d <= 6.0 for d in dists),
              f"min={dists[0]:.1f} max={dists[-1]:.1f}")
        check("dragged walls face the camera",
              all(ang_diff(w["angle"], az_before) < 0.05 for w in walls),
              f"angles={[round(w['angle'], 2) for w in walls]} azimuth={az_before:.3f}")
    page.screenshot(path=SHOT_DIR + "wall-drag-line.png")
    print("SHOT: wall-drag-line.png")

    # A plain click still places exactly one segment.
    before = len(page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall')"))
    page.mouse.click(640, 300)
    page.wait_for_timeout(600)
    after = len(page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall')"))
    check("single click places one segment", after - before == 1, f"{before} -> {after}")
    page.screenshot(path=SHOT_DIR + "wall-drag-click.png")
    print("SHOT: wall-drag-click.png")

    # The King is still standing by the keep.
    king = page.evaluate("() => window.__castle.world.king()")
    print("KING:", json.dumps(king))
    check("king still by the keep", abs(king[0]) < 30 and abs(king[2]) < 30, json.dumps(king))

    # Wave 1 still spawns enemies.
    page.click("#btn-next-wave")
    page.wait_for_timeout(6000)
    n = page.evaluate("() => window.__castle.enemies.length")
    print("ENEMIES:", n)
    check("wave 1 spawns 3 enemies", n == 3, f"enemies={n}")
    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs) if failed_reqs else "none")
check("no console/page errors", not real_errors)
check("no failed requests", not failed_reqs)
ok = all(c[1] for c in checks)
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
