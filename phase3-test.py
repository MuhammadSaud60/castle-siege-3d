"""Phase 3 headless test: audio unlock, music, mute, sounds, zero errors."""
import json
import sys
import time
from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:4173/"
errors = []
failed_reqs = []

with sync_playwright() as p:
    browser = p.chromium.launch(args=["--autoplay-policy=no-user-gesture-required"])
    page = browser.new_page(viewport={"width": 1280, "height": 800})
    page.on("console", lambda m: errors.append(f"console.{m.type}: {m.text}") if m.type == "error" else None)
    page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
    page.on("requestfailed", lambda r: failed_reqs.append(f"{r.url} :: {r.failure}"))
    page.on("response", lambda r: failed_reqs.append(f"{r.url} :: HTTP {r.status}") if r.status >= 400 else None)

    page.goto(URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2500)
    state0 = page.evaluate("() => ({ unlocked: window.__castle.audio.isUnlocked(), muted: window.__castle.audio.isMuted(), musicPaused: window.__castle.audio.musicPaused(), btn: document.getElementById('btn-sound').textContent, pools: window.__castle.audio.poolSizes() })")
    print("BEFORE INTERACTION:", json.dumps(state0))

    # First interaction: click on the canvas centre (unlocks audio, starts music).
    page.mouse.click(640, 400)
    page.wait_for_timeout(1200)
    state1 = page.evaluate("() => ({ unlocked: window.__castle.audio.isUnlocked(), muted: window.__castle.audio.isMuted(), musicPaused: window.__castle.audio.musicPaused(), btn: document.getElementById('btn-sound').textContent })")
    print("AFTER FIRST CLICK:", json.dumps(state1))

    # Mute with the M key, then unmute.
    page.keyboard.press("m")
    page.wait_for_timeout(400)
    state2 = page.evaluate("() => ({ muted: window.__castle.audio.isMuted(), musicPaused: window.__castle.audio.musicPaused(), btn: document.getElementById('btn-sound').textContent })")
    print("AFTER M (muted):", json.dumps(state2))
    page.keyboard.press("m")
    page.wait_for_timeout(400)
    state3 = page.evaluate("() => ({ muted: window.__castle.audio.isMuted(), musicPaused: window.__castle.audio.musicPaused(), btn: document.getElementById('btn-sound').textContent })")
    print("AFTER M AGAIN (unmuted):", json.dumps(state3))

    # Place a farm: Build Farm button, then click on open ground.
    page.click("#btn-build-farm")
    page.mouse.click(640, 620)
    page.wait_for_timeout(600)
    build_state = page.evaluate("() => window.__castle.audio.poolState('build')")
    print("BUILD POOL:", json.dumps(build_state))
    print("FARM COUNT:", page.evaluate("() => window.__castle.state.farmCount"))

    # Start a wave: horn should play, towers should shoot (shoot pool advances).
    page.click("#btn-next-wave")
    page.wait_for_timeout(1000)
    horn_state = page.evaluate("() => window.__castle.audio.poolState('horn')")
    print("HORN POOL:", json.dumps(horn_state))
    # Towers only shoot once enemies walk into range, and game time runs
    # slower than wall clock under SwiftShader, so poll for up to 60s.
    shoot_state = []
    for _ in range(30):
        page.wait_for_timeout(2000)
        shoot_state = page.evaluate("() => window.__castle.audio.poolState('shoot')")
        if any(s["time"] > 0 for s in shoot_state):
            break
    print("SHOOT POOL:", json.dumps(shoot_state))
    wave = page.evaluate("() => ({ wave: window.__castle.state.wave, enemies: window.__castle.enemies.length, status: document.getElementById('wave-status').textContent })")
    print("WAVE:", json.dumps(wave))

    # Mute via the Sound button.
    page.click("#btn-sound")
    page.wait_for_timeout(400)
    state4 = page.evaluate("() => ({ muted: window.__castle.audio.isMuted(), musicPaused: window.__castle.audio.musicPaused(), btn: document.getElementById('btn-sound').textContent })")
    print("AFTER SOUND BUTTON (muted):", json.dumps(state4))

    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase3-screenshot.png")
    browser.close()

print("CONSOLE/PAGE ERRORS:", json.dumps(errors, indent=1) if errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")

ok = True
if state0["unlocked"]:
    print("FAIL: audio unlocked before interaction"); ok = False
if not state1["unlocked"] or state1["musicPaused"]:
    print("FAIL: music did not start after first click"); ok = False
if not (state2["muted"] and state2["musicPaused"] and state2["btn"] == "Sound: Off"):
    print("FAIL: M key did not mute"); ok = False
if not (state3["muted"] is False and not state3["musicPaused"] and state3["btn"] == "Sound: On"):
    print("FAIL: M key did not unmute"); ok = False
if not any(b["time"] > 0 for b in build_state):
    print("FAIL: build sound never played"); ok = False
if not any(h["time"] > 0 for h in horn_state):
    print("FAIL: horn never played"); ok = False
if not any(s["time"] > 0 for s in shoot_state):
    print("FAIL: shoot sound never played"); ok = False
if not (state4["muted"] and state4["musicPaused"]):
    print("FAIL: Sound button did not mute"); ok = False
if errors or failed_reqs:
    print("FAIL: errors or failed requests present"); ok = False
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
