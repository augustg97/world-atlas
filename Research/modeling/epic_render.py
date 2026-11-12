"""Render the atlas from NASA EPIC's eight camera positions, headless, so the EPIC audit can run
without a person at a browser.

    "$STUDIO/.venv/bin/python" Research/modeling/epic_render.py [tag] [layers]   # needs build/serve.py running on 8150

`layers` is a comma list of the layers left on (default clouds,air,daylight,ice). `clr air,daylight,ice`
renders with clouds off, for the clear-sky composite (epic_clearsky.py).

Playwright lives in the Modeling Studio venv, not the project's. Software GL (swiftshader), so the
pixels do not depend on the machine. Writes scratchpad/epic_<tag>_<frame>.jpg through the dev
server's /__shot endpoint; epic_compare.py --tag <tag> scores them.
"""
import os
import sys
from playwright.sync_api import sync_playwright

tag = sys.argv[1] if len(sys.argv) > 1 else "cur"
layers = sys.argv[2].split(",") if len(sys.argv) > 2 else None
base = "http://localhost:" + os.environ.get("ATLAS_PORT", "8150")
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    page = b.new_context(viewport={"width": 1024, "height": 1024}, device_scale_factor=2).new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    page.goto(base + "/?frozen=1#t=2025-03-20T10:56Z&v=globe&s=space&on=clouds,air,daylight,ice", wait_until="load", timeout=120000)
    page.wait_for_function("window.__FRAME_READY === true", timeout=240000)
    out = page.evaluate("async ([tag, on]) => { const m = await import('/js/refshots.js'); return on ? m.renderEpic(tag, on) : m.renderEpic(tag); }", [tag, layers])
    b.close()
for line in out:
    print(line)
if errors:
    print("console errors:", *dict.fromkeys(errors), sep="\n  ")
    sys.exit(1)
