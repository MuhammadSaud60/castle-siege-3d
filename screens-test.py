"""Phase 3 screens test: start screen, win/lose screens, How to Play.

- Start screen is visible on load and the game is paused until Start
  (gold does not tick, no wave starts). The pause window is sized from
  a measured frame rate, and the same window is shown to produce a
  tick once the game starts, so the no-tick assertion is meaningful.
- Start begins the game (income ticks resume).
- How to Play opens and closes from the HUD button and from the start
  screen, and pauses the game while open.
- Lose path: damageKeep(100) through the real function shows the
  game-over screen with stats; Restart returns a fully fresh game.
- Win path: wave 10 is started for real, its enemies are cleared
  through the exposed debug handle, checkWaveEnd fires the victory
  screen with stats; Play again returns a fully fresh game.
- A tower is built through the real challenge flow first, and a wave-1
  enemy is killed by its arrows, so the lose stats carry real kills,
  buildings and solved challenges. No cheat button ships in the game.
"""
import json
import re
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []
failed_reqs = []
failures = []

# Reference solutions, kept in this test file only (copied from
# build-flow-test.py). Only the tower challenge is needed here.
REF = {
    "tower-1": "function totalArrows(waves) { let t = 0; for (const n of waves) t += n; return t * 3; }",
    "tower-2": "function countGoblins(types) { let c = 0; for (const t of types) if (t === 'goblin') c++; return c; }",
    "tower-3": "function enemiesInRange(range, distances) { let c = 0; for (const d of distances) if (d <= range) c++; return c; }",
}

FPS_JS = """() => new Promise((res) => {
  let n = 0;
  const t0 = performance.now();
  function f() {
    n++;
    if (performance.now() - t0 < 2000) requestAnimationFrame(f);
    else res(n / 2);
  }
  requestAnimationFrame(f);
})"""

