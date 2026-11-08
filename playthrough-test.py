"""Phase 4 playthrough test: a full game, won the real way, plus the
passive lose path.

Victory run: Start is clicked for real; every building and soldier is
earned through the real challenge panel (one solved challenge per
placement, reference solutions kept in this test file only, never in the
bundle) and placed by clicking the canvas; every wave is started with the
real Next Wave button and cleared by the defences. The kingdom follows
the measured competent pace: 2 towers for wave 1, a 3rd before wave 2, a
4th before wave 4, factory + barracks + a wall line + 4 soldiers before
wave 5, a 5th tower + 2 soldiers before wave 7, a 6th tower + 2 soldiers
before wave 9. Buildings get destroyed in the fight, so the plan is kept
by topping up: a lost barracks is rebuilt before training, a lost tower
is replaced at a free slot. Wave 1 marches in for real with no teleporting; waves 2-10
are teleported once started, because the headless march alone would take
minutes per wave (SwiftShader runs the game clock far slower than wall
clock). Each enemy is moved in along its own approach to the radius it
would have reached 19 game-seconds into a real march from the map edge
(radius = max(39, 125 - 19 * speed)), so the wave keeps its real shape:
cavalry enter tower range about 20 game-seconds after the wave starts,
foot soldiers about 25, brutes about 45, and each spends the same time
in tower range as on a real march. Only the dead outer march, where
nothing can shoot anything, is skipped. A uniform teleport was tried
first and rejected twice: to 18 units it drops the whole wave on the keep
at once (80 damage a second, the keep falls in about a second of game
time), and to 45 it still compresses the arrival into one burst. No real
march does either; the staggered teleport is the faithful one. Tower
arrows, soldier melee, building attacks and keep damage all run through
the real update loop.

Resources: the headless clock ticks income far slower than a real session,
so before each build the test tops up exactly the shortfall and logs it.
Every top-up is income a real player would already have banked by then
(1 Stone per 5-second tick, 3 Gold per tick, +20 Gold per cleared wave);
the totals are printed at the end for the economy check.

Passive run: Play again resets to a fresh game, Next Wave is called with
nothing built, and the keep must fall before wave 10.

Screenshots: mid-game kingdom at wave 5, the victory screen, and the
game-over screen. Zero console errors, zero failed requests.
"""
import json
import math
import sys
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
SHOT_DIR = "/home/hatch/workspace/castle-siege-3d/"
errors = []
failed_reqs = []
failures = []

# Reference solutions, kept in this test file only (copied from
# challenge-test.py). Only the kinds this run builds are needed.
REF = {
    "wall-1": "function stonesForLength(length) { return length * 3; }",
    "wall-2": "function stonesForWall(length, height) { return length * height; }",
    "wall-3": "function stoneLeft(stone, length) { return Math.max(0, stone - length * 3); }",
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
    "tower": {"stone": 30, "wood": 10},
    "factory": {"wood": 25, "stone": 15},
    "barracks": {"wood": 30, "stone": 20},
    "soldier": {"gold": 20},
}

# Wave sizes after the Phase 4 balance pass: 3 + 2 per wave, plus one
# extra per wave from wave 6 (wave 10 has 26 enemies).
WAVE_COUNT = {1: 3, 2: 5, 3: 7, 4: 9, 5: 11, 6: 14, 7: 17, 8: 20, 9: 23, 10: 26}

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
    goldEarned: s.goldEarned, barracks: s.barracksCount,
    factories: s.factoryCount, wave: s.wave, waveActive: s.waveActive,
    keepHp: s.keepHp, kills: s.kills, buildingsBuilt: s.buildingsBuilt,
    challengesSolved: s.challengesSolved, built: window.__castle.built.length,
    builtKinds: window.__castle.built.map((b) => b.kind),
    soldiers: window.__castle.soldiers.length,
    enemies: window.__castle.enemies.length,
    placing: window.__castle.placing().kind,
    started: window.__castle.started(), gameOver: window.__castle.gameOver(),
    startVisible: vis('start-overlay'), victoryVisible: vis('victory-overlay'),
    fallenVisible: vis('fallen-overlay') };
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

