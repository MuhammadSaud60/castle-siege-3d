"""Phase 7 headless test: bigger ground (440) and proper soldier characters."""
import json
import sys
from playwright.sync_api import sync_playwright

URL = "http://localhost:4173/"
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
    print("CANVAS:", page.evaluate("() => !!document.querySelector('#app canvas')"))
    print("GROUND SIZE:", page.evaluate("() => window.__castle.groundSize()"))

    # Measure frame rate over 3 seconds (SwiftShader, so this is a floor).
    fps = page.evaluate("""() => new Promise((res) => {
      let n = 0; const t0 = performance.now();
      function f() { n++; if (performance.now() - t0 < 3000) requestAnimationFrame(f); else res((n / 3).toFixed(1)); }
      requestAnimationFrame(f);
    })""")
    print("FPS (headless SwiftShader):", fps)

    # Placement still works on the bigger ground: build a farm.
    page.mouse.click(640, 400)
    page.wait_for_timeout(800)
    page.click("#btn-build-farm")
    page.mouse.click(640, 620)
    page.wait_for_timeout(600)
    print("FARM COUNT:", page.evaluate("() => window.__castle.state.farmCount"))

    # Start wave 1: 3 enemies spawn at the new far edge with limbs.
    page.click("#btn-next-wave")
    page.wait_for_timeout(800)
    spawn = page.evaluate("""() => window.__castle.enemies.map(e => ({
      dist: Math.round(Math.hypot(e.group.position.x, e.group.position.z)),
      hp: e.hp,
      speed: e.speed,
      hasLimbs: !!e.limbs && !!e.limbs.legL && !!e.limbs.legR && !!e.limbs.armL && !!e.limbs.armR,
      parts: e.group.children.length,
    }))""")
    print("SPAWN:", json.dumps(spawn))
    print("WAVE:", json.dumps(page.evaluate("() => ({ wave: window.__castle.state.wave, enemies: window.__castle.enemies.length, status: document.getElementById('wave-status').textContent })")))

    # Walk animation: a leg's swing angle must change over time.
    leg_a = page.evaluate("() => window.__castle.enemies[0].limbs.legL.rotation.x")
    page.wait_for_timeout(4000)
    leg_b = page.evaluate("() => window.__castle.enemies[0].limbs.legL.rotation.x")
    print("LEG SWING:", leg_a, "->", leg_b, "changed:", abs(leg_a - leg_b) > 0.05)

    # Wide screenshot from a pulled-back camera, showing the bigger ground.
    page.evaluate("""() => {
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(0, 0, 0);
      c.position.set(95, 75, 95);
    }""")
    page.wait_for_timeout(1200)
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase7-screenshot.png")

    # Towers shoot and kill: move one enemy into a corner tower's range and
    # wait for an arrow kill (game time runs slow under SwiftShader).
    page.evaluate("() => { const e = window.__castle.enemies[0]; e.group.position.x = 26; e.group.position.z = 0; }")
    killed = False
    for _ in range(45):
        page.wait_for_timeout(2000)
        if page.evaluate("() => window.__castle.state.kills") > 0:
            killed = True
            break
    print("KILLS:", page.evaluate("() => window.__castle.state.kills"), "killed:", killed)
    print("ARROWS IN FLIGHT:", page.evaluate("() => window.__castle.arrows.length"))
    print("ENEMIES LEFT:", page.evaluate("() => window.__castle.enemies.length"))

    # Close screenshot: frame a surviving soldier up close.
    page.evaluate("""() => {
      const e = window.__castle.enemies[0];
      if (!e) return;
      const p = e.group.position;
      const c = window.__castle.camera, t = window.__castle.controls;
      t.target.set(p.x, p.y + 1.4, p.z);
      c.position.set(p.x + 9, p.y + 5, p.z + 9);
    }""")
    page.wait_for_timeout(1200)
    page.screenshot(path="/home/hatch/workspace/castle-siege-3d/phase7-screenshot-close.png")
    browser.close()

# Filter the harmless SwiftShader ReadPixels warnings.
real_errors = [e for e in errors if "ReadPixels" not in e and "GPU stall" not in e]
print("CONSOLE/PAGE ERRORS:", json.dumps(real_errors, indent=1) if real_errors else "none")
print("FAILED REQUESTS:", json.dumps(failed_reqs, indent=1) if failed_reqs else "none")

ok = True
if len(spawn) != 3:
    print("FAIL: expected 3 enemies, got", len(spawn)); ok = False
for s in spawn:
    if not (120 <= s["dist"] <= 140):
        print("FAIL: enemy spawned at wrong distance", s); ok = False
    if s["hp"] != 2 or not s["hasLimbs"] or s["parts"] < 8:
        print("FAIL: enemy model wrong", s); ok = False
if abs(leg_a - leg_b) <= 0.05:
    print("FAIL: leg swing did not change"); ok = False
if not killed:
    print("FAIL: no tower kill within 90s"); ok = False
print("RESULT:", "PASS" if ok and not real_errors and not failed_reqs else "FAIL")
sys.exit(0 if ok and not real_errors and not failed_reqs else 1)
