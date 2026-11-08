"""Wall-angle test: a placed wall rotates to follow the camera's azimuth,
and the green placement ghost shows the same rotation before placing.
Places walls from three camera angles (SE, NE, NW) and checks the ghost
rotation and the placed wall's stored angle against the camera azimuth."""
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

    def azimuth():
        return page.evaluate("() => window.__castle.controls.getAzimuthalAngle()")

    # SE (azimuth ~+pi/4), NE (~+3pi/4), NW (~-3pi/4).
    views = [
        ("se", 56, 42, 56, "wall-angle-se.png"),
        ("ne", 56, 42, -56, "wall-angle-ne.png"),
        ("nw", -56, 42, -56, "wall-angle-nw.png"),
    ]
    for name, cx, cy, cz, shot in views:
        set_cam(0, 2, 0, cx, cy, cz)
        az = azimuth()
        print(f"{name.upper()} azimuth: {az:.3f} (expect ~{math.pi/4 if name=='se' else 3*math.pi/4 if name=='ne' else -3*math.pi/4:.3f})")
        page.click("#btn-build-wall")
        page.wait_for_timeout(300)
        # Hover a ground spot so the ghost appears.
        placed = False
        for (sx, sy) in [(640, 620), (700, 600), (580, 600), (640, 560)]:
            page.mouse.move(sx, sy)
            page.wait_for_timeout(500)
            ghost = page.evaluate("() => window.__castle.placing()")
            if ghost["ghostVisible"]:
                print(f"{name.upper()} ghost rotation: {ghost['ghostRotationY']:.3f} vs azimuth {az:.3f}")
                check(f"ghost follows camera ({name})",
                      ang_diff(ghost["ghostRotationY"], az) < 0.05,
                      f"ghost={ghost['ghostRotationY']:.3f} azimuth={az:.3f}")
                before = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall').length")
                page.mouse.click(sx, sy)
                page.wait_for_timeout(600)
                after = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall').length")
                if after > before:
                    placed = True
                    break
        check(f"wall placed from {name}", placed)
        if placed:
            wall = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall').slice(-1)[0]")
            print(f"{name.upper()} placed wall: {wall}")
            check(f"placed wall angle matches camera ({name})",
                  ang_diff(wall["angle"], az) < 0.05,
                  f"angle={wall['angle']:.3f} azimuth={az:.3f}")
        page.screenshot(path=SHOT_DIR + shot)
        print("SHOT:", shot)
        # Leave placing mode before the next angle.
        page.click("#btn-build-wall")
        page.wait_for_timeout(300)

    walls = page.evaluate("() => window.__castle.built.filter(b => b.kind === 'wall')")
    print("WALLS:", json.dumps(walls))
    check("three walls placed", len(walls) == 3, json.dumps(walls))
    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs) if failed_reqs else "none")
check("no console/page errors", not real_errors)
check("no failed requests", not failed_reqs)
ok = all(c[1] for c in checks)
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
