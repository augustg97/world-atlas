"""Does the atlas draw on a real GPU what the audits see on a software one? (register G7)

Every other browser audit runs headless Chromium on SwiftShader, so that its pixels do not depend on the
machine. SwiftShader is also more generous than hardware: it allows 32 texture units where WebGL2 guarantees
16, and a seventeenth sampler once linked there and gave a black page on the Mac's own GPU. This audit runs the
same page on the machine's GPU (ANGLE on Metal) and checks three things:

    frames   the six canonical frames (Research/baselines/frames.json), drawn on the GPU, against the ACCEPTED
             software frames beside it. A frame is broken if the page reports an error, if the frame is blank, or
             if it differs from the software frame beyond what two rasterisers differ by (see TOL below).
    lights   the one piece of GL the frames do not reach: js/detail.js writes the streamed night lights into the
             alpha channel of the imagery texture through a framebuffer. Planted pixels go in, and what comes
             back must be the lights rule (detail.js nightLight) of them, with the colour untouched.
    limits   the hardware's texture units, and that the page linked within them.

    "$STUDIO/.venv/bin/python" Research/modeling/audit_gpu.py [--json] [--port 8150] [--keep]   # needs build/serve.py
    "$STUDIO/.venv/bin/python" Research/modeling/audit_gpu.py --selftest

It cannot run without a GPU, and says so: a renderer that is SwiftShader, or no WebGL2, is exit 3 and a
message, never a pass. Lower is better for every key; gpu_broken must be 0.
"""
from __future__ import annotations

import io
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
BASE = os.path.join(ROOT, "Research", "baselines")
OUT = os.path.join(ROOT, "scratchpad", "gpu")

# What two correct rasterisers differ by on these frames, MEASURED (2026-11-10, Apple M5 Ultra on ANGLE Metal against
# SwiftShader): mean difference 0.14 to 0.73 levels of 255 a frame, and 0.03% to 0.59% of pixels more than 24 levels
# apart, all of them on edges: label glyphs, coastlines, tracer streaks (the Atlas sheet, which is mostly edges, is
# the largest). A broken frame is not near these: a missing texture or a failed link moves tens of levels over
# most of the picture, so the tolerance sits five to ten times above the measurement.
TOL = dict(mean_abs=4.0, far_frac=0.06)
FAR = 24            # levels: a pixel this far from the software frame is "far"
BLANK_STD = 3.0     # levels: a frame whose pixels vary less than this is blank

LIGHTS_JS = """async () => {
  const D = await import('/js/detail.js'), A = window.ATLAS, gl = A.gl, det = A.detail;
  const w = 64, h = 32;
  const mk = (fn) => { const c = new OffscreenCanvas(w, h), g = c.getContext('2d', { alpha: false, colorSpace: 'srgb' }); const im = g.createImageData(w, h);
    for (let i = 0; i < w * h; i++) { const [r, gg, b] = fn(i % w, Math.floor(i / w)); im.data[i * 4] = r; im.data[i * 4 + 1] = gg; im.data[i * 4 + 2] = b; im.data[i * 4 + 3] = 255; }
    g.putImageData(im, 0, 0); return c; };
  // day: a colour ramp. night: Black Marble's own run of colours, dark base to white core, and a moonlit desert that is not light
  const NIGHT = [[5, 5, 15], [25, 23, 46], [37, 34, 62], [82, 69, 72], [128, 103, 91], [174, 138, 111], [248, 202, 146], [255, 255, 255]];
  const day = mk((x, y) => [x * 4, y * 8, 200 - x * 2]), night = mk((x, y) => NIGHT[(x + y) % NIGHT.length]);
  const tex = gl.createTexture();
  gl.bindTexture(gl.TEXTURE_2D, tex);
  gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1); gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false); gl.pixelStorei(gl.UNPACK_COLORSPACE_CONVERSION_WEBGL, gl.NONE);
  gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA8, gl.RGBA, gl.UNSIGNED_BYTE, day);
  const before = { blend: gl.isEnabled(gl.BLEND), vp: Array.from(gl.getParameter(gl.VIEWPORT)), mask: gl.getParameter(gl.COLOR_WRITEMASK) };
  det._writeLights(tex, night, w, h);
  const after = { blend: gl.isEnabled(gl.BLEND), vp: Array.from(gl.getParameter(gl.VIEWPORT)), mask: gl.getParameter(gl.COLOR_WRITEMASK) };
  const fb = gl.createFramebuffer(); gl.bindFramebuffer(gl.FRAMEBUFFER, fb);
  gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
  const px = new Uint8Array(w * h * 4); gl.readPixels(0, 0, w, h, gl.RGBA, gl.UNSIGNED_BYTE, px);
  gl.bindFramebuffer(gl.FRAMEBUFFER, null); gl.deleteFramebuffer(fb); gl.deleteTexture(tex);
  let worstA = 0, worstRGB = 0, lit = 0;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    const i = (y * w + x) * 4, n = NIGHT[(x + y) % NIGHT.length], want = D.nightLight(n[0], n[1], n[2]) * 255;
    worstA = Math.max(worstA, Math.abs(px[i + 3] - want)); if (want > 1) lit++;
    worstRGB = Math.max(worstRGB, Math.abs(px[i] - x * 4), Math.abs(px[i + 1] - y * 8), Math.abs(px[i + 2] - (200 - x * 2)));
  }
  return { worstA, worstRGB, lit, restored: JSON.stringify(before) === JSON.stringify(after) };
}"""

