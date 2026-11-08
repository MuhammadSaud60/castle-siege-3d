"""Retake the two weak screenshots from build-flow-test.py: the ghost shot
caught a frame from before the mouse move (SwiftShader renders ~2 FPS, so
400ms is less than one frame), and the soldier was tiny and half hidden
behind the HUD bar. This run waits 2s after each move/camera change so a
frame renders, and frames the soldier close up.
"""
import json
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []
failed_reqs = []
failures = []

REF = {
    "soldier-1": "function soldiersNeeded(enemies) { return Math.ceil(enemies / 2); }",
    "soldier-2": "function canHold(soldiers, enemies) { return soldiers * 2 >= enemies; }",
    "soldier-3": "function survivors(soldiers, losses) { let r = soldiers; for (const l of losses) r -= l; return Math.max(0, r); }",
    "barracks-1": "function strongestSoldier(soldiers) { if (soldiers.length === 0) return null; let best = soldiers[0]; for (const s of soldiers) if (s.strength > best.strength) best = s; return best.name; }",
    "barracks-2": "function totalStrength(soldiers) { return soldiers.reduce((t, s) => t + s.strength, 0); }",
    "barracks-3": "function readyForBattle(soldiers, minStrength) { return soldiers.filter((s) => s.strength >= minStrength).map((s) => s.name); }",
    "wall-1": "function stonesForLength(length) { return length * 3; }",
    "wall-2": "function stonesForWall(length, height) { return length * height; }",
    "wall-3": "function stoneLeft(stone, length) { return Math.max(0, stone - length * 3); }",
}

SOLVE_RETRY_JS = """async (ref) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const cid = window.__castle.challengeId();
  if (!cid || !ref[cid]) return { ok: false, cid, error: 'no reference for ' + cid };
  document.getElementById('challenge-editor').value = ref[cid];
  for (let attempt = 0; attempt < 3; attempt++) {
    document.getElementById('challenge-run').click();
    const t0 = performance.now();
    let failed = false;
    while (performance.now() - t0 < 30000) {
      if (!document.getElementById('challenge-success').classList.contains('hidden')) {
        return { ok: true, cid, attempts: attempt + 1 };
      }
      const err = document.getElementById('challenge-error').textContent;
      const summary = document.getElementById('challenge-summary').textContent;
      if (err || summary.indexOf('Run failed') === 0) { failed = true; break; }
      if (summary && document.querySelectorAll('#challenge-results .challenge-test').length >= 3
        && !document.getElementById('challenge-run').disabled) break;
      await sleep(100);
    }
    if (!failed) break;
    await sleep(300);
  }
  return { ok: false, cid,
    summary: document.getElementById('challenge-summary').textContent,
    error: document.getElementById('challenge-error').textContent };
}"""


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""), flush=True)
    if not cond:
        failures.append(name)


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 640, "height": 400})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(0, 2, 0); c.position.set(0, 110, 70); t.update();
      window.__castle.state.wood = 500;
      window.__castle.state.stone = 500;
      window.__castle.state.gold = 500;
    }""")
    page.wait_for_timeout(1000)

    # Ghost: solve the wall challenge, enter placement, hover the spot and
    # wait for a frame (or two) before shooting.
    page.click("#btn-build-wall")
    page.wait_for_timeout(400)
    solved = page.evaluate(SOLVE_RETRY_JS, REF)
    check("ghost retake: wall challenge solves", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(300)
    pt = page.evaluate("() => window.__castle.screenPoint(24, 0, -24)")
    page.mouse.move(pt[0], pt[1])
    page.wait_for_timeout(2000)
    ghost = page.evaluate("() => window.__castle.placing()")
    check("ghost retake: ghost visible, green, at the hovered spot",
          ghost["ghostVisible"] is True and ghost["ghostColor"] == "#7ec850", ghost)
    page.screenshot(path=SHOT_DIR + "build-ghost-after-solve.png")
    print("GHOST SHOT SAVED", flush=True)

    # Soldier: build a barracks, train one soldier, then frame the camera
    # close on the soldier and wait for a frame before shooting.
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    page.click("#btn-build-barracks")
    page.wait_for_timeout(400)
    solved = page.evaluate(SOLVE_RETRY_JS, REF)
    check("soldier retake: barracks challenge solves", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(300)
    pt = page.evaluate("() => window.__castle.screenPoint(8, 0, -40)")
    page.mouse.click(pt[0], pt[1])
    page.wait_for_timeout(400)
    check("soldier retake: barracks built",
          page.evaluate("() => window.__castle.state.barracksCount") == 1)
    page.click("#btn-train-soldier")
    page.wait_for_timeout(400)
    solved = page.evaluate(SOLVE_RETRY_JS, REF)
    check("soldier retake: soldier challenge solves", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(400)
    army = page.evaluate("() => window.__castle.army()")
    check("soldier retake: one soldier trained", army["count"] == 1, army)
    print("SOLDIER AT:", json.dumps(army["list"]), flush=True)
    page.evaluate("""() => {
      const s = window.__castle.army().list[0];
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(s.x, 2, s.z);
      c.position.set(s.x + 16, 13, s.z + 16);
      t.update();
    }""")
    page.wait_for_timeout(2000)
    page.screenshot(path=SHOT_DIR + "soldier-trained.png")
    print("SOLDIER SHOT SAVED", flush=True)

    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none", flush=True)
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none", flush=True)
print("RESULT:", "PASS" if not failures and not real_errors and not failed_reqs else "FAIL", flush=True)
if failures:
    print("FAILURES:", json.dumps(failures, indent=1), flush=True)
sys.exit(0 if not failures and not real_errors and not failed_reqs else 1)
