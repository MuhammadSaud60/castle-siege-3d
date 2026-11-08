"""Phase 5 headless test: graphics upgrade renders, particles work, FPS check."""
import json
import sys
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
    fx0 = page.evaluate("() => ({ clouds: window.__castle.fx.clouds(), chimneys: window.__castle.fx.chimneys(), particles: window.__castle.fx.particles() })")
    print("FX ON LOAD:", json.dumps(fx0))
    print("CANVAS:", page.evaluate("() => !!document.querySelector('#app canvas')"))

    # Measure frame rate over 3 seconds (SwiftShader, so this is a floor).
    fps = page.evaluate("""() => new Promise((res) => {
      let n = 0; const t0 = performance.now();
      function f() { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(f); else res((n / 3).toFixed(1)); }
      requestAnimationFrame(f);
    })""")
    print("FPS (headless SwiftShader):", fps)

    # First interaction: click on the canvas centre (unlocks audio).
    page.mouse.click(640, 400)
    page.wait_for_timeout(1000)

    # Place a farm: Build Farm button, then click on open ground.
    page.click("#btn-build-farm")
    page.mouse.click(640, 620)
    page.wait_for_timeout(600)
    print("FARM COUNT:", page.evaluate("() => window.__castle.state.farmCount"))

    # Start a wave and wait for combat: arrows fly, sparks and dust spawn.
    page.click("#btn-next-wave")
    page.wait_for_timeout(1000)
    shot = False
    parts_seen = 0
    for _ in range(30):
        page.wait_for_timeout(2000)
        shoot_state = page.evaluate("() => window.__castle.audio.poolState('shoot')")
        parts_seen = page.evaluate("() => window.__castle.fx.particles()")
        if any(s["time"] > 0 for s in shoot_state) or parts_seen > 0:
            shot = True
            break
    print("SHOOT POOL:", json.dumps(shoot_state))
    print("PARTICLES ALIVE:", parts_seen)
    wave = page.evaluate("() => ({ wave: window.__castle.state.wave, enemies: window.__castle.enemies.length, status: document.getElementById('wave-status').textContent })")
    print("WAVE:", json.dumps(wave))

    # Wide screenshot, then zoom in for a close look at textures.
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase5-screenshot.png")
    page.mouse.move(640, 400)
    page.mouse.wheel(0, -900)
    page.wait_for_timeout(1200)
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase5-screenshot-close.png")
    browser.close()

# Filter the harmless SwiftShader ReadPixels warnings the same way Phase 3 did,
# plus the sandbox egress proxy blocking the (cancelled) leaderboard API:
# the game handles that fetch failure with its local fallback.
real_errors = [
    e for e in errors
    if "ReadPixels" not in e and "GPU stall" not in e
    and "ERR_TUNNEL_CONNECTION_FAILED" not in e
]
real_failed = [r for r in failed_reqs if "castle-siege-3d-api.onrender.com" not in r]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(real_failed, indent=1) if real_failed else "none")

ok = True
if fx0["clouds"] != 6:
    print("FAIL: expected 6 clouds, got", fx0["clouds"]); ok = False
if fx0["chimneys"] < 6:
    print("FAIL: expected at least 6 chimneys, got", fx0["chimneys"]); ok = False
if parts_seen == 0:
    print("FAIL: no particles seen in 60s (smoke/dust should spawn)"); ok = False
if real_errors or real_failed:
    print("FAIL: errors or failed requests present"); ok = False
print("RESULT:", "PASS" if ok else "FAIL")
sys.exit(0 if ok else 1)