INFO_JS = """() => { const gl = window.ATLAS.gl, e = gl.getExtension('WEBGL_debug_renderer_info');
  return { renderer: e ? gl.getParameter(e.UNMASKED_RENDERER_WEBGL) : String(gl.getParameter(gl.RENDERER)), units: gl.getParameter(gl.MAX_TEXTURE_IMAGE_UNITS),
           maxTex: gl.getParameter(gl.MAX_TEXTURE_SIZE), lost: gl.isContextLost(), detailError: window.__DETAIL_ERROR || null }; }"""


def compare(a: np.ndarray, b: np.ndarray) -> dict:
    """Two frames as (h, w, 3) uint8. mean_abs in levels; far_frac the share of pixels more than FAR levels apart in any channel."""
    if a.shape != b.shape:
        return dict(verdict="SHAPE", mean_abs=255.0, far_frac=1.0, std=float(a.std()))
    d = np.abs(a.astype(np.int16) - b.astype(np.int16))
    out = dict(mean_abs=float(d.mean()), far_frac=float((d.max(axis=2) > FAR).mean()), std=float(a.astype(np.float32).std()))
    out["verdict"] = "BLANK" if out["std"] < BLANK_STD else ("DIFFERS" if out["mean_abs"] > TOL["mean_abs"] or out["far_frac"] > TOL["far_frac"] else "ok")
    return out