grants = {"wood": 0, "stone": 0, "gold": 0}


def check(name, cond, extra=""):
    print(("PASS " if cond else "FAIL ") + name + ((" :: " + str(extra)) if extra and not cond else ""), flush=True)
    if not cond:
        failures.append(name)


def report(code):
    real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
    print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none", flush=True)
    print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none", flush=True)
    print("RESULT:", "PASS" if not failures and not real_errors and not failed_reqs else "FAIL", flush=True)
    if failures:
        print("FAILURES:", json.dumps(failures, indent=1), flush=True)
    sys.exit(code)


def snap(page):
    return page.evaluate(SNAP_JS)


def top_up(page, cost, why):
    """Grant exactly the shortfall for a build, and log it. The shortfall
    is income ticks the slow headless clock has not fired yet: stone at
    1 per tick (3 with a factory), gold at 3 per tick, plus +20 Gold per
    cleared wave, all of which a real session banks while playing."""
    s = snap(page)
    add = {}
    for res, amount in cost.items():
        if s[res] < amount:
            add[res] = amount - s[res]
    if add:
        for res, amount in add.items():
            grants[res] += amount
        page.evaluate("""(add) => {
          const s = window.__castle.state;
          if (add.wood) s.wood += add.wood;
          if (add.stone) s.stone += add.stone;
          if (add.gold) s.gold += add.gold;
        }""", add)
        print(f"GRANT {why}: {add} (cumulative {grants})", flush=True)


def center_camera(page, x, z):
    """Top-down camera centred over (x, z), so its screen point is the
    middle of the canvas and never under a HUD panel."""
    page.evaluate("""([x, z]) => {
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(x, 2, z);
      c.position.set(x, 110, z + 70);
      t.update();
    }""", [x, z])
    page.wait_for_timeout(400)


def ground_click(page, x, z):
    """Click the ground at world (x, z) via its screen point. Returns
    True when the point lands on the canvas."""
    center_camera(page, x, z)
    pt = page.evaluate("([x, z]) => window.__castle.screenPoint(x, 0, z)", [x, z])
    if not pt:
        return False
    el = page.evaluate("""([px, py]) => {
      const el = document.elementFromPoint(px, py);
      return el ? el.tagName : 'null';
    }""", pt)
    if el != "CANVAS":
        print(f"GROUND CLICK ({x},{z}): screen point {pt} hits {el}, not the canvas", flush=True)
        return False
    page.mouse.click(pt[0], pt[1])
    page.wait_for_timeout(500)
    return True


