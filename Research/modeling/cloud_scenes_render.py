"""Render the atlas over the five cloud-texture scenes (cloud_texture.py), headless, at 2 km a pixel.

    "$STUDIO/.venv/bin/python" Research/modeling/cloud_scenes_render.py [tag]      # needs build/serve.py on 8150

Each scene is rendered at 13:30 local solar time on the first of its reference days, clouds, air and
daylight on, nothing else: no labels, no borders, no streamed detail (the frame must not depend on the
network). The two Southern Ocean scenes (cloud_texture.EXTRA) are rendered without the air: see there. Writes scratchpad/cloudscene_<tag>_<scene>.jpg through the dev server.
"""
import importlib.util
import os
import sys

from playwright.sync_api import sync_playwright

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("scenes_src", os.path.join(HERE, "cloud_texture.py"))
tag = sys.argv[1] if len(sys.argv) > 1 else "cur"

# cloud_texture imports numpy and PIL, which the Studio venv has; only its SCENES table is needed
ct = importlib.util.module_from_spec(spec); spec.loader.exec_module(ct)

with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    ctx = b.new_context(viewport={"width": ct.PX, "height": ct.PX}, device_scale_factor=1)
    for name, (lon, lat, days) in {**ct.SCENES, **ct.EXTRA}.items():
        h = (13.5 - lon / 15.0) % 24
        t = f"{days[0]}T{int(h):02d}:{int((h % 1) * 60):02d}Z"
        page = ctx.new_page()
        errors = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(f"http://localhost:{os.environ.get('ATLAS_PORT', '8150')}/?frozen=1#t={t}&v=globe&s=space&ll={lon},{lat}&km={ct.KM}&on={'daylight,clouds' if name in ct.EXTRA else 'daylight,clouds,air'}", wait_until="load", timeout=120000)
        page.wait_for_function("window.__FRAME_READY === true", timeout=240000)
        # the panels sit over the canvas in a screenshot; ATLAS.shot writes the canvas alone
        out = page.evaluate("async (n) => { ATLAS.step(3); return await ATLAS.shot(n); }", f"cloudscene_{tag}_{name}.jpg")
        print(name, t, out)
        if errors:
            print("  page errors:", *dict.fromkeys(errors), sep="\n    ")
            sys.exit(1)
        page.close()
    b.close()