def run(port: str, as_json: bool, keep: bool) -> dict:
    from playwright.sync_api import sync_playwright
    m = json.load(open(os.path.join(BASE, "frames.json")))
    base = f"http://localhost:{port}"
    vp, ready = m["viewport"], m.get("ready", {})
    rows, errors, info, lights = [], [], None, None
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as pw:
        b = pw.chromium.launch(args=["--use-angle=metal", "--enable-gpu", "--ignore-gpu-blocklist", "--disable-lcd-text", "--force-device-scale-factor=1"])
        ctx = b.new_context(viewport={"width": vp["width"], "height": vp["height"]}, device_scale_factor=m.get("device_scale_factor", 1),
                            reduced_motion="reduce", color_scheme=m.get("color_scheme", "light"))
        for fr in m["frames"]:
            page = ctx.new_page()                                        # a fresh page a frame: a changed fragment alone does not reload
            errs = []
            page.on("console", lambda msg, e=errs: e.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err, e=errs: e.append(str(err)))
            page.goto(base + fr["path"], wait_until="load", timeout=m.get("nav_timeout_ms", 60000))
            try:
                page.wait_for_function(ready.get("expr", "window.__FRAME_READY === true"), timeout=ready.get("timeout_ms", 240000))
            except Exception as exc:  # noqa: BLE001 - a frame that never becomes ready is a finding, reported below
                errs.append(f"never ready: {str(exc)[:120]}")
            page.wait_for_timeout(m.get("settle_ms", 500))
            if info is None:
                info = page.evaluate(INFO_JS)
                if "swiftshader" in info["renderer"].lower() or "llvmpipe" in info["renderer"].lower():
                    b.close()
                    print(f"audit_gpu: COULD NOT RUN. The browser gave a software renderer ({info['renderer']}); this audit needs the machine's GPU.", file=sys.stderr)
                    sys.exit(3)
                lights = page.evaluate(LIGHTS_JS)
            png = page.screenshot(type="png")
            page.close()
            got = np.asarray(Image.open(io.BytesIO(png)).convert("RGB"))
            ref = np.asarray(Image.open(os.path.join(BASE, "frames", fr["name"] + ".png")).convert("RGB"))
            r = compare(got, ref)
            if errs:
                r["verdict"] = "ERROR"
            r.update(frame=fr["name"], errors=list(dict.fromkeys(errs))[:3])
            rows.append(r)
            errors += errs
            if keep or r["verdict"] != "ok":
                Image.fromarray(got).save(os.path.join(OUT, fr["name"] + ".png"))
        b.close()
    lights_ok = lights["worstA"] <= 1.5 and lights["worstRGB"] == 0 and lights["lit"] > 0 and lights["restored"]
    broken = sum(r["verdict"] != "ok" for r in rows) + (0 if lights_ok else 1) + (1 if info["lost"] or info["detailError"] else 0)
    summary = dict(gpu_broken=broken, gpu_worst_mean_abs=round(max(r["mean_abs"] for r in rows), 2), gpu_worst_far_pct=round(100 * max(r["far_frac"] for r in rows), 2))
    if not as_json:
        print(f"the atlas on {info['renderer']}")
        print(f"  texture units: {info['units']} (the earth shader uses 16; build/check_shaders.py holds it there)   largest texture: {info['maxTex']}")
        print("  frame                     verdict   mean diff   pixels > 24 levels apart      (against the accepted software frame)")
        for r in rows:
            print(f"    {r['frame']:24} {r['verdict']:8} {r['mean_abs']:6.2f}      {100 * r['far_frac']:5.2f}%" + ("   " + "; ".join(r["errors"]) if r["errors"] else ""))
        print(f"  lights into alpha: worst alpha error {lights['worstA']:.2f} of 255 over {lights['lit']} lit pixels, colour moved by {lights['worstRGB']}, GL state put back: {lights['restored']}"
              + ("" if lights_ok else "   <-- BROKEN"))
    with open(os.path.join(HERE, "REGISTER-gpu.md"), "w") as fh:
        fh.write(f"# The atlas on a real GPU (audit_gpu.py)\n\nRenderer: {info['renderer']}. Texture units: {info['units']}.\n\n| frame | verdict | mean difference, levels | pixels more than {FAR} levels apart |\n|---|---|---|---|\n")
        for r in rows:
            fh.write(f"| {r['frame']} | {r['verdict']} | {r['mean_abs']:.2f} | {100 * r['far_frac']:.2f}% |\n")
        fh.write(f"\nLights into the imagery texture's alpha: worst error {lights['worstA']:.2f} of 255; colour moved by {lights['worstRGB']}; GL state restored: {lights['restored']}.\n")
    print(json.dumps(summary))
    return summary


def selftest():
    rng = np.random.default_rng(1)
    a = rng.integers(0, 255, (90, 160, 3), dtype=np.uint8)
    assert compare(a, a)["verdict"] == "ok" and compare(a, a)["mean_abs"] == 0.0
    # rasteriser noise: one level everywhere, and 1% of pixels on edges far off. Not broken.
    b = np.clip(a.astype(np.int16) + 1, 0, 255).astype(np.uint8)
    idx = rng.random((90, 160)) < 0.01
    b[idx] = 255 - b[idx]
    r = compare(a, b)
    assert r["verdict"] == "ok" and 0.5 < r["mean_abs"] < TOL["mean_abs"], r
    # a black canvas (the seventeenth sampler) and a missing layer (a third of the frame 40 levels off) are both caught
    assert compare(np.zeros_like(a), a)["verdict"] == "BLANK"
    c = a.copy(); c[:30] = np.clip(c[:30].astype(np.int16) + 40, 0, 255).astype(np.uint8)
    assert compare(c, a)["verdict"] == "DIFFERS", compare(c, a)
    assert compare(a[:, :100], a)["verdict"] == "SHAPE"
    print("audit_gpu selftest: ok")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        run(sys.argv[sys.argv.index("--port") + 1] if "--port" in sys.argv else "8150", "--json" in sys.argv, "--keep" in sys.argv)
