"""Sea-ice extent in the shipped field against the NSIDC Sea Ice Index (register C1).

Reads web/fields/oceanA.png exactly as the dashboard does (web/js/dash.js, iceExtents): a cell
counts when it is valid ocean and its concentration is at least 15%. The witness is NSIDC's own
1991-2020 mean of its monthly extents, in Research/modeling/witness/ (from NSIDC's yearly tables).

What this audit can and cannot say, since the field was rebuilt from NSIDC's per-year grids
(build/fields_climate.py, ice_typical_year, 2026-11-10):

  The build SOLVES for this number. It ranks cells by how often they are iced and takes them
  until the area, counted the way this audit counts it, reaches NSIDC's mean extent. So the
  table below is near zero by construction. It is a regression guard on the shipped bytes (the
  encoding, the mask, a rebuild that went wrong), not independent evidence that the ice is in
  the right place.

  The independent evidence is the per-year check (--peryear, needs data/nsidc): each of the 720
  monthly grids is converted on its own, with a fixed 15% threshold and no fitting, and its extent
  on the canonical raster is compared with the same grid counted on NSIDC's cells. That tests the
  projection, the resampling and the coast handling. Its results are kept in
  witness/nsidc_peryear_check.json and summarised in the register.

  The ice AREA column (concentration times cell area inside the 15% line, against NSIDC's mean
  monthly area) is not solved for. It runs low where the ice is somewhere else every year: the
  shipped concentration is the 30-year mean, which is diluted by the open years, and the ice
  that lies outside the typical line in any one year is not in it.

The old explanation here (a mean concentration field overshoots because a cell iced in a third of
the years clears 15%) was true of the OISST field this replaced, but it was not the whole of it:
OISST's ice ran 9-92% over however it was thresholded. Both are gone.

    ./venv/bin/python Research/modeling/audit_ice.py [--json] [--selftest] [--peryear]
"""
import json, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
R_KM = 6371.0088
Image.MAX_IMAGE_PIXELS = None


def extents(stack, lo, hi):
    """stack: (12, h, w, 3) uint8 with G = ice, B = valid (255 sea, 200 inland water, which is not counted:
    NSIDC's is a sea-ice index). Returns (north[12], south[12]) in M km2."""
    _, h, w, _ = stack.shape
    thr = (0.15 - lo) / (hi - lo) * 255
    cell = np.pi / h
    lat = np.pi / 2 - (np.arange(h) + 0.5) * cell
    area = R_KM ** 2 * (2 * np.pi / w) * (np.sin(lat + cell / 2) - np.sin(lat - cell / 2))
    iced = (stack[..., 2] > 227) & (stack[..., 1] >= thr)
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


MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
BEFORE = "Before 2026-11-10 (NOAA OISST long-term-mean ice): largest error Arctic 31.5%, Antarctic 93.5%; mean absolute 29.3%."


def areas(stack, lo, hi):
    """Ice AREA (million km2): concentration x cell area over the cells extents() counts."""
    _, h, w, _ = stack.shape
    thr = (0.15 - lo) / (hi - lo) * 255
    cell = np.pi / h
    lat = np.pi / 2 - (np.arange(h) + 0.5) * cell
    area = R_KM ** 2 * (2 * np.pi / w) * (np.sin(lat + cell / 2) - np.sin(lat - cell / 2))
    conc = lo + (hi - lo) * stack[..., 1] / 255.0
    rows = (np.where((stack[..., 2] > 227) & (stack[..., 1] >= thr), conc, 0.0)).sum(2) * area[None, :]
    return rows[:, lat > 0].sum(1) / 1e6, rows[:, lat <= 0].sum(1) / 1e6