SNAP_JS = """() => {
  const s = window.__castle.state;
  const vis = (id) => !document.getElementById(id).classList.contains('hidden');
  return { wood: s.wood, stone: s.stone, gold: s.gold, food: s.food,
    pop: s.population, popCap: s.popCap, wave: s.wave,
    waveActive: s.waveActive, keepHp: s.keepHp, kills: s.kills,
    goldEarned: s.goldEarned, buildingsBuilt: s.buildingsBuilt,
    challengesSolved: s.challengesSolved,
    built: window.__castle.built.length,
    soldiers: window.__castle.soldiers.length,
    enemies: window.__castle.enemies.length,
    armyCap: window.__castle.army().cap,
    started: window.__castle.started(), gameOver: window.__castle.gameOver(),
    startVisible: vis('start-overlay'), howtoVisible: vis('howto-overlay'),
    victoryVisible: vis('victory-overlay'), fallenVisible: vis('fallen-overlay'),
    status: document.getElementById('wave-status').textContent };
}"""

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
        summary: document.getElementById('challenge-summary').textContent };
    }
    const summary = document.getElementById('challenge-summary').textContent;
    if (summary && document.querySelectorAll('#challenge-results .challenge-test').length >= 3
      && !document.getElementById('challenge-run').disabled) break;
    await sleep(100);
  }
  return { ok: false, cid, summary: document.getElementById('challenge-summary').textContent };
}"""

STATS_JS = """(prefix) => {
  const t = (id) => document.getElementById(prefix + '-' + id).textContent;
  return { waves: t('waves'), kills: t('kills'), gold: t('gold'),
    buildings: t('buildings'), challenges: t('challenges'), time: t('time') };
}"""

FRESH_JS = """(btnId) => {
  document.getElementById(btnId).click();
  const s = window.__castle.state;
  const vis = (id) => !document.getElementById(id).classList.contains('hidden');
  return { wood: s.wood, stone: s.stone, gold: s.gold, food: s.food,
    pop: s.population, popCap: s.popCap, wave: s.wave,
    waveActive: s.waveActive, keepHp: s.keepHp, kills: s.kills,
    goldEarned: s.goldEarned, buildingsBuilt: s.buildingsBuilt,
    challengesSolved: s.challengesSolved,
    built: window.__castle.built.length,
    soldiers: window.__castle.soldiers.length,
    enemies: window.__castle.enemies.length,
    armyCap: window.__castle.army().cap,
    started: window.__castle.started(), gameOver: window.__castle.gameOver(),
    startVisible: vis('start-overlay'), howtoVisible: vis('howto-overlay'),
    victoryVisible: vis('victory-overlay'), fallenVisible: vis('fallen-overlay') };
}"""


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""), flush=True)
    if not cond:
        failures.append(name)


def snap(page):
    return page.evaluate(SNAP_JS)


def fresh(page, btn_id):
    return page.evaluate(FRESH_JS, btn_id)


def expect_fresh(name, s):
    ok = (
        s["wood"] == 100 and s["stone"] == 80 and s["gold"] == 50
        and s["food"] == 60 and s["pop"] == 12 and s["popCap"] == 16
        and s["wave"] == 0 and not s["waveActive"] and s["keepHp"] == 100
        and s["kills"] == 0 and s["goldEarned"] == 0
        and s["buildingsBuilt"] == 0 and s["challengesSolved"] == 0
        and s["built"] == 0 and s["soldiers"] == 0 and s["enemies"] == 0
        and s["armyCap"] == 8 and s["started"] and not s["gameOver"]
        and not s["startVisible"] and not s["howtoVisible"]
        and not s["victoryVisible"] and not s["fallenVisible"]
    )
    check(name, ok, json.dumps(s))


def wait_for_tick(page, timeout_s):
    """Poll until gold changes; return seconds waited, or None."""
    before = snap(page)["gold"]
    waited = 0.0
    while waited < timeout_s:
        page.wait_for_timeout(500)
        waited += 0.5
        if snap(page)["gold"] != before:
            return waited
    return None


with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 640, "height": 400})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    check("game object is live", page.evaluate("() => !!window.__castle"))

    # Frame rate sets the pause window: delta is clamped at 0.1s, so
    # game-seconds per real second is min(fps, 10) * 0.1. Wait long
    # enough for more than one 5-second income tick if unpaused.
    fps = page.evaluate(FPS_JS)
    rate = min(fps, 10) * 0.1
    wait_pre = min(6 / rate + 1, 45)
    print(f"FPS: {fps:.1f} game-rate: {rate:.2f} pause window: {wait_pre:.1f}s", flush=True)

    s0 = snap(page)
    check("start screen is visible on load", s0["startVisible"] and not s0["started"], json.dumps(s0))
    check("starting resources on load", s0["gold"] == 50 and s0["wave"] == 0 and s0["enemies"] == 0, json.dumps(s0))
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_timeout(600)
    page.screenshot(path=SHOT_DIR + "screens-start.png")
    page.set_viewport_size({"width": 640, "height": 400})
    page.wait_for_timeout(400)

    # Paused until Start: gold must not tick over a window that would
    # produce a tick if the game were running.
    page.wait_for_timeout(int(wait_pre * 1000))
    s1 = snap(page)
    check("game is paused until Start (gold does not tick)", s1["gold"] == 50, json.dumps(s1))
    check("no wave starts before Start", s1["wave"] == 0 and s1["enemies"] == 0 and not s1["waveActive"], json.dumps(s1))

    # How to Play from the start screen, then back to the start screen.
    page.click("#btn-start-howto")
    page.wait_for_timeout(400)
    s2 = snap(page)
    check("How to Play opens from the start screen", s2["howtoVisible"], json.dumps(s2))
    howto_text = page.evaluate("() => document.getElementById('howto-overlay').textContent")
    check("How to Play lists buildings, waves and the win", "Barracks" in howto_text and "10 waves" in howto_text and "Tower" in howto_text, howto_text[:120])
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_timeout(600)
    page.screenshot(path=SHOT_DIR + "screens-howto.png")
    page.set_viewport_size({"width": 640, "height": 400})
    page.wait_for_timeout(400)
    page.click("#btn-howto-close")
    page.wait_for_timeout(400)
    s3 = snap(page)
    check("How to Play closes back to the start screen", not s3["howtoVisible"] and s3["startVisible"] and not s3["started"], json.dumps(s3))
    check("still paused after closing How to Play", snap(page)["gold"] == 50)

    # Start begins the game: income ticks resume.
    page.click("#btn-start")
    page.wait_for_timeout(400)
    s4 = snap(page)
    check("Start hides the start screen and starts the game", not s4["startVisible"] and s4["started"], json.dumps(s4))
    tick_in = wait_for_tick(page, 45)
    check("income ticks after Start", tick_in is not None, f"no tick in 45s (gold {snap(page)['gold']})")
    if tick_in is not None:
        print(f"first tick after Start: {tick_in}s", flush=True)
        check("pause window was long enough for a tick", tick_in <= wait_pre, f"tick_in={tick_in} window={wait_pre:.1f}")

    # How to Play from the HUD pauses the game while open.
    page.click("#btn-howto")
    page.wait_for_timeout(400)
    check("How to Play opens from the HUD button", snap(page)["howtoVisible"])
    gold_open = snap(page)["gold"]
    page.wait_for_timeout(int(wait_pre * 1000))
    check("game pauses while How to Play is open", snap(page)["gold"] == gold_open,
          f"gold {gold_open} -> {snap(page)['gold']}")
    page.keyboard.press("Escape")
    page.wait_for_timeout(400)
    check("Escape closes How to Play", not snap(page)["howtoVisible"])
    check("income resumes after closing How to Play", wait_for_tick(page, 45) is not None)

    # Build a tower through the real challenge flow.
    page.click("#btn-build-tower")
    page.wait_for_timeout(600)
    check("tower button opens the challenge panel",
          page.evaluate("() => !document.getElementById('challenge-overlay').classList.contains('hidden')"))
    solved = page.evaluate(SOLVE_JS, REF)
    check("tower challenge solves", solved["ok"], json.dumps(solved))
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(400)
    check("solving arms tower placement",
          page.evaluate("() => window.__castle.placing().kind") == "tower")
    pt = page.evaluate("() => window.__castle.screenPoint(12, 0, -12)")
    page.mouse.click(pt[0], pt[1])
    page.wait_for_timeout(600)
    s5 = snap(page)
    check("tower is built", s5["built"] == 1 and s5["buildingsBuilt"] == 1, json.dumps(s5))
    check("challenge counted as solved", s5["challengesSolved"] == 1, json.dumps(s5))

    # Wave 1: the tower's arrows kill an enemy (soldier HP is 2).
    page.click("#btn-next-wave")
    page.wait_for_timeout(1000)
    check("wave 1 started", snap(page)["wave"] == 1 and snap(page)["enemies"] == 3, json.dumps(snap(page)))
    page.evaluate("""() => {
      const t = window.__castle.built[0];
      for (const e of window.__castle.enemies) {
        e.group.position.set(t.x + 5.7, window.__castle.world.terrain(t.x + 5.7, t.z - 5.7), t.z - 5.7);
      }
    }""")
    killed = False
    for _ in range(90):
        page.wait_for_timeout(500)
        if snap(page)["kills"] >= 1:
            killed = True
            break
    check("tower arrows kill an enemy (kills counts)", killed, json.dumps(snap(page)))

    # Lose path through the real damageKeep function.
    page.evaluate("() => window.__castle.damageKeep(100)")
    page.wait_for_timeout(600)
    s6 = snap(page)
    check("keep HP 0 shows the game-over screen", s6["fallenVisible"] and s6["gameOver"], json.dumps(s6))
    lost = page.evaluate(STATS_JS, "fallen")
    print("LOSE STATS:", json.dumps(lost), flush=True)
    check("game-over stats are filled", lost["waves"] == "0" and int(lost["kills"]) >= 1
          and int(lost["gold"]) > 0 and lost["buildings"] == "1" and lost["challenges"] == "1"
          and re.fullmatch(r"\d+:\d\d", lost["time"]) is not None, json.dumps(lost))
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_timeout(600)
    page.screenshot(path=SHOT_DIR + "screens-gameover.png")
    page.set_viewport_size({"width": 640, "height": 400})
    page.wait_for_timeout(400)

    # Restart returns a fully fresh game, verified atomically.
    expect_fresh("Restart returns a fully fresh game", fresh(page, "btn-restart"))

    # Win path: wave 10 starts for real, then its enemies are cleared
    # through the exposed debug handle and checkWaveEnd fires victory.
    page.evaluate("() => { window.__castle.state.wave = 9; }")
    page.click("#btn-next-wave")
    page.wait_for_timeout(1000)
    s7 = snap(page)
    check("wave 10 started", s7["wave"] == 10 and s7["waveActive"] and s7["enemies"] == 21, json.dumps(s7))
    page.evaluate("() => window.__castle.clearEnemies()")
    won = False
    for _ in range(20):
        page.wait_for_timeout(500)
        if snap(page)["victoryVisible"]:
            won = True
            break
    check("clearing wave 10 shows the victory screen", won, json.dumps(snap(page)))
    won_stats = page.evaluate(STATS_JS, "victory")
    print("WIN STATS:", json.dumps(won_stats), flush=True)
    check("victory stats are filled", won_stats["waves"] == "10" and int(won_stats["gold"]) >= 20
          and re.fullmatch(r"\d+:\d\d", won_stats["time"]) is not None, json.dumps(won_stats))
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_timeout(600)
    page.screenshot(path=SHOT_DIR + "screens-victory.png")
    page.set_viewport_size({"width": 640, "height": 400})
    page.wait_for_timeout(400)

    # Play again returns a fully fresh game, verified atomically.
    expect_fresh("Play again returns a fully fresh game", fresh(page, "btn-play-again"))

    browser.close()

real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none", flush=True)
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none", flush=True)
print("RESULT:", "PASS" if not failures and not real_errors and not failed_reqs else "FAIL", flush=True)
if failures:
    print("FAILURES:", json.dumps(failures, indent=1), flush=True)
sys.exit(0 if not failures and not real_errors and not failed_reqs else 1)