def build(page, kind, x, z, why):
    """One building through the real flow: button, challenge, Place,
    canvas click. Asserts one solve buys exactly one building."""
    top_up(page, COSTS[kind], why)
    before = snap(page)
    page.click(f"#btn-build-{kind}")
    page.wait_for_timeout(500)
    check(f"{why}: {kind} button opens the challenge panel", page.evaluate(
        "() => !document.getElementById('challenge-overlay').classList.contains('hidden')"))
    solved = page.evaluate(SOLVE_JS, REF)
    check(f"{why}: {kind} challenge solves ({solved.get('cid')})", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(400)
    check(f"{why}: {kind} enters placement mode",
          page.evaluate("() => window.__castle.placing().kind") == kind)
    ok = ground_click(page, x, z)
    check(f"{why}: {kind} ground click lands on the canvas at ({x},{z})", ok)
    after = snap(page)
    check(f"{why}: {kind} is built",
          after["built"] == before["built"] + 1
          and after["builtKinds"].count(kind) == before["builtKinds"].count(kind) + 1,
          {"before": before["built"], "after": after["built"]})
    check(f"{why}: one solve buys one {kind} (placement ends)",
          after["placing"] is None, after["placing"])
    check(f"{why}: challenge counted as solved",
          after["challengesSolved"] == before["challengesSolved"] + 1,
          {"before": before["challengesSolved"], "after": after["challengesSolved"]})
    return after


def build_wall_line(page, x0, z0, x1, z1, why):
    """One wall drag through the real flow: button, challenge, Place,
    drag across the ground. One solve buys one drag."""
    top_up(page, {"stone": 60}, why)
    before = snap(page)
    page.click("#btn-build-wall")
    page.wait_for_timeout(500)
    solved = page.evaluate(SOLVE_JS, REF)
    check(f"{why}: wall challenge solves ({solved.get('cid')})", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(400)
    center_camera(page, (x0 + x1) / 2, (z0 + z1) / 2)
    a = page.evaluate("([x, z]) => window.__castle.screenPoint(x, 0, z)", [x0, z0])
    b = page.evaluate("([x, z]) => window.__castle.screenPoint(x, 0, z)", [x1, z1])
    page.mouse.move(a[0], a[1])
    page.wait_for_timeout(200)
    page.mouse.down()
    for i in range(1, 9):
        page.mouse.move(a[0] + (b[0] - a[0]) * i / 8, a[1] + (b[1] - a[1]) * i / 8)
        page.wait_for_timeout(100)
    page.mouse.up()
    page.wait_for_timeout(500)
    after = snap(page)
    walls = after["builtKinds"].count("wall") - before["builtKinds"].count("wall")
    check(f"{why}: wall drag places segments", walls >= 4, f"walls={walls}")
    check(f"{why}: one drag spends the grant (placement ends)",
          after["placing"] is None, after["placing"])
    print(f"WALL LINE: {walls} segments placed", flush=True)
    return after


TOWER_SLOTS = [(16, 0), (-16, 0), (8, 14), (-8, 14), (-8, -14), (8, -14)]
BARRACKS_SPOTS = [(24, 24), (-24, -24)]


def ensure_barracks(page, why):
    """Buildings get destroyed in the fight: if the barracks is gone,
    training is disabled, so rebuild it first (a fresh Hard challenge).
    This is what a real player does after losing a building."""
    if snap(page)["barracks"] > 0:
        return
    print("BARRACKS LOST: rebuilding before training", flush=True)
    for (x, z) in BARRACKS_SPOTS:
        taken = page.evaluate(
            "([x, z]) => window.__castle.built.some((b) => b.x === x && b.z === z)",
            [x, z])
        if not taken:
            build(page, "barracks", x, z, why + " (barracks rebuild)")
            return
    raise AssertionError("no free barracks spot")


def build_towers_up_to(page, n, why):
    """Top the tower count up to n, building at empty slots. Towers get
    destroyed too, so the plan is a count, not a fixed list of builds."""
    for _ in range(3):
        s = snap(page)
        have = s["builtKinds"].count("tower")
        if have >= n:
            return
        for (x, z) in TOWER_SLOTS:
            taken = page.evaluate(
                "([x, z]) => window.__castle.built.some((b) => b.x === x && b.z === z)",
                [x, z])
            if not taken:
                build(page, "tower", x, z, why)
                break
    check(f"{why}: tower count topped up to {n}",
          snap(page)["builtKinds"].count("tower") >= n)


def train(page, why):
    """One soldier through the real flow: Train button, challenge, Train."""
    ensure_barracks(page, why)
    top_up(page, COSTS["soldier"], why)
    before = snap(page)
    page.click("#btn-train-soldier")
    page.wait_for_timeout(500)
    check(f"{why}: Train opens the soldier challenge", page.evaluate(
        "() => !document.getElementById('challenge-overlay').classList.contains('hidden')"))
    solved = page.evaluate(SOLVE_JS, REF)
    check(f"{why}: soldier challenge solves ({solved.get('cid')})", solved["ok"] is True, solved)
    page.evaluate("() => document.getElementById('challenge-place-btn').click()")
    page.wait_for_timeout(500)
    after = snap(page)
    check(f"{why}: soldier trained",
          after["soldiers"] == before["soldiers"] + 1,
          {"before": before["soldiers"], "after": after["soldiers"]})
    check(f"{why}: challenge counted as solved",
          after["challengesSolved"] == before["challengesSolved"] + 1)
    return after


TELEPORT_JS = """() => {
  // Staggered teleport (see the module docstring): every enemy is moved
  // in along its own approach to the radius it would have reached 19
  // game-seconds into a real march from the map edge, so the wave keeps
  // its real arrival stagger and tower-engagement time.
  for (const e of window.__castle.enemies) {
    const a = Math.atan2(e.group.position.z, e.group.position.x);
    const r = Math.max(39, 125 - 19 * e.speed);
    const x = Math.cos(a) * r, z = Math.sin(a) * r;
    e.group.position.set(x, window.__castle.world.terrain(x, z), z);
  }
}"""


def run_wave(page, n, rate, teleport):
    """Start wave n with the real Next Wave button, then wait for the
    defences to clear it. teleport=True moves the spawned enemies from
    the map edge along their own approaches (the march is skipped, the
    fight is real); wave 1 runs with no teleport at all."""
    page.click("#btn-next-wave")
    page.wait_for_timeout(1000)
    s = snap(page)
    check(f"wave {n}: started by the Next button",
          s["wave"] == n and s["waveActive"] and s["enemies"] == WAVE_COUNT[n], json.dumps(s))
    if teleport:
        page.evaluate(TELEPORT_JS)
        print(f"wave {n}: enemies staggered-teleported (19 game-seconds in)", flush=True)
    cap = (70 / rate + 90) if n == 1 else (60 / rate + 60)
    t0 = time.time()
    cleared = False
    while time.time() - t0 < cap:
        page.wait_for_timeout(2000)
        s = snap(page)
        if s["keepHp"] <= 0:
            break
        if not s["waveActive"]:
            cleared = True
            break
    s = snap(page)
    check(f"wave {n}: cleared by the defences (keep HP {s['keepHp']}, kills {s['kills']})",
          cleared and s["keepHp"] > 0, json.dumps(s))
    print(f"WAVE {n} DONE: keep HP {s['keepHp']}, kills {s['kills']}, "
          f"soldiers {s['soldiers']}, built {s['built']}, "
          f"wall time {time.time() - t0:.0f}s", flush=True)
    if s["keepHp"] <= 0:
        # The keep fell: stop the victory run here instead of clicking
        # Next Wave behind the game-over overlay until Playwright times out.
        print("ABORT: the victory run lost the keep on wave "
              f"{n}; see the wave log above", flush=True)
        report(1)
    return s


def shot(page, path):
    page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(0, 2, 0);
      c.position.set(56, 42, 56);
      t.update();
    }""")
    page.set_viewport_size({"width": 1280, "height": 800})
    page.wait_for_timeout(1500)
    page.screenshot(path=path)
    page.set_viewport_size({"width": 640, "height": 400})
    page.wait_for_timeout(500)


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
    fps = page.evaluate(FPS_JS)
    rate = min(fps, 10) * 0.1
    print(f"FPS: {fps:.1f} game-rate: {rate:.2f} game-seconds per wall second", flush=True)

    # The real path starts here: Start button, real challenge, real place.
    check("start screen is visible on load", snap(page)["startVisible"])
    page.click("#btn-start")
    page.wait_for_timeout(500)
    check("Start begins the game", snap(page)["started"] and not snap(page)["startVisible"])

    # Top-down camera for placement clicks.
    center_camera(page, 0, 0)

    # Two towers for wave 1 (60 Stone of the starting 80).
    build(page, "tower", 16, 0, "wave 1")
    build(page, "tower", -16, 0, "wave 1")

    # Wave 1: fully real, enemies march in from the map edge.
    run_wave(page, 1, rate, teleport=False)

    # 3rd tower before wave 2 (10 more Stone is 10 income ticks of waiting).
    build(page, "tower", 8, 14, "wave 2")
    run_wave(page, 2, rate, teleport=True)
    run_wave(page, 3, rate, teleport=True)

    # 4th tower before wave 4 (30 Stone is 30 income ticks of waiting).
    build(page, "tower", -8, 14, "wave 4")
    run_wave(page, 4, rate, teleport=True)

    # Before wave 5: factory, barracks, a wall line, 4 soldiers.
    build(page, "factory", 24, -24, "wave 5")
    build(page, "barracks", 24, 24, "wave 5")
    build_wall_line(page, -12, -30, 12, -30, "wave 5")
    for i in range(4):
        train(page, f"wave 5 soldier {i + 1}")
    s = snap(page)
    check("kingdom ready for wave 5 (4 towers, factory, barracks, wall, 4 soldiers)",
          s["builtKinds"].count("tower") == 4 and s["builtKinds"].count("factory") == 1
          and s["builtKinds"].count("barracks") == 1 and s["soldiers"] == 4, json.dumps(s))
    run_wave(page, 5, rate, teleport=True)
    shot(page, SHOT_DIR + "playthrough-wave5.png")
    print("SHOT: playthrough-wave5.png", flush=True)

    run_wave(page, 6, rate, teleport=True)

    # 5th tower + 2 soldiers before wave 7 (topping up: towers fall).
    build_towers_up_to(page, 5, "wave 7")
    for i in range(2):
        train(page, f"wave 7 soldier {i + 1}")
    run_wave(page, 7, rate, teleport=True)
    run_wave(page, 8, rate, teleport=True)

    # 6th tower + 2 soldiers before wave 9 (topping up: towers fall).
    build_towers_up_to(page, 6, "wave 9")
    for i in range(2):
        train(page, f"wave 9 soldier {i + 1}")
    run_wave(page, 9, rate, teleport=True)

    # Wave 10: the win.
    final = run_wave(page, 10, rate, teleport=True)
    s = snap(page)
    check("victory screen shows after wave 10",
          s["victoryVisible"] and not s["waveActive"], json.dumps(s))
    check("victory stats say 10 waves cleared, 135 enemies defeated",
          page.text_content("#victory-waves") == "10"
          and page.text_content("#victory-kills") == "135",
          page.evaluate("() => document.getElementById('victory-waves').textContent + '/' + document.getElementById('victory-kills').textContent"))
    check("victory with the keep alive", s["keepHp"] > 0, json.dumps(s))
    # Pressure verdict (informational, not a pass/fail: spawn angles vary
    # run to run; the 8-seed simulation is the pressure evidence).
    pressure = ("PRESSURED" if s["keepHp"] <= 70 else
                "LIGHT" if s["keepHp"] < 100 else "UNTOUCHED")
    print(f"PRESSURE VERDICT: {pressure} (keep HP {s['keepHp']} at victory)", flush=True)
    check("all 135 enemies defeated across the 10 waves",
          s["kills"] == 135, json.dumps(s))
    print("VICTORY STATS:", json.dumps(s), flush=True)
    print("TOTAL GRANTS (simulated banked income):", json.dumps(grants), flush=True)
    shot(page, SHOT_DIR + "playthrough-victory.png")
    print("SHOT: playthrough-victory.png", flush=True)

    # Passive run: Play again, call wave 1 with nothing built, the keep falls.
    page.click("#btn-play-again")
    page.wait_for_timeout(800)
    s = snap(page)
    check("Play again resets to a fresh game",
          s["keepHp"] == 100 and s["wave"] == 0 and s["built"] == 0
          and s["soldiers"] == 0 and not s["victoryVisible"], json.dumps(s))
    page.click("#btn-next-wave")
    page.wait_for_timeout(1000)
    s = snap(page)
    check("passive run: wave 1 started with no defences",
          s["wave"] == 1 and s["enemies"] == 3, json.dumps(s))
    page.evaluate(TELEPORT_JS)
    fallen = False
    t0 = time.time()
    while time.time() - t0 < 45 / rate + 60:
        page.wait_for_timeout(2000)
        s = snap(page)
        if s["fallenVisible"] and s["gameOver"]:
            fallen = True
            break
    check("passive run: the keep falls before wave 10 (game over on wave 1)",
          fallen and s["keepHp"] == 0 and s["wave"] == 1, json.dumps(s))
    check("passive run: game-over stats say 0 waves cleared on wave 1",
          page.text_content("#fallen-waves") == "0"
          and page.text_content("#fallen-wave") == "1",
          page.evaluate("() => document.getElementById('fallen-waves').textContent + '/' + document.getElementById('fallen-wave').textContent"))
    print("PASSIVE RUN:", json.dumps(s), flush=True)
    shot(page, SHOT_DIR + "playthrough-gameover.png")
    print("SHOT: playthrough-gameover.png", flush=True)

    browser.close()

report(0 if not failures and not [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e] and not failed_reqs else 1)
