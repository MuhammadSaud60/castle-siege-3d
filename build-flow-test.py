"""Phase 2 build-flow test: build buttons and Train Soldier go through the
code challenge panel. For each of the 6 buildings: the button opens the
panel (no placement starts); closing deducts nothing and places nothing;
solving then "Place building" enters placement mode; placing deducts exactly
the building's cost and the building appears; cancelling placement after a
solve deducts nothing and the next click opens a fresh challenge; an
unaffordable click shows "Not enough resources" and opens no panel. Train
Soldier: disabled with no barracks; with a barracks, challenge then solve
trains a soldier for 20 Gold; at the cap, training is refused. Wall drag
after a solve places segments at 10 Stone each.

Income ticks keep running while the panel is closed, so every resource
assertion is tick-adjusted: the number of ticks in a measurement window is
read from goldEarned (or food for the house, whose placement changes the
gold rate), and the expected value is before - cost + ticks * tick income.

NOTE: the 3D scene renders continuously under SwiftShader, so CDP round
trips are slow. Multi-step panel flows run as ONE in-page async evaluate;
HUD buttons are clicked with real Playwright clicks, panel-internal buttons
with in-page .click() (the same pattern as challenge-test.py).
"""
import json
import sys
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []
failed_reqs = []
failures = []

# Reference solutions, kept in this test file only (copied from challenge-test.py).
REF = {
    "wall-1": "function stonesForLength(length) { return length * 3; }",
    "wall-2": "function stonesForWall(length, height) { return length * height; }",
    "wall-3": "function stoneLeft(stone, length) { return Math.max(0, stone - length * 3); }",
    "house-1": "function canHouse(family, rooms) { return rooms * 2 >= family; }",
    "house-2": "function taxIncome(houses, hasMarket) { return houses * 3 + (hasMarket ? 5 : 0); }",
    "house-3": "function needsRepair(age, damage) { return age > 20 || damage > 50; }",
    "farm-1": "function canPlant(water, sunny) { return water >= 4 && sunny; }",
    "farm-2": "function harvestYield(plots, rain) { return plots * 4 + (rain ? plots * 2 : 0); }",
    "farm-3": "function foodForWinter(food, people) { return food >= people * 5; }",
    "tower-1": "function totalArrows(waves) { let t = 0; for (const n of waves) t += n; return t * 3; }",
    "tower-2": "function countGoblins(types) { let c = 0; for (const t of types) if (t === 'goblin') c++; return c; }",
    "tower-3": "function enemiesInRange(range, distances) { let c = 0; for (const d of distances) if (d <= range) c++; return c; }",
    "factory-1": "function totalStone(outputs) { let t = 0; for (const o of outputs) t += o; return t; }",
    "factory-2": "function bestFactory(outputs) { if (outputs.length === 0) return 0; return Math.max(...outputs); }",
    "factory-3": "function factoriesAbove(outputs, min) { let c = 0; for (const o of outputs) if (o > min) c++; return c; }",
    "soldier-1": "function soldiersNeeded(enemies) { return Math.ceil(enemies / 2); }",
    "soldier-2": "function canHold(soldiers, enemies) { return soldiers * 2 >= enemies; }",
    "soldier-3": "function survivors(soldiers, losses) { let r = soldiers; for (const l of losses) r -= l; return Math.max(0, r); }",
    "barracks-1": "function strongestSoldier(soldiers) { if (soldiers.length === 0) return null; let best = soldiers[0]; for (const s of soldiers) if (s.strength > best.strength) best = s; return best.name; }",
    "barracks-2": "function totalStrength(soldiers) { return soldiers.reduce((t, s) => t + s.strength, 0); }",
    "barracks-3": "function readyForBattle(soldiers, minStrength) { return soldiers.filter((s) => s.strength >= minStrength).map((s) => s.name); }",
}

