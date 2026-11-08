"""Change 2 test: the bottom bar spans the complete width of the screen.

One full-width bar: buttons on the left, wave status in the middle,
hint on the right. The bar itself must not block camera orbit drags
(only the buttons take clicks). Checked at a wide and a narrow viewport.
"""
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
    for width, tag in [(1280, "wide"), (700, "narrow")]:
        page = browser.new_page(viewport={"width": width, "height": 800})
        page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
        page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)
        page.goto(URL, wait_until="domcontentloaded")
        page.wait_for_timeout(2500)

        def ev(expr):
            return page.evaluate(expr)

        bar = page.evaluate("""() => {
          const r = document.getElementById('actions').getBoundingClientRect();
          const cs = getComputedStyle(document.getElementById('actions'));
          const btn = document.getElementById('btn-build-wall');
          const bcs = getComputedStyle(btn);
          return { left: r.left, right: r.right, width: r.width,
                   vw: window.innerWidth, pointerEvents: cs.pointerEvents,
                   btnPointerEvents: bcs.pointerEvents };
        }""")
        check(f"[{tag}] bar spans full width", bar["left"] == 0 and abs(bar["right"] - bar["vw"]) < 1,
              f"left={bar['left']} right={bar['right']} vw={bar['vw']}")
        check(f"[{tag}] bar itself passes drags through", bar["pointerEvents"] == "none",
              bar["pointerEvents"])
        check(f"[{tag}] buttons still take clicks", bar["btnPointerEvents"] == "auto",
              bar["btnPointerEvents"])

        # Buttons stay clickable: arming the wall tool works from the bar.
        page.click("#btn-build-wall")
        page.wait_for_timeout(300)
        check(f"[{tag}] wall button clickable in bar",
              ev("() => window.__castle.placing().kind") == "wall")
        page.keyboard.press("Escape")
        page.wait_for_timeout(200)

        # Layout order: buttons left, status middle, hint right (on its row).
        order = page.evaluate("""() => {
          const btns = document.getElementById('action-buttons').getBoundingClientRect();
          const st = document.getElementById('wave-status').getBoundingClientRect();
          const hint = document.getElementById('hint').getBoundingClientRect();
          const hs = getComputedStyle(document.getElementById('hint'));
          return { btnsRight: btns.right, btnsBottom: btns.bottom,
                   stLeft: st.left, stRight: st.right, stTop: st.top,
                   hintLeft: hint.left, hintRight: hint.right,
                   hintVisible: hs.display !== 'none', vw: window.innerWidth };
        }""")
        if width == 1280:
            check(f"[{tag}] buttons left of status", order["btnsRight"] <= order["stLeft"] + 1,
                  f"btnsRight={order['btnsRight']} stLeft={order['stLeft']}")
            check(f"[{tag}] hint right-aligned on its row",
                  abs(order["hintRight"] - (order["vw"] - 14)) < 2,
                  f"hintRight={order['hintRight']} vw={order['vw']}")
        else:
            # Narrow: buttons wrap, status sits on its own row below them.
            check(f"[{tag}] status on its own row below buttons",
                  order["stTop"] >= order["btnsBottom"] - 1,
                  f"stTop={order['stTop']} btnsBottom={order['btnsBottom']}")
            check(f"[{tag}] hint hidden on narrow screen", not order["hintVisible"],
                  "display:none under 760px")

        # A drag starting on the bar's empty background orbits the camera.
        az0 = ev("() => window.__castle.controls.getAzimuthalAngle()")
        page.mouse.move(width / 2, 790)
        page.mouse.down()
        page.mouse.move(width / 2 + 200, 790, steps=10)
        page.mouse.up()
        page.wait_for_timeout(400)
        az1 = ev("() => window.__castle.controls.getAzimuthalAngle()")
        check(f"[{tag}] drag on bar background orbits camera", abs(az1 - az0) > 0.05,
              f"az {az0:.3f} -> {az1:.3f}")

        page.screenshot(path=SHOT_DIR + f"bottom-bar-{tag}.png")
        page.close()

    check("no console errors", len(errors) == 0, "; ".join(errors[:5]))
    check("no failed requests", len(failed_reqs) == 0, "; ".join(failed_reqs[:5]))
    print(f"\n{sum(1 for _, ok, _ in checks if ok)}/{len(checks)} checks passed")
    browser.close()
