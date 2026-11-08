"""Phase 4 headless test: save/load round trip, leaderboard panel + submit,
local fallback when the server is unreachable, zero errors.

Prereqs (started by the runner before this script):
  - API server on http://127.0.0.1:3001 (fresh, data/scores.json removed)
  - vite preview on http://127.0.0.1:4173 serving the production build
"""
import json
import sys
import time
import urllib.request
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
API = "http://127.0.0.1:3001"
errors = []
failed_reqs = []

def harmless(text):
    # SwiftShader warnings are environment noise, not game errors.
    if "ReadPixels" in text or "GPU stall" in text:
        return True
    # A failed fetch always logs "Failed to load resource" in Chromium.
    # The only fetches this test makes to unreachable origins are expected:
    # the Render API URL (not deployed yet, the sandbox proxy cannot tunnel
    # to it) and the deliberate dead-port fallback probe on 127.0.0.1:3999.
    if text.startswith("Failed to load resource: net::ERR_TUNNEL_CONNECTION_FAILED"):
        return True
    if text.startswith("Failed to load resource: net::ERR_CONNECTION_REFUSED"):
        return True
    return False

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" and not harmless(m.text) else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}") if "onrender.com" not in r.url and "127.0.0.1:3999" not in r.url else None)
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 and "onrender.com" not in r.url and "127.0.0.1:3999" not in r.url else None)

    # --- fresh start: no save, no Continue overlay -------------------------
    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    start_state = page.evaluate("""() => ({
      started: window.__castle.save.isStarted(),
      overlayHidden: document.getElementById('start-overlay').classList.contains('hidden'),
      wave: window.__castle.state.wave,
      boardVisible: !document.getElementById('leaderboard-panel').classList.contains('hidden'),
      note: document.getElementById('leaderboard-note').textContent,
    })""")
    print("FRESH START:", json.dumps(start_state))

    # --- point the leaderboard at the local API and load it -----------------
    page.evaluate(f"() => {{ window.__castle.leaderboard.setApiBase('{API}'); window.__castle.leaderboard.fetchBoard(); }}")
    page.wait_for_timeout(1500)
    board0 = page.evaluate("""() => ({
      note: document.getElementById('leaderboard-note').textContent,
      rows: [...document.querySelectorAll('#leaderboard-list li')].map(li => li.textContent),
      serverOk: window.__castle.leaderboard.serverOk(),
    })""")
    print("BOARD EMPTY:", json.dumps(board0))

    # --- place a farm, set distinctive state, save --------------------------
    page.click("#btn-build-farm")
    page.mouse.click(640, 620)
    page.wait_for_timeout(600)
    page.evaluate("""() => {
      const s = window.__castle.state;
      s.wood = 123; s.stone = 45; s.gold = 67; s.food = 89;
      s.wave = 2; s.keepHp = 77; s.kills = 5; s.goldEarned = 99;
      window.__castle.save.save(false);
    }""")
    saved = page.evaluate("() => JSON.parse(localStorage.getItem('castle-siege-save-v1'))")
    print("SAVED:", json.dumps({k: saved[k] for k in ("wood", "wave", "keepHp", "kills", "goldEarned", "farmCount")}), "buildings:", json.dumps(saved["buildings"]))

    # --- reload: Continue overlay must appear; continue restores state -------
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    overlay = page.evaluate("""() => ({
      hidden: document.getElementById('start-overlay').classList.contains('hidden'),
      summary: document.getElementById('save-summary').textContent,
      started: window.__castle.save.isStarted(),
    })""")
    print("AFTER RELOAD (overlay):", json.dumps(overlay))
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase4-screenshot-continue.png")
    page.click("#btn-continue")
    page.wait_for_timeout(600)
    restored = page.evaluate("""() => ({
      wood: window.__castle.state.wood, stone: window.__castle.state.stone,
      gold: window.__castle.state.gold, food: window.__castle.state.food,
      wave: window.__castle.state.wave, keepHp: window.__castle.state.keepHp,
      kills: window.__castle.state.kills, goldEarned: window.__castle.state.goldEarned,
      farmCount: window.__castle.state.farmCount, built: window.__castle.built.length,
      started: window.__castle.save.isStarted(),
    })""")
    print("RESTORED:", json.dumps(restored))

    # --- submit a score to the local API ------------------------------------
    page.evaluate("() => { window.__castle.leaderboard.setApiBase('" + API + "'); window.__castle.leaderboard.enableSubmit(); }")
    page.fill("#score-name", "Tester")
    page.click("#btn-submit-score")
    page.wait_for_timeout(1500)
    submit = page.evaluate("""() => ({
      status: document.getElementById('score-status').textContent,
      rows: [...document.querySelectorAll('#leaderboard-list li')].map(li => li.textContent),
      note: document.getElementById('leaderboard-note').textContent,
    })""")
    print("SUBMIT:", json.dumps(submit))
    with urllib.request.urlopen(API + "/api/scores?limit=10") as r:
        api_top = json.loads(r.read())
    print("API TOP10:", json.dumps(api_top))

    # --- server unreachable: local fallback ----------------------------------
    page.evaluate("() => { window.__castle.leaderboard.setApiBase('http://127.0.0.1:3999'); window.__castle.leaderboard.fetchBoard(); }")
    page.wait_for_timeout(1500)
    fallback = page.evaluate("""() => ({
      note: document.getElementById('leaderboard-note').textContent,
      rows: [...document.querySelectorAll('#leaderboard-list li')].map(li => li.textContent),
    })""")
    print("FALLBACK:", json.dumps(fallback))

    # --- corrupt save: game must start fresh, no overlay --------------------
    page.evaluate("() => { localStorage.setItem('castle-siege-save-v1', '{not json'); }")
    page.reload(wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    corrupt = page.evaluate("""() => ({
      hidden: document.getElementById('start-overlay').classList.contains('hidden'),
      started: window.__castle.save.isStarted(),
      wave: window.__castle.state.wave,
    })""")
    print("CORRUPT SAVE:", json.dumps(corrupt))

    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase4-screenshot.png")
    browser.close()

print("CONSOLE/PAGE ERRORS:", json.dumps(errors, indent=1) if errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")

ok = True
def check(cond, msg):
    global ok
    if not cond:
        print("FAIL:", msg); ok = False

check(start_state["started"] and start_state["overlayHidden"], "fresh start should not show Continue overlay")
check(start_state["boardVisible"], "leaderboard panel should be visible")
check(board0["serverOk"] and "from the server" in board0["note"], "leaderboard did not load from local API")
check(saved["wood"] == 123 and saved["wave"] == 2 and saved["keepHp"] == 77, "save did not hold the set state")
check(saved["farmCount"] == 1 and len(saved["buildings"]) == 1 and saved["buildings"][0]["kind"] == "farm", "farm was not recorded in the save")
check(not overlay["hidden"] and not overlay["started"] and "Wave 2" in overlay["summary"], "Continue overlay missing after reload")
check(restored["wood"] == 123 and restored["wave"] == 2 and restored["keepHp"] == 77 and restored["kills"] == 5 and restored["goldEarned"] == 99, "state was not restored after Continue")
check(restored["farmCount"] == 1 and restored["built"] == 1, "farm building was not restored after Continue")
check("rank #1" in submit["status"], "score submit did not report rank #1")
check(len(api_top["scores"]) == 1 and api_top["scores"][0]["name"] == "Tester" and api_top["scores"][0]["waves"] == 2, "API top 10 does not hold the submitted score")
check("unreachable" in fallback["note"] and any("Tester" in r for r in fallback["rows"]), "local fallback did not show the saved score")
check(corrupt["hidden"] and corrupt["started"] and corrupt["wave"] == 0, "corrupt save broke the fresh start")
check(not errors and not failed_reqs, "errors or failed requests present")
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
