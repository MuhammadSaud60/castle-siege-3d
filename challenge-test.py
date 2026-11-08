"""Phase 1 challenge-system test: panel for all 7 kinds, wrong/correct code,
infinite-loop timeout, and all 21 challenges verified against reference
solutions written ONLY in this test script (never shipped in the game).

NOTE: the 3D scene renders continuously under SwiftShader, so CDP round
trips are slow (seconds each). Every multi-step flow therefore runs as ONE
in-page async evaluate that polls with its own timers, instead of many
separate Playwright calls. Timings are measured in-page with performance.now().
"""
import json
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
errors = []
failed_reqs = []

# Reference solutions, kept in this test file only.
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

KIND_OF = {
    "wall-1": "wall", "wall-2": "wall", "wall-3": "wall",
    "house-1": "house", "house-2": "house", "house-3": "house",
    "farm-1": "farm", "farm-2": "farm", "farm-3": "farm",
    "tower-1": "tower", "tower-2": "tower", "tower-3": "tower",
    "factory-1": "factory", "factory-2": "factory", "factory-3": "factory",
    "barracks-1": "barracks", "barracks-2": "barracks", "barracks-3": "barracks",
    "soldier-1": "soldier", "soldier-2": "soldier", "soldier-3": "soldier",
}

failures = []

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
    check("canvas present", page.evaluate("() => !!document.querySelector('#app canvas')"))
    check("openChallenge exposed", page.evaluate("() => typeof window.__castle.openChallenge === 'function'"))

    # 1. Panel opens for every one of the 7 kinds (one in-page pass).
    kinds = page.evaluate("""async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const out = [];
      for (const kind of ['wall', 'house', 'farm', 'tower', 'factory', 'barracks', 'soldier']) {
        window.__solvedKind = null;
        window.__castle.openChallenge(kind, (k) => { window.__solvedKind = k; });
        await sleep(150);
        out.push({
          kind,
          visible: !document.getElementById('challenge-overlay').classList.contains('hidden'),
          id: window.__castle.challengeId(),
          title: document.getElementById('challenge-title').textContent,
          difficulty: document.getElementById('challenge-difficulty').textContent,
        });
        document.getElementById('challenge-close').click();
        await sleep(150);
        out[out.length - 1].closed = document.getElementById('challenge-overlay').classList.contains('hidden');
      }
      return out;
    }""")
    for info in kinds:
        check(f"panel opens for {info['kind']}", info["visible"] and bool(info["title"]), info)
        check(f"panel closes for {info['kind']}", info["closed"])
    check("barracks challenge is Hard", any(i["kind"] == "barracks" and i["difficulty"] == "Hard" for i in kinds), kinds)

    # Screenshots: easy wall challenge, hard barracks challenge.
    page.evaluate("""() => { window.__castle.openChallenge('wall', () => {}); }""")
    page.wait_for_timeout(400)
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/challenge-wall-easy.png")
    page.evaluate("""() => { document.getElementById('challenge-close').click(); window.__castle.openChallenge('barracks', () => {}); }""")
    page.wait_for_timeout(400)
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/challenge-barracks-hard.png")
    page.evaluate("""() => document.getElementById('challenge-close').click()""")

    # 2. Wrong code fails with per-test output shown; hint reveals text.
    wrong = page.evaluate("""async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      window.__castle.openChallenge('wall', (k) => { window.__solvedKind = k; });
      await sleep(150);
      const ed = document.getElementById('challenge-editor');
      const m = ed.value.match(/function\\s+(\\w+)/);
      const cid = window.__castle.challengeId();
      ed.value = 'function ' + m[1] + '() { return 999999; }';
      document.getElementById('challenge-run').click();
      const t0 = performance.now();
      while (performance.now() - t0 < 30000) {
        const rows = document.querySelectorAll('#challenge-results .challenge-test');
        if (rows.length >= 3) break;
        await sleep(100);
      }
      const out = {
        cid,
        ms: Math.round(performance.now() - t0),
        rows: Array.from(document.querySelectorAll('#challenge-results .challenge-test')).map((e) => e.textContent),
        successHidden: document.getElementById('challenge-success').classList.contains('hidden')
          && getComputedStyle(document.getElementById('challenge-success')).display === 'none',
      };
      document.getElementById('challenge-hint-btn').click();
      await sleep(100);
      out.hintShown = !document.getElementById('challenge-hint').classList.contains('hidden')
        && document.getElementById('challenge-hint').textContent.length > 5;
      return out;
    }""")
    check("wrong code shows 3 per-test rows", len(wrong["rows"]) == 3, wrong)
    check("wrong code rows show expected vs actual", all("Expected" in r for r in wrong["rows"]), wrong["rows"])
    check("wrong code shows no success state", wrong["successHidden"])
    check("hint reveals text", wrong["hintShown"])
    print("WRONG CODE RUN MS (in page):", wrong["ms"], flush=True)
    page.evaluate("() => { const b = document.querySelector('.challenge-box'); b.scrollTop = b.scrollHeight; }")
    page.wait_for_timeout(300)
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/challenge-failed.png")

    # 3. Correct code passes, Place building appears, onSolved fires.
    # Run first and screenshot the success state while the panel is open,
    # then click Place building in a second step.
    solved = page.evaluate("""async (ref) => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      const ed = document.getElementById('challenge-editor');
      ed.value = ref;
      document.getElementById('challenge-run').click();
      const t0 = performance.now();
      while (performance.now() - t0 < 30000) {
        if (!document.getElementById('challenge-success').classList.contains('hidden')) break;
        await sleep(100);
      }
      return {
        ms: Math.round(performance.now() - t0),
        success: !document.getElementById('challenge-success').classList.contains('hidden')
          && getComputedStyle(document.getElementById('challenge-success')).display !== 'none',
        summary: document.getElementById('challenge-summary').textContent,
      };
    }""", REF[wrong["cid"]])
    check("correct code shows success state", solved["success"], solved)
    print("CORRECT CODE RUN MS (in page):", solved["ms"], flush=True)
    page.evaluate("() => { const b = document.querySelector('.challenge-box'); b.scrollTop = b.scrollHeight; }")
    page.wait_for_timeout(300)
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/challenge-passed.png")
    placed = page.evaluate("""async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      window.__solvedKind = null;
      document.getElementById('challenge-place-btn').click();
      await sleep(150);
      return { solvedKind: window.__solvedKind,
               closed: document.getElementById('challenge-overlay').classList.contains('hidden') };
    }""")
    check("Place building fired onSolved", placed.get("solvedKind") == "wall", placed)
    check("panel closed after Place building", placed.get("closed") is True, placed)

    # 4. Infinite loop times out without hanging the page (timed in-page).
    loop = page.evaluate("""async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      window.__castle.openChallenge('tower', () => {});
      await sleep(150);
      const ed = document.getElementById('challenge-editor');
      const m = ed.value.match(/function\\s+(\\w+)/);
      ed.value = 'function ' + m[1] + '() { while (true) {} }';
      const t0 = performance.now();
      document.getElementById('challenge-run').click();
      while (performance.now() - t0 < 30000) {
        if (document.getElementById('challenge-error').textContent.length > 0) break;
        await sleep(100);
      }
      const out = {
        ms: Math.round(performance.now() - t0),
        error: document.getElementById('challenge-error').textContent,
        responsive: 1 + 1,
      };
      document.getElementById('challenge-close').click();
      return out;
    }""")
    check("infinite loop reports timeout", "Time limit exceeded" in loop["error"], loop)
    check("page still responsive after timeout", loop["responsive"] == 2)
    check("timeout fired promptly (in page)", loop["ms"] < 10000, loop["ms"])
    print("INFINITE LOOP TIMEOUT MS (in page):", loop["ms"], flush=True)

    # 5. Pause check: enemy movement frozen while the panel is open, resumes
    # after; gold also frozen while open and ticks again after close.
    # (At ~2 FPS under SwiftShader, game time runs ~5x slower than real time,
    # so the gold check polls up to 60s for the next 5s income tick.)
    pause = page.evaluate("""async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      document.getElementById('btn-next-wave').click();
      let spawned = false;
      for (let i = 0; i < 60; i++) {
        if (window.__castle.enemies.length > 0) { spawned = true; break; }
        await sleep(500);
      }
      if (!spawned) return { spawned: false };
      const pos = () => {
        const e = window.__castle.enemies[0];
        return e ? [e.group.position.x, e.group.position.z] : null;
      };
      const goldBefore = window.__castle.state.gold;
      const p0 = pos();
      window.__castle.openChallenge('farm', () => {});
      await sleep(8000);
      const p1 = pos();
      const goldDuring = window.__castle.state.gold;
      const flagOpen = window.__castle.challengeOpen();
      document.getElementById('challenge-close').click();
      await sleep(8000);
      const p2 = pos();
      let goldAfter = window.__castle.state.gold;
      const t0 = performance.now();
      while (goldAfter <= goldDuring && performance.now() - t0 < 60000) {
        await sleep(1000);
        goldAfter = window.__castle.state.gold;
      }
      const moved = (a, b) => !a || !b ? false : Math.hypot(a[0] - b[0], a[1] - b[1]);
      return { spawned: true, goldBefore, goldDuring, goldAfter, flagOpen,
        frozenDist: moved(p0, p1), resumedDist: moved(p1, p2) };
    }""")
    check("wave spawned an enemy for the pause check", pause.get("spawned") is True, pause)
    check("challengeOpen flag true while open", pause.get("flagOpen") is True)
    check("enemy frozen while panel open", pause.get("frozenDist") == 0, pause)
    check("enemy moves again after close", (pause.get("resumedDist") or 0) > 0.5, pause)
    check("gold frozen while panel open", pause.get("goldDuring") == pause.get("goldBefore"), pause)
    check("gold ticks again after close", pause.get("goldAfter") > pause.get("goldDuring"), pause)

    # 6. All 21 challenges pass against reference solutions (visible + hidden).
    solved_ids = []
    for cid, code in REF.items():
        res = page.evaluate("""async ([cid, code, kind]) => {
          const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
          let id = null;
          for (let attempt = 0; attempt < 12; attempt++) {
            window.__solvedKind = null;
            window.__castle.openChallenge(kind, (k) => { window.__solvedKind = k; });
            await sleep(150);
            id = window.__castle.challengeId();
            if (id === cid) break;
            document.getElementById('challenge-close').click();
            await sleep(120);
          }
          if (id !== cid) return { cid, opened: false, id };
          document.getElementById('challenge-editor').value = code;
          const runOnce = async () => {
            document.getElementById('challenge-run').click();
            const t0 = performance.now();
            while (performance.now() - t0 < 30000) {
              if (!document.getElementById('challenge-success').classList.contains('hidden')) return true;
              if (document.getElementById('challenge-summary').textContent.length > 0
                && document.querySelectorAll('#challenge-results .challenge-test').length >= 3
                && document.getElementById('challenge-run').disabled === false) return false;
              if (document.getElementById('challenge-summary').textContent.indexOf('Run failed') === 0
                && document.getElementById('challenge-run').disabled === false) return false;
              await sleep(100);
            }
            return false;
          };
          let success = await runOnce();
          // One retry if the runner itself errored (starved worker in this
          // headless environment), since Run is idempotent and free.
          if (!success && document.getElementById('challenge-summary').textContent.indexOf('Run failed') === 0) {
            success = await runOnce();
          }
          const out = { cid, opened: true, id, success,
            summary: document.getElementById('challenge-summary').textContent };
          if (success) {
            document.getElementById('challenge-place-btn').click();
            await sleep(150);
            out.solvedKind = window.__solvedKind;
          } else {
            document.getElementById('challenge-close').click();
            await sleep(120);
          }
          return out;
        }""", [cid, code, KIND_OF[cid]])
        check(f"opened {cid}", res.get("opened") is True, res)
        check(f"reference solution solves {cid}", res.get("success") is True, res)
        if res.get("success"):
            solved_ids.append(cid)
            check(f"onSolved fired for {cid}", res.get("solvedKind") == KIND_OF[cid], res)
    print("SOLVED 21:", json.dumps(solved_ids), flush=True)

    # 7. No-repeat rule: opening the same kind twice in a row gives a different variant.
    norepeat = page.evaluate("""async () => {
      const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
      window.__castle.openChallenge('wall', () => {});
      await sleep(150);
      const a = window.__castle.challengeId();
      document.getElementById('challenge-close').click();
      await sleep(150);
      window.__castle.openChallenge('wall', () => {});
      await sleep(150);
      const b = window.__castle.challengeId();
      document.getElementById('challenge-close').click();
      return { a, b };
    }""")
    check("no immediate repeat variant", norepeat["a"] != norepeat["b"], norepeat)

    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/challenge-test-final.png")
    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none", flush=True)
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none", flush=True)
print("RESULT:", "PASS" if not failures and not real_errors and not failed_reqs else "FAIL", flush=True)
if failures:
    print("FAILURES:", json.dumps(failures, indent=1), flush=True)
sys.exit(0 if not failures and not real_errors and not failed_reqs else 1)
