"""Sea-ice extent in the shipped field against the NSIDC Sea Ice Index (register C1).

Reads web/fields/oceanA.png exactly as the dashboard does (web/js/dash.js, iceExtents): a cell
counts when it is valid ocean and its concentration is at least 15%. The witness is NSIDC's own
1991-2020 monthly mean extent, in Research/modeling/witness/ (computed from NSIDC's yearly files).

The atlas ships the mean CONCENTRATION field; the extent of a mean field is larger than the mean
of yearly extents, because any cell iced in a third of the years still clears 15%. So this is a
known overshoot, held by the ratchet until the climatology is rebuilt per year.

    ./venv/bin/python Research/modeling/audit_ice.py [--json] [--selftest]
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
R_KM = 6371.0088
Image.MAX_IMAGE_PIXELS = None


def extents(stack, lo, hi):
    """stack: (12, h, w, 3) uint8 with G = ice, B = valid. Returns (north[12], south[12]) in M km2."""
    _, h, w, _ = stack.shape
    thr = (0.15 - lo) / (hi - lo) * 255
    cell = np.pi / h
    lat = np.pi / 2 - (np.arange(h) + 0.5) * cell
    area = R_KM ** 2 * (2 * np.pi / w) * (np.sin(lat + cell / 2) - np.sin(lat - cell / 2))
    iced = (stack[..., 2] > 127) & (stack[..., 1] >= thr)
    rows = iced.sum(2) * area[None, :]
    return rows[:, lat > 0].sum(1) / 1e6, rows[:, lat <= 0].sum(1) / 1e6


def selftest():
    s = np.zeros((12, 180, 360, 3), np.uint8); s[..., 2] = 255
    s[:, :10, :, 1] = 255                                       # a cap from 80N to the pole
    n, so = extents(s, 0.0, 1.0)
    cap = 2 * np.pi * R_KM ** 2 * (1 - np.sin(np.radians(80))) / 1e6
    assert abs(n[0] - cap) < 0.01 and so[0] == 0, (n[0], cap)
    s[:, :10, :, 1] = 30                                        # 12% concentration: below the threshold
    assert extents(s, 0.0, 1.0)[0][0] == 0
    print("audit_ice selftest: ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    meta = json.load(open(os.path.join(ROOT, "web", "fields", "climate.json")))
    enc = meta["encodings"]["ice"]; at = meta["atlases"]["oceanA"]
    im = np.asarray(Image.open(os.path.join(ROOT, "web", "fields", at["file"])).convert("RGB"))
    stack = im.reshape(12, at["h"], at["w"], 3)
    n, s = extents(stack, enc["lo"], enc["hi"])
    w = json.load(open(os.path.join(HERE, "witness", "nsidc_extent_1991_2020.json")))
    wn, ws = np.array(w["north"]), np.array(w["south"])
    en, es = (n - wn) / wn * 100, (s - ws) / ws * 100
    res = {"arctic_max_over_pct": round(float(np.abs(en).max()), 1), "antarctic_max_over_pct": round(float(np.abs(es).max()), 1),
           "mean_abs_pct": round(float(np.concatenate([np.abs(en), np.abs(es)]).mean()), 1)}
    lines = ["# Sea-ice extent: shipped field against NSIDC (1991-2020 means), million km2", "",
             "| month | Arctic atlas | NSIDC | error | Antarctic atlas | NSIDC | error |", "|---|---|---|---|---|---|---|"]
    for m, name in enumerate("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()):
        lines.append(f"| {name} | {n[m]:.2f} | {wn[m]:.2f} | {en[m]:+.0f}% | {s[m]:.2f} | {ws[m]:.2f} | {es[m]:+.0f}% |")
    lines += ["", f"Largest error: Arctic {res['arctic_max_over_pct']}%, Antarctic {res['antarctic_max_over_pct']}%; mean absolute {res['mean_abs_pct']}%.", ""]
    open(os.path.join(HERE, "REGISTER-ice.md"), "w").write("\n".join(lines))
    if "--json" not in sys.argv:
        print("\n".join(lines))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