COSTS = {
    "wall": {"stone": 10},
    "house": {"wood": 20},
    "farm": {"wood": 15},
    "tower": {"stone": 30, "wood": 10},
    "factory": {"wood": 25, "stone": 15},
    "barracks": {"wood": 30, "stone": 20},
}
SPOTS = {
    # Far side of the keep (negative z): projects to the clear middle of
    # the screen at 640x400. The near-side spots projected onto the HUD
    # action bar, so a placement click hit a button instead of the ground.
    "wall": (24, -24), "house": (-24, -24), "farm": (0, -32),
    "tower": (32, -16), "factory": (-32, -16), "barracks": (8, -40),
}
KINDS = ["wall", "house", "farm", "tower", "factory", "barracks"]

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
    status: document.getElementById('wave-status').textContent,
    inc };
}"""

# Solve the currently open challenge with the reference solution for its id.
SOLVE_JS = """async (ref) => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const cid = window.__castle.challengeId();
  if (!cid || !ref[cid]) return { ok: false, cid, summary: 'no reference for ' + cid };
  document.getElementById('challenge-editor').value = ref[cid];
  document.getElementById('challenge-run').click();
  const t0 = performance.now();
  while (performance.now() - t0 < 30000) {
    if (!document.getElementById('challenge-success').classList.contains('hidden')) {
      return { ok: true, cid,
        summary: document.getElementById('challenge-summary').textContent,
        placeLabel: document.getElementById('challenge-place-btn').textContent,
        successText: document.getElementById('challenge-success-text').textContent };
    }
    const summary = document.getElementById('challenge-summary').textContent;
    if (summary && document.querySelectorAll('#challenge-results .challenge-test').length >= 3
      && !document.getElementById('challenge-run').disabled) break;
    await sleep(100);
  }
  return { ok: false, cid, summary: document.getElementById('challenge-summary').textContent };
}"""


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""), flush=True)
    if not cond:
        failures.append(name)


def snap(page):
    return page.evaluate(SNAP_JS)


def count_ticks(before, after, detector="gold"):
    """Ticks fired between two snapshots, from a resource whose tick income
    the window cannot change. goldEarned rises by the gold tick income;
    food rises by the food tick income."""
    if detector == "food":
        rate = 2 + before["farms"] * 2
        return round((after["food"] - before["food"]) / rate) if rate else 0
    rate = 3 + before["houses"]
    return round((after["goldEarned"] - before["goldEarned"]) / rate) if rate else 0


def expect_resources(before, after, cost, kind):
    """True when every cost resource moved by exactly -cost + ticks * rate.
    The factory's stone rate rises 1 -> 3 when it is placed, so a tick in
    that window may credit 1 or 3 stone; both are accepted there."""
    detector = "food" if kind == "house" else "gold"
    ticks = count_ticks(before, after, detector)
    for res, amount in cost.items():
        rate = before["inc"][res]
        expected = before[res] - amount + ticks * rate
        if kind == "factory" and res == "stone" and ticks > 0:
            alt = before[res] - amount + ticks * (1 + (before["factories"] + 1) * 2)
            if after[res] not in (expected, alt):
                return False, {"res": res, "before": before[res], "after": after[res],
                               "expected": expected, "alt": alt, "ticks": ticks}
        elif after[res] != expected:
            return False, {"res": res, "before": before[res], "after": after[res],
                           "expected": expected, "ticks": ticks}
    return True, {"ticks": ticks}


def check_no_cost_change(name, before, after):
    """No placement happened: every resource moved only by tick income."""
    ticks = count_ticks(before, after, "gold")
    bad = {}
    for res in ("wood", "stone", "gold", "food"):
        expected = before[res] + ticks * before["inc"][res]
        if after[res] != expected:
            bad[res] = (before[res], after[res], expected)
    check(name, not bad, bad if bad else f"ticks={ticks}")


def wait_tick(page, timeout=90):
    """Wait until an income tick fires, so the next tick is ~25s of real
    time away and a short measurement window cannot straddle one."""
    start = page.evaluate("() => window.__castle.state.goldEarned")
    t0 = time.time()
    while time.time() - t0 < timeout:
        cur = page.evaluate("() => window.__castle.state.goldEarned")
        if cur > start:
            return True
        page.wait_for_timeout(500)
    return False


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 640, "height": 400})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    # The start screen (Phase 3) covers the HUD until Start is clicked.
    page.click("#btn-start")
    page.wait_for_timeout(400)
    check("canvas present", page.evaluate("() => !!document.querySelector('#app canvas')"))
    check("openChallenge exposed", page.evaluate("() => typeof window.__castle.openChallenge === 'function'"))

    # Top-down camera, so screen points map cleanly to ground spots.
    page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(0, 2, 0);
      c.position.set(0, 110, 70);
      t.update();
    }""")
    page.wait_for_timeout(1000)
    screen = {}
    for kind, (x, z) in SPOTS.items():
        pt = page.evaluate("([x, z]) => window.__castle.screenPoint(x, 0, z)", [x, z])
        screen[kind] = pt
        el = page.evaluate(
            "([x, z]) => { const pt = window.__castle.screenPoint(x, 0, z);"
            " const el = document.elementFromPoint(pt[0], pt[1]);"
            " return el ? el.tagName : 'null'; }", [x, z])
        print("SCREEN", kind, (x, z), "->", pt, "element:", el, flush=True)
        check(f"screen point on screen for {kind}", pt and 0 <= pt[0] < 640 and 0 <= pt[1] < 340, pt)
        check(f"screen point hits the canvas for {kind}", el == "CANVAS", el)

    # 1. Train Soldier is disabled with no barracks: no panel opens.
    no_barr = page.evaluate("""() => {
      const btn = document.getElementById('btn-train-soldier');
      btn.click();
      return { disabled: btn.disabled,
        panelOpen: !document.getElementById('challenge-overlay').classList.contains('hidden') };
    }""")
    check("Train disabled with no barracks", no_barr["disabled"] is True, no_barr)
    check("Train click with no barracks opens no panel", no_barr["panelOpen"] is False, no_barr)

    # 2. Each building: open via button, close for free, solve, place.
    for kind in KINDS:
        before = snap(page)
        check(f"{kind}: challenge panel closed before button click", page.evaluate(
            "() => document.getElementById('challenge-overlay').classList.contains('hidden')"))
        page.click(f"#btn-build-{kind}")
        page.wait_for_timeout(400)
        panel_open = page.evaluate("() => !document.getElementById('challenge-overlay').classList.contains('hidden')")
        placing = snap(page)["placing"]
        check(f"{kind}: build button opens challenge panel", panel_open is True)
        check(f"{kind}: placement does not start on button click", placing is None, placing)
        check(f"{kind}: success button says Place building",
              page.text_content("#challenge-place-btn") == "Place building")
        if kind == "wall":
            page.screenshot(path=SHOT_DIR + "build-panel-from-button.png")

        # Closing the panel deducts nothing and places nothing.
        before_close = snap(page)
        page.click("#challenge-close")
        page.wait_for_timeout(300)
        after_close = snap(page)
        check(f"{kind}: panel closes", page.evaluate(
            "() => document.getElementById('challenge-overlay').classList.contains('hidden')"))
        check(f"{kind}: closing panel places nothing", after_close["built"] == before_close["built"])
        check_no_cost_change(f"{kind}: closing panel deducts nothing", before_close, after_close)

        # Solve, then "Place building" enters placement mode, deducting nothing yet.
        page.click(f"#btn-build-{kind}")
        page.wait_for_timeout(400)
        solved = page.evaluate(SOLVE_JS, REF)
        check(f"{kind}: correct code solves challenge", solved["ok"] is True, solved)
        before_place_btn = snap(page)
        placed_mode = page.evaluate("""() => {
          document.getElementById('challenge-place-btn').click();
          return { placing: window.__castle.placing().kind,
            closed: document.getElementById('challenge-overlay').classList.contains('hidden') };
        }""")
        check(f"{kind}: Place building closes the panel", placed_mode["closed"] is True, placed_mode)
        check(f"{kind}: Place building enters placement mode", placed_mode["placing"] == kind, placed_mode)
        after_place_btn = snap(page)
        check_no_cost_change(f"{kind}: solving deducts nothing", before_place_btn, after_place_btn)

        if kind == "wall":
            sx, sy = screen[kind]
            page.mouse.move(sx, sy)
            page.wait_for_timeout(400)
            page.screenshot(path=SHOT_DIR + "build-ghost-after-solve.png")
            ghost = page.evaluate("() => window.__castle.placing()")
            check("wall: ghost visible after solve", ghost["ghostVisible"] is True, ghost)

        # Place on the ground: exactly the cost is deducted, building appears.
        if kind == "factory":
            # The factory changes its own stone tick rate, so sync to just
            # after a tick first to keep the exact-deduction check clean.
            check("factory: tick sync before placement", wait_tick(page))
        before_place = snap(page)
        sx, sy = screen[kind]
        page.mouse.click(sx, sy)
        page.wait_for_timeout(400)
        after_place = snap(page)
        ok, detail = expect_resources(before_place, after_place, COSTS[kind], kind)
        check(f"{kind}: placing deducts exactly its cost", ok, detail)
        check(f"{kind}: building appears",
              after_place["built"] == before_place["built"] + 1
              and after_place["builtKinds"].count(kind) == before_place["builtKinds"].count(kind) + 1,
              {"before": before_place["built"], "after": after_place["built"]})
        # One solve buys one placement (Phase 4 fix): placing ends after
        # the building lands, and the next building needs a fresh challenge.
        check(f"{kind}: placement ends after placing (one solve, one building)",
              after_place["placing"] is None, after_place["placing"])
        # Top up first: after all six placements the fresh game's purse is
        # nearly empty, and a second barracks (30 Wood, 20 Stone) would be
        # refused as unaffordable instead of opening its challenge.
        page.evaluate("() => { window.__castle.state.wood = 200; window.__castle.state.stone = 200; window.__castle.state.gold = 200; }")
        page.click(f"#btn-build-{kind}")
        page.wait_for_timeout(400)
        check(f"{kind}: next click opens a fresh challenge",
              page.evaluate("() => !document.getElementById('challenge-overlay').classList.contains('hidden')"))
        if page.evaluate("() => !document.getElementById('challenge-overlay').classList.contains('hidden')"):
            page.click("#challenge-close")
            page.wait_for_timeout(200)

    # 3. Cancel placement after a solve: grant consumed, next click is a fresh challenge.
    page.evaluate("() => { window.__castle.state.wood = 200; window.__castle.state.stone = 200; window.__castle.state.gold = 200; }")
    page.click("#btn-build-house")
    page.wait_for_timeout(400)
    solved = page.evaluate(SOLVE_JS, REF)
    check("cancel flow: house challenge solves", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(300)
    check("cancel flow: placement entered after solve",
          page.evaluate("() => window.__castle.placing().kind") == "house")
    before_cancel = snap(page)
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    after_cancel = snap(page)
    check("cancel flow: Esc leaves placement mode", after_cancel["placing"] is None, after_cancel["placing"])
    check("cancel flow: cancelling places nothing", after_cancel["built"] == before_cancel["built"])
    check_no_cost_change("cancel flow: cancelling deducts nothing", before_cancel, after_cancel)
    page.click("#btn-build-house")
    page.wait_for_timeout(400)
    check("cancel flow: next click opens a fresh challenge",
          page.evaluate("() => !document.getElementById('challenge-overlay').classList.contains('hidden')")
          and page.evaluate("() => window.__castle.placing().kind") is None)
    page.click("#challenge-close")
    page.wait_for_timeout(200)

    # 4. Unaffordable: no panel, "Not enough resources" status.
    page.evaluate("() => { window.__castle.state.wood = 0; window.__castle.state.stone = 0; window.__castle.state.gold = 0; }")
    unaff = page.evaluate("""async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const out = [];
      for (const kind of ['wall', 'house', 'farm', 'tower', 'factory', 'barracks']) {
        document.getElementById('btn-build-' + kind).click();
        await sleep(200);
        out.push({ kind,
          panelOpen: !document.getElementById('challenge-overlay').classList.contains('hidden'),
          status: document.getElementById('wave-status').textContent,
          placing: window.__castle.placing().kind });
      }
      return out;
    }""")
    for info in unaff:
        check(f"{info['kind']}: unaffordable click opens no panel", info["panelOpen"] is False, info)
        check(f"{info['kind']}: unaffordable click shows Not enough resources",
              info["status"] == "Not enough resources", info)
        check(f"{info['kind']}: unaffordable click starts no placement", info["placing"] is None, info)
    page.evaluate("() => { window.__castle.state.wood = 500; window.__castle.state.stone = 500; window.__castle.state.gold = 500; }")

    # 5. Train Soldier with a barracks: gold gate, close for free, solve and train.
    page.evaluate("() => { window.__castle.state.gold = 10; }")
    page.click("#btn-train-soldier")
    page.wait_for_timeout(300)
    check("train: gold below 20 opens no panel", page.evaluate(
        "() => document.getElementById('challenge-overlay').classList.contains('hidden')"))
    check("train: gold below 20 shows Not enough resources",
          page.evaluate("() => document.getElementById('wave-status').textContent") == "Not enough resources")
    page.evaluate("() => { window.__castle.state.gold = 500; }")

    page.click("#btn-train-soldier")
    page.wait_for_timeout(400)
    check("train: button opens soldier challenge", page.evaluate(
        "() => !document.getElementById('challenge-overlay').classList.contains('hidden')"))
    check("train: success button says Train soldier",
          page.text_content("#challenge-place-btn") == "Train soldier")
    check("train: success text is about a soldier",
          "soldier" in page.text_content("#challenge-success-text"))
    before_close = snap(page)
    page.click("#challenge-close")
    page.wait_for_timeout(300)
    after_close = snap(page)
    check("train: closing panel trains no soldier", after_close["soldiers"] == before_close["soldiers"])
    check_no_cost_change("train: closing panel deducts nothing", before_close, after_close)

    page.click("#btn-train-soldier")
    page.wait_for_timeout(400)
    solved = page.evaluate(SOLVE_JS, REF)
    check("train: correct code solves soldier challenge", solved["ok"] is True, solved)
    check("train: solved soldier challenge offers Train soldier",
          solved.get("placeLabel") == "Train soldier", solved)
    before_train = snap(page)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(400)
    after_train = snap(page)
    check("train: solving trains a soldier", after_train["soldiers"] == before_train["soldiers"] + 1,
          {"before": before_train["soldiers"], "after": after_train["soldiers"]})
    ok, detail = expect_resources(before_train, after_train, {"gold": 20}, "soldier")
    check("train: training deducts exactly 20 Gold", ok, detail)
    check("train: army display shows 1 soldier", page.text_content("#btn-train-soldier .btn-label") == "20 Gold · 1/12",
          page.text_content("#btn-train-soldier .btn-label"))

    # Screenshot: a soldier trained after a challenge (3/4 view).
    page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(0, 2, 0);
      c.position.set(56, 42, 56);
      t.update();
    }""")
    page.wait_for_timeout(1200)
    page.screenshot(path=SHOT_DIR + "soldier-trained.png")

    # 6. At the cap (12 with one barracks), training is refused: no panel.
    cap_loop = page.evaluate("""async (ref) => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const out = [];
      for (let i = 0; i < 11; i++) {
        document.getElementById('btn-train-soldier').click();
        await sleep(200);
        const cid = window.__castle.challengeId();
        if (!cid) { out.push({ i, error: 'no panel' }); break; }
        document.getElementById('challenge-editor').value = ref[cid];
        document.getElementById('challenge-run').click();
        const t0 = performance.now();
        let ok = false;
        while (performance.now() - t0 < 30000) {
          if (!document.getElementById('challenge-success').classList.contains('hidden')) { ok = true; break; }
          await sleep(100);
        }
        if (!ok) { out.push({ i, cid, error: 'solve failed' }); document.getElementById('challenge-close').click(); break; }
        document.getElementById('challenge-place-btn').click();
        await sleep(200);
        out.push({ i, cid, soldiers: window.__castle.soldiers.length });
      }
      return out;
    }""", REF)
    check("cap: 11 more soldiers trained to the cap", len(cap_loop) == 11 and cap_loop[-1]["soldiers"] == 12, cap_loop)
    cap_refused = page.evaluate("""() => {
      document.getElementById('btn-train-soldier').click();
      return { panelOpen: !document.getElementById('challenge-overlay').classList.contains('hidden'),
        status: document.getElementById('wave-status').textContent,
        soldiers: window.__castle.soldiers.length };
    }""")
    page.wait_for_timeout(300)
    check("cap: training at the cap opens no panel", cap_refused["panelOpen"] is False, cap_refused)
    check("cap: training at the cap is refused",
          "full strength" in cap_refused["status"], cap_refused)
    check("cap: no soldier added at the cap", cap_refused["soldiers"] == 12, cap_refused)

    # 7. Wall drag after a solve places segments at 10 Stone each.
    page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(0, 2, 0);
      c.position.set(0, 110, 70);
      t.update();
      window.__castle.state.stone = 500;
    }""")
    page.wait_for_timeout(800)
    page.click("#btn-build-wall")
    page.wait_for_timeout(400)
    solved = page.evaluate(SOLVE_JS, REF)
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
    ok, detail = expect_resources(before_drag, after_drag, {"stone": 10 * walls_added}, "wall")
    check("wall drag: per-segment cost deducted (10 Stone each)", ok, detail)
    check("wall drag: one drag spends the grant (placement ends)",
          page.evaluate("() => window.__castle.placing().kind") is None)

    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none", flush=True)
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none", flush=True)
print("RESULT:", "PASS" if not failures and not real_errors and not failed_reqs else "FAIL", flush=True)
if failures:
    print("FAILURES:", json.dumps(failures, indent=1), flush=True)
sys.exit(0 if not failures and not real_errors and not failed_reqs else 1)