def peryear():
    """Recompute the per-year conversion check and the typical-year diagnostics from data/nsidc and
    write them, with NSIDC's per-year tables, into witness/. Uses the build's own code path."""
    sys.path.insert(0, os.path.join(ROOT, "build"))
    import fields_climate as C
    import frames as F
    W, H = 1440, 720
    sst, lon, lat = C.psl_months("sst.mon.ltm.nc", "sst", "noaa.oisst.v2.highres/sst.mon.ltm.1991-2020.nc")
    valid = ~np.isnan(F.resample_grid(sst[:1], lon, lat, W, H))[0]
    water = F.reduce_aligned(np.load(os.path.join(C.CACHE, "water4.npy")).astype(np.float32), W, H)
    frames, stacks, tables = {}, {}, {}
    for letter, grid in C._HEMI:
        stacks[letter] = C.nsidc_stack(letter, grid)
        frames[letter] = C.IceFrame(grid, valid, water, W, H)
        frames[letter].set_ocean(~np.isnan(stacks[letter][0, 0]))
        ext, area = C.nsidc_extent_csv(letter)
        tables[grid["name"]] = {"extent": [[float(x) for x in r] for r in ext], "area": [[float(x) for x in r] for r in area],
                                "extent_mean": [round(float(x), 3) for x in ext.mean(0)], "area_mean": [round(float(x), 3) for x in area.mean(0)]}
    src = {"source": "NSIDC Sea Ice Index, Version 4 (G02135): Fetterer, Knowles, Meier, Savoie, Windnagel, Stafford (2025), doi:10.7265/a98x-0f50",
           "url": "https://noaadata.apps.nsidc.org/NOAA/G02135/", "years": [C.ICE_YEARS[0], C.ICE_YEARS[-1]], "units": "million km2"}
    json.dump({**src, "files": "north|south/monthly/data/{N|S}_{MM}_extent_v4.0.csv; rows are years 1991..2020, columns January..December",
               "note": "NSIDC's monthly extent is the mean of that month's daily extents; area excludes the Arctic pole hole, extent includes it.",
               **tables}, open(os.path.join(HERE, "witness", "nsidc_extent_per_year_1991_2020.json"), "w"), indent=1)
    chk = C.ice_peryear_check(frames, stacks, verbose=False)
    _, _, diag = C.ice_typical_year(frames, stacks, verbose=False)
    for v in chk.values():                                  # the per-year tables live in the file above
        v.pop("nsidc_csv_extent_mkm2")
    json.dump({**src, "files": "north|south/monthly/geotiff/{MM}_{Mon}/{N|S}_{YYYYMM}_concentration_v4.0.tif, 720 files",
               "what": "per_year: every monthly grid on its own, 15% threshold, nearest-cell conversion, no fitting; percent error in extent. "
                       "canonical_vs_native = canonical raster with the atlas ocean mask and coast fill against the same grid on NSIDC's cells with true cell areas. "
                       "projection_only = canonical raster with no atlas mask. native_vs_nsidc_csv = the monthly-mean grid against NSIDC's published extent (mean of daily extents). "
                       "typical_year: the shipped construction, by month.",
               "per_year": chk, "typical_year": diag}, open(os.path.join(HERE, "witness", "nsidc_peryear_check.json"), "w"), indent=1)
    for name in ("north", "south"):
        for k in ("projection_only_vs_native_pct", "canonical_vs_native_pct", "native_vs_nsidc_csv_pct", "canonical_vs_nsidc_csv_pct"):
            v = chk[name][k]
            print(f"  {name:5s} {k:32s} median {v['median']:+6.2f}  p05 {v['p05']:+6.2f}  p95 {v['p95']:+6.2f}  worst {v['worst']:+6.2f}")
    print("wrote witness/nsidc_extent_per_year_1991_2020.json, witness/nsidc_peryear_check.json")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    if "--peryear" in sys.argv:
        peryear()
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
    for m, name in enumerate(MONTHS):
        lines.append(f"| {name} | {n[m]:.2f} | {wn[m]:.2f} | {en[m]:+.2f}% | {s[m]:.2f} | {ws[m]:.2f} | {es[m]:+.2f}% |")
    lines += ["", f"Largest error: Arctic {res['arctic_max_over_pct']}%, Antarctic {res['antarctic_max_over_pct']}%; mean absolute {res['mean_abs_pct']}%.", "",
              BEFORE, "",
              "The build solves for this table (it takes the most often iced cells until their area reaches NSIDC's mean extent), so it guards the shipped "
              "bytes and is not independent evidence. The sections below are.", ""]

    py = os.path.join(HERE, "witness", "nsidc_extent_per_year_1991_2020.json")
    if os.path.exists(py):
        t = json.load(open(py))
        an, as_ = areas(stack, enc["lo"], enc["hi"])
        tn, ts = np.array(t["north"]["area_mean"]), np.array(t["south"]["area_mean"])
        res["area_max_under_pct"] = round(float(max(np.abs((an - tn) / tn).max(), np.abs((as_ - ts) / ts).max()) * 100), 1)
        lines += ["## Ice area (concentration x cell area inside the 15% line), not solved for", "",
                  "| month | Arctic atlas | NSIDC | error | Antarctic atlas | NSIDC | error |", "|---|---|---|---|---|---|---|"]
        for m, name in enumerate(MONTHS):
            lines.append(f"| {name} | {an[m]:.2f} | {tn[m]:.2f} | {(an[m] - tn[m]) / tn[m] * 100:+.1f}% | {as_[m]:.2f} | {ts[m]:.2f} | {(as_[m] - ts[m]) / ts[m] * 100:+.1f}% |")
        lines += ["", "The shipped concentration is the 30-year mean inside the typical line. Where the ice is somewhere else every year (the Antarctic summer) "
                      "that mean is diluted by the open years, and the ice outside the line in any one year is not counted, so area runs low there. "
                      "NSIDC's area leaves out the Arctic pole hole (0.03-0.31 million km2 in these years); the atlas fills it.", ""]

    pc = os.path.join(HERE, "witness", "nsidc_peryear_check.json")
    if os.path.exists(pc):
        c = json.load(open(pc))
        lines += ["## Per-year check of the conversion (720 monthly grids, each on its own, 15% threshold, no fitting)", "",
                  "Percent error in extent. `--peryear` recomputes this from data/nsidc.", "",
                  "| comparison | hemisphere | median | 5th pct | 95th pct | worst |", "|---|---|---|---|---|---|"]
        for key, label in (("projection_only_vs_native_pct", "canonical raster, no atlas mask, against the grid on NSIDC's own cells"),
                           ("canonical_vs_native_pct", "canonical raster as the dashboard counts (atlas ocean mask, coast fill), against the grid on NSIDC's own cells"),
                           ("native_vs_nsidc_csv_pct", "the monthly-mean grid on NSIDC's own cells, against NSIDC's published monthly extent"),
                           ("canonical_vs_nsidc_csv_pct", "canonical raster as the dashboard counts, against NSIDC's published monthly extent")):
            for name in ("north", "south"):
                v = c["per_year"][name][key]
                lines.append(f"| {label} | {name} | {v['median']:+.2f} | {v['p05']:+.2f} | {v['p95']:+.2f} | {v['worst']:+.2f} |")
        lines += ["",
                  "Row 1 is the projection alone. It is not zero because the atlas measures area on a 6371.0088 km sphere and NSIDC on the Hughes ellipsoid: "
                  "spherical cells poleward of 60 degrees are 0.7-0.9% smaller (build/test_frames.py asserts the figure).",
                  "Row 2 adds the atlas's ocean mask: it gains the fjords and channels NSIDC's 25 km mask calls coast and loses the cells OISST calls land.",
                  "Row 3 has no conversion in it at all. NSIDC's monthly extent is the mean of the daily extents; a monthly-mean grid clears 15% wherever ice sat "
                  "for a fifth of the month, so it overshoots most in the months the edge moves fastest (Arctic October, Antarctic March and December).", "",
                  "## Why the 15% line is not the median ice edge", "",
                  "Million km2, counted on NSIDC's cells. The shipped line is the ice-frequency contour that encloses NSIDC's mean extent; "
                  "`frequency` is the share of the thirty years iced at that line (0.50 would be the median edge).", ""]
        for name, title in (("north", "Arctic"), ("south", "Antarctic")):
            d = c["typical_year"][name]; tg = np.array(d["target_mkm2"])
            lines += [f"| {title} | " + " | ".join(MONTHS) + " |", "|---|" + "---|" * 12,
                      "| NSIDC mean of yearly extents | " + " | ".join(f"{x:.2f}" for x in tg) + " |",
                      "| mean concentration >= 15% | " + " | ".join(f"{(x - t) / t * 100:+.0f}%" for x, t in zip(d["mean_field_native_mkm2"], tg)) + " |",
                      "| median ice edge | " + " | ".join(f"{(x - t) / t * 100:+.0f}%" for x, t in zip(d["median_edge_native_mkm2"], tg)) + " |",
                      "| shipped line | " + " | ".join(f"{(x - t) / t * 100:+.1f}%" for x, t in zip(d["shipped_mkm2"], tg)) + " |",
                      "| frequency at the shipped line | " + " | ".join(f"{x:.2f}" for x in d["level_frequency"]) + " |",
                      "| iced cells borrowed at coasts | " + " | ".join(f"{x:.2f}" for x in d["borrowed_iced_mkm2"]) + " |",
                      "| iced NSIDC cells the atlas calls land | " + " | ".join(f"{x:.2f}" for x in d["observed_lost_mkm2"]) + " |", ""]
    open(os.path.join(HERE, "REGISTER-ice.md"), "w").write("\n".join(lines))
    if "--json" not in sys.argv:
        print("\n".join(lines))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
