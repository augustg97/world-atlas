"""How many states are named at the whole-Earth framing, against the baseline sheet (register F1).

The National Geographic sheet names every state at this framing. The count comes from the app
itself: the frozen page is opened headless at 1440 x 900 and the label layer is asked what it
actually placed (measure what is drawn, not what is in the data).

    "$STUDIO/.venv/bin/python" Research/modeling/audit_labels.py [--json]     # needs build/serve.py on 8150
"""
import json, sys
from playwright.sync_api import sync_playwright

VIEWS = {"sheet": "/?frozen=1#t=2026-06-21T12:00Z&v=sheet&s=atlas&on=daylight,borders,labels,ice",
         "globe": "/?frozen=1#t=2026-06-21T12:00Z&v=globe&s=space&ll=15,20&on=daylight,clouds,air,ice,lights,borders,labels"}
JS = """() => {
  const states = ATLAS.data.political.countries.filter((c) => c.type === 'Sovereign country' || c.type === 'Country');
  const placed = new Set(ATLAS.labels.placed.filter((p) => p.it.cls === 'country').map((p) => p.it.ref[1].a3));
  return { states: states.length, named: states.filter((c) => placed.has(c.a3)).length, all: ATLAS.labels.placed.length };
}"""

res, detail = {}, {}
with sync_playwright() as pw:
    b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, device_scale_factor=1)
    for name, path in VIEWS.items():
        page = ctx.new_page()
        page.goto("http://localhost:8150" + path, wait_until="load", timeout=120000)
        page.wait_for_function("window.__FRAME_READY === true", timeout=240000)
        d = page.evaluate(JS)
        detail[name] = d
        page.close()
    b.close()
# on the globe only about half the states face the camera, so only the sheet is held to "all of them"
res["sheet_states_unnamed"] = detail["sheet"]["states"] - detail["sheet"]["named"]
res["sheet_states_named"] = detail["sheet"]["named"]
res["globe_states_named"] = detail["globe"]["named"]
if "--json" not in sys.argv:
    for k, d in detail.items():
        print(f"{k}: {d['named']} of {d['states']} states named; {d['all']} labels placed in all")
print(json.dumps(res))
