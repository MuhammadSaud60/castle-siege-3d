"""Phase 6 headless test: save/leaderboard removed, action buttons are icons."""
import json
import sys
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
errors = []
failed_reqs = []
all_reqs = []

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("request", lambda r: all_reqs.append(r.url))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    print("CANVAS:", page.evaluate("() => !!document.querySelector('#app canvas')"))

    # 1. Save / leaderboard UI must be gone from the DOM entirely.
    gone = ["#btn-save", "#btn-leaderboard", "#leaderboard-panel", "#start-overlay",
            "#score-name", "#fallen-name", "#btn-submit-score", "#btn-submit-fallen",
            "#btn-refresh-board", "#score-line", "#score-status"]
    missing = {s: page.evaluate(f"() => !!document.querySelector('{s}')") for s in gone}
    print("REMOVED UI STILL PRESENT:", json.dumps({k: v for k, v in missing.items() if v}) or "none")

    # 2. Six icon buttons: svg icon + cost label + title tooltip.
    expected = {
        "#btn-build-wall": ("10 Stone", "Build Wall (10 Stone)"),
        "#btn-build-house": ("20 Wood", "Build House (20 Wood)"),
        "#btn-build-farm": ("15 Wood", "Build Farm (15 Wood)"),
        "#btn-build-tower": ("30 Stone, 10 Wood", "Build Tower (30 Stone, 10 Wood)"),
        "#btn-next-wave": ("Next", "Next Wave"),
        "#btn-sound": ("On", "Sound"),
    }
    btns = {}
    for sel, (label, title) in expected.items():
        btns[sel] = page.evaluate("""(sel) => {
          const b = document.querySelector(sel);
          if (!b) return null;
          const lab = b.querySelector('.btn-label');
          return {
            iconBtn: b.classList.contains('icon-btn'),
            hasSvg: !!b.querySelector('svg'),
            label: lab ? lab.textContent : null,
            title: b.getAttribute('title'),
          };
        }""", sel)
    print("ICON BUTTONS:", json.dumps(btns, indent=1))

    # 3. Fresh start: no overlay, wave 0, and no save/score keys in storage.
    print("FRESH STATE:", json.dumps(page.evaluate("""() => ({
      wave: window.__castle.state.wave,
      saveKey: window.localStorage.getItem('castle-siege-save-v1'),
      scoresKey: window.localStorage.getItem('castle-siege-local-scores-v1'),
    })""")))

    # 4. Game still works: place a farm, start a wave.
    page.mouse.click(640, 400)
    page.wait_for_timeout(800)
    page.click("#btn-build-farm")
    page.wait_for_timeout(300)
    print("FARM BTN LABEL WHILE PLACING:",
          page.evaluate("() => document.querySelector('#btn-build-farm .btn-label').textContent"))
    page.mouse.click(640, 620)
    page.wait_for_timeout(600)
    print("FARM COUNT:", page.evaluate("() => window.__castle.state.farmCount"))
    print("FARM BTN LABEL AFTER PLACE:",
          page.evaluate("() => document.querySelector('#btn-build-farm .btn-label').textContent"))
    page.click("#btn-next-wave")
    page.wait_for_timeout(1500)
    print("WAVE:", json.dumps(page.evaluate("() => ({ wave: window.__castle.state.wave, enemies: window.__castle.enemies.length, status: document.getElementById('wave-status').textContent })")))

    # 5. Sound toggle flips the icon button label and muted class.
    page.click("#btn-sound")
    page.wait_for_timeout(300)
    print("SOUND AFTER 1 CLICK:", json.dumps(page.evaluate("() => ({ label: document.getElementById('sound-label').textContent, muted: document.getElementById('btn-sound').classList.contains('muted') })")))
    page.click("#btn-sound")
    page.wait_for_timeout(300)
    print("SOUND AFTER 2 CLICKS:", json.dumps(page.evaluate("() => ({ label: document.getElementById('sound-label').textContent, muted: document.getElementById('btn-sound').classList.contains('muted') })")))

    # 6. No save/score keys written after playing, and no leaderboard requests.
    print("STORAGE AFTER PLAY:", json.dumps(page.evaluate("""() => ({
      saveKey: window.localStorage.getItem('castle-siege-save-v1'),
      scoresKey: window.localStorage.getItem('castle-siege-local-scores-v1'),
    })""")))
    print("LEADERBOARD REQUESTS:", json.dumps([u for u in all_reqs if 'leaderboard' in u or 'api/scores' in u]) or "none")

    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase6-screenshot.png")
    browser.close()

# Harmless SwiftShader ReadPixels warnings only.
real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")

ok = True
if any(missing.values()):
    print("FAIL: removed save/leaderboard UI still present"); ok = False
for sel, (label, title) in expected.items():
    b = btns.get(sel)
    if not b:
        print("FAIL: missing button", sel); ok = False; continue
    if not (b["iconBtn"] and b["hasSvg"] and b["label"] == label and b["title"] == title):
        print("FAIL: button wrong", sel, b); ok = False
print("RESULT:", "PASS" if ok and not real_errors and not failed_reqs else "FAIL")
sys.exit(0 if ok and not real_errors and not failed_reqs else 1)
