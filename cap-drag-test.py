"""Focused follow-up to build-flow-test.py: the cap section of the main run
hit a flaky challenge-runner failure (soldier-1 solved fine twice, then one
run never reported success in 30s under a saturated SwiftShader renderer),
so the army stopped at 8/12 and the cap-refusal checks cascaded. This test
re-verifies just the cap and the wall drag, with the same retry-on-run-error
the Phase 1 test used ("Run is idempotent and free"), and captures the
runner error text on failure so a real bug can be told apart from starvation.

Flow: build one barracks via its challenge, train 12 soldiers (cap with one
barracks), verify a 13th training is refused with no panel, then wall drag
after a solve places 4 segments at 10 Stone each.
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

SNAP_JS = """() => {
  const s = window.__castle.state;
  const inc = window.__castle.incomePerTick();
  return { wood: s.wood, stone: s.stone, gold: s.gold, food: s.food,
    goldEarned: s.goldEarned, houses: s.houseCount, farms: s.farmCount,
    factories: s.factoryCount, barracks: s.barracksCount,
    built: window.__castle.built.length,
    builtKinds: window.__castle.built.map((b) => b.kind),
    soldiers: window.__castle.soldiers.length,
    placing: window.__castle.placing().kind,
    status: document.getElementById('wave-status').textContent, inc };
}"""

# Solve the open challenge, retrying the run itself up to 3 times when the
# runner reports an error (starved worker under SwiftShader). Returns the
# challenge id, whether it solved, and the runner error/summary for diagnosis.
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
      const summary = document.getElementById('challenge-summary').textContent;
      const err = document.getElementById('challenge-error').textContent;
      if (err || summary.indexOf('Run failed') === 0) { failed = true; break; }
      if (summary && document.querySelectorAll('#challenge-results .challenge-test').length >= 3
        && !document.getElementById('challenge-run').disabled) break;
      await sleep(100);
    }
    if (!failed) break; // tests genuinely failed, retrying will not help
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


def snap(page):
    return page.evaluate(SNAP_JS)


def count_ticks(before, after):
    rate = 3 + before["houses"]
    return round((after["goldEarned"] - before["goldEarned"]) / rate) if rate else 0


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
    page.wait_for_timeout(800)

    # Build one barracks through its challenge.
    page.click("#btn-build-barracks")
    page.wait_for_timeout(400)
    check("barracks: button opens challenge panel", page.evaluate(
        "() => !document.getElementById('challenge-overlay').classList.contains('hidden')"))
    solved = page.evaluate(SOLVE_RETRY_JS, REF)
    check("barracks: challenge solves", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(300)
    check("barracks: placement entered after solve",
          page.evaluate("() => window.__castle.placing().kind") == "barracks")
    pt = page.evaluate("() => window.__castle.screenPoint(8, 0, -40)")
    page.mouse.click(pt[0], pt[1])
    page.wait_for_timeout(400)
    check("barracks: barracks built", page.evaluate(
        "() => window.__castle.state.barracksCount") == 1)
    check("barracks: Train button enabled", page.evaluate(
        "() => !document.getElementById('btn-train-soldier').disabled"))

    # Train 12 soldiers to the cap (8 base + 4 per barracks).
    cap_loop = page.evaluate("""async (ref) => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const out = [];
      for (let i = 0; i < 12; i++) {
        document.getElementById('btn-train-soldier').click();
        await sleep(200);
        const cid = window.__castle.challengeId();
        if (!cid) { out.push({ i, error: 'no panel' }); break; }
        document.getElementById('challenge-editor').value = ref[cid];
        let ok = false;
        let lastErr = '';
        for (let attempt = 0; attempt < 3 && !ok; attempt++) {
          document.getElementById('challenge-run').click();
          const t0 = performance.now();
          let failed = false;
          while (performance.now() - t0 < 30000) {
            if (!document.getElementById('challenge-success').classList.contains('hidden')) { ok = true; break; }
            const err = document.getElementById('challenge-error').textContent;
            const summary = document.getElementById('challenge-summary').textContent;
            if (err || summary.indexOf('Run failed') === 0) { failed = true; lastErr = err || summary; break; }
            if (summary && document.querySelectorAll('#challenge-results .challenge-test').length >= 3
              && !document.getElementById('challenge-run').disabled) break;
            await sleep(100);
          }
          if (!failed) break;
          await sleep(300);
        }
        if (!ok) { out.push({ i, cid, error: 'solve failed', lastErr,
          summary: document.getElementById('challenge-summary').textContent });
          document.getElementById('challenge-close').click(); break; }
        document.getElementById('challenge-place-btn').click();
        await sleep(200);
        out.push({ i, cid, soldiers: window.__castle.soldiers.length,
          gold: window.__castle.state.gold });
      }
      return out;
    }""", REF)
    check("cap: 12 soldiers trained to the cap",
          len(cap_loop) == 12 and cap_loop[-1]["soldiers"] == 12, cap_loop)
    gold_after = snap(page)["gold"]
    print("GOLD AFTER 12 TRAINS:", gold_after, flush=True)

    # A 13th training is refused: no panel, full-strength status, no soldier.
    cap_refused = page.evaluate("""() => {
      document.getElementById('btn-train-soldier').click();
      return { panelOpen: !document.getElementById('challenge-overlay').classList.contains('hidden'),
        status: document.getElementById('wave-status').textContent,
        soldiers: window.__castle.soldiers.length };
    }""")
    page.wait_for_timeout(300)
    check("cap: training at the cap opens no panel", cap_refused["panelOpen"] is False, cap_refused)
    check("cap: training at the cap is refused", "full strength" in cap_refused["status"], cap_refused)
    check("cap: no soldier added at the cap", cap_refused["soldiers"] == 12, cap_refused)
    check("cap: army display shows 12/12",
          page.text_content("#btn-train-soldier .btn-label") == "20 Gold · 12/12",
          page.text_content("#btn-train-soldier .btn-label"))

    # Wall drag after a solve places 4 segments at 10 Stone each.
    page.evaluate("() => { window.__castle.state.stone = 500; }")
    page.click("#btn-build-wall")
    page.wait_for_timeout(400)
    solved = page.evaluate(SOLVE_RETRY_JS, REF)
    check("wall drag: challenge solves", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(300)
    check("wall drag: placement entered after solve",
          page.evaluate("() => window.__castle.placing().kind") == "wall")
    drag_pts = page.evaluate("""() => ({
      a: window.__castle.screenPoint(28, 0, 0),
      b: window.__castle.screenPoint(44, 0, 0) })""")
    print("DRAG PTS:", json.dumps(drag_pts), flush=True)
    before_drag = snap(page)
    walls_before = before_drag["builtKinds"].count("wall")
    page.mouse.move(drag_pts["a"][0], drag_pts["a"][1])
    page.wait_for_timeout(200)
    page.mouse.down()
    steps = 8
    for i in range(1, steps + 1):
        page.mouse.move(
            drag_pts["a"][0] + (drag_pts["b"][0] - drag_pts["a"][0]) * i / steps,
            drag_pts["a"][1] + (drag_pts["b"][1] - drag_pts["a"][1]) * i / steps,
        )
        page.wait_for_timeout(100)
    page.mouse.up()
    page.wait_for_timeout(400)
    after_drag = snap(page)
    walls_added = after_drag["builtKinds"].count("wall") - walls_before
    check("wall drag: 4 segments placed along the drag", walls_added == 4, walls_added)
    ticks = count_ticks(before_drag, after_drag)
    expected_stone = before_drag["stone"] - 10 * walls_added + ticks * before_drag["inc"]["stone"]
    check("wall drag: per-segment cost deducted (10 Stone each)",
          after_drag["stone"] == expected_stone,
          {"before": before_drag["stone"], "after": after_drag["stone"],
           "expected": expected_stone, "ticks": ticks})

    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none", flush=True)
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none", flush=True)
print("RESULT:", "PASS" if not failures and not real_errors and not failed_reqs else "FAIL", flush=True)
if failures:
    print("FAILURES:", json.dumps(failures, indent=1), flush=True)
sys.exit(0 if not failures and not real_errors and not failed_reqs else 1)
