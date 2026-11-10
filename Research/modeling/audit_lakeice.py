"""Lake ice against the lakes' own records (register A5).

The witness is NSIDC's Global Lake and River Ice Phenology Database (G01377; Benson, Magnuson & Sharma):
the dates each lake froze over and opened, season by season, kept by people who watched it. For every
lake with at least ten seasons from 1980-81 to 2019-20 it gives how much of each month the lake is iced
in a typical year, which is the quantity the atlas draws. Nothing from it is shipped.

Two things are scored against it.

    the model     build/lakeice.py, fed the air temperature the atlas has at each lake. Its two fitted
                  numbers come from HALF the lakes (--fit prints them); the scores are on the other half.
    the atlas     the ice the shipped field (web/fields/oceanA.png) holds at each lake: what is drawn.

    mae           mean, over lakes and the twelve months, of |share of the month iced, atlas - record|
    days          mean over lakes of |days iced a year, atlas - record|

    ./venv/bin/python Research/modeling/audit_lakeice.py [--json] [--fit] [--register]
    ./venv/bin/python Research/modeling/audit_lakeice.py --selftest
"""
from __future__ import annotations

import argparse
import csv
import datetime
import json
import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "build"))
import frames as F  # noqa: E402
import lakeice as LI  # noqa: E402

SRC = os.path.join(ROOT, "data", "lakeice")
DAYS = np.array([31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])
FIRST, LAST, MIN_SEASONS = 1980, 2019, 10


def season_months(on, off):
    """Share of each calendar month iced in one season. on, off: dates, or None for a season with no ice.
    The season runs from 1 July to 30 June (every lake in the database is north of the equator)."""
    out = np.zeros(12)
    if on is None or off is None or off <= on:
        return out
    d = on
    while d < off:
        out[d.month - 1] += 1
        d += datetime.timedelta(days=1)
    return np.minimum(out / DAYS, 1.0)


def witness():
    """lakecode -> dict(name, lat, lon, elev, months (12,), seasons, area)."""
    phys = {r["lakecode"]: r for r in csv.DictReader(open(os.path.join(SRC, "liag_physical_character_table.csv"), encoding="latin-1"))}
    acc = {}
    for r in csv.DictReader(open(os.path.join(SRC, "liag_freeze_thaw_table.csv"), encoding="latin-1")):
        if r["lakeorriver"] != "L" or not r["season"][:4].isdigit():
            continue
        y = int(r["season"][:4])
        if not FIRST <= y <= LAST:
            continue
        iv = lambda k: int(float(r[k]))
        a = acc.setdefault(r["lakecode"], dict(name=r["lakename"], lat=float(r["latitude"]), lon=float(r["longitude"]), sum=np.zeros(12), n=0, froze=0, used=0))
        a["froze"] += r["froze"] == "Y"
        if r["froze"] == "N":
            m = np.zeros(12)
        elif r["froze"] == "Y" and min(iv("iceon_year"), iv("iceon_month"), iv("iceon_day"), iv("iceoff_year"), iv("iceoff_month"), iv("iceoff_day")) > 0:
            try:
                on = datetime.date(iv("iceon_year"), iv("iceon_month"), iv("iceon_day")); off = datetime.date(iv("iceoff_year"), iv("iceoff_month"), iv("iceoff_day"))
            except ValueError:
                continue
            if not 0 < (off - on).days < 330:
                continue
            m = season_months(on, off)
        else:
            continue                                         # a season with a date missing says nothing usable
        a["sum"] += m; a["n"] += 1; a["used"] += r["froze"] == "Y"
    out = {}
    for k, a in acc.items():
        if a["n"] < MIN_SEASONS or not (-90 <= a["lat"] <= 90 and -180 <= a["lon"] <= 180):
            continue
        # A lake whose frozen seasons mostly lack a date would be averaged over its open seasons alone and
        # come out as a lake that never freezes (Lake Champlain did: 0 days, from a record whose frozen seasons carry no dates).
        if a["froze"] and a["used"] < 0.8 * a["froze"]:
            continue
        p = phys.get(k, {})
        num = lambda key: (float(p[key]) if p.get(key) not in (None, "", "-", "-999") and float(p[key]) > -900 else None)
        out[k] = dict(name=a["name"], lat=a["lat"], lon=a["lon"], months=a["sum"] / a["n"], seasons=a["n"], elev=num("elevation"), area=num("surface_area"), depth=num("mean_depth"))
    return out


def half(code):
    """Which half a lake is in: 0 to fit on, 1 to test on. Fixed by its code, not by a random draw."""
    return sum(code.encode()) % 2


def temperature(lakes):
    """(12, n) monthly mean air temperature at each lake, as the build computes it for a lake cell."""
    import fields_climate as C
    t0 = C.land_air_t0()
    e4 = np.load(os.path.join(C.CACHE, "elev4.npy"))
    out = np.zeros((12, len(lakes)))
    for i, lk in enumerate(lakes):
        x = (lk["lon"] + 180.0) % 360.0 - 0.5; y = 89.5 - lk["lat"]
        x0 = int(np.floor(x)); y0 = int(np.clip(np.floor(y), 0, 178)); fx = x - x0; fy = np.clip(y - y0, 0, 1)
        c = lambda yy, xx: t0[:, yy, xx % 360]
        t = (c(y0, x0) * (1 - fx) + c(y0, x0 + 1) * fx) * (1 - fy) + (c(y0 + 1, x0) * (1 - fx) + c(y0 + 1, x0 + 1) * fx) * fy
        ii, jj = F.lonlat_to_px(lk["lon"], lk["lat"], e4.shape[1], e4.shape[0])
        z = lk["elev"] if lk["elev"] is not None else max(float(e4[jj, ii]), 0.0)
        out[:, i] = t - C.LAPSE * z / 1000.0
    return out


def score(pred, obs):
    """pred, obs: (12, n). mae over months and lakes; mean |days iced a year| difference; mean signed days."""
    d = (pred * DAYS[:, None]).sum(0) - (obs * DAYS[:, None]).sum(0)
    return float(np.abs(pred - obs).mean()), float(np.abs(d).mean()), float(d.mean())


def shipped_at(lakes):
    """(12, n) ice the shipped field holds at each lake, and (n,) whether the field marks the cell as water it has ice for."""
    Image.MAX_IMAGE_PIXELS = None
    a = np.asarray(Image.open(os.path.join(ROOT, "web", "fields", "oceanA.png")))
    W = a.shape[1]; H = a.shape[0] // 12
    ice = np.zeros((12, len(lakes))); ok = np.zeros(len(lakes), bool)
    for i, lk in enumerate(lakes):
        ii, jj = F.lonlat_to_px(lk["lon"], lk["lat"], W, H)
        ice[:, i] = a[jj::H, ii, 1][:12] / 255.0
        ok[i] = a[jj, ii, 2] >= 128
    return ice, ok


def run(as_json=False, fit=False, register=False):
    wit = witness()
    codes = sorted(wit)
    lakes = [wit[c] for c in codes]
    obs = np.stack([lk["months"] for lk in lakes], 1)
    tm = temperature(lakes)
    hv = np.array([half(c) for c in codes])
    if fit:
        best = None
        for lag in (6, 10, 14, 18, 24, 30, 38, 48, 60):
            for melt in (0.003, 0.004, 0.0055, 0.007, 0.009, 0.012):
                p = LI.monthly_ice(tm[:, hv == 0], lag=lag, melt=melt)
                s = score(p, obs[:, hv == 0])
                if best is None or s[0] < best[0][0]:
                    best = (s, lag, melt)
                print(f"  lag {lag:3d}  melt {melt:.4f}   mae {s[0]:.4f}  days {s[1]:5.1f} ({s[2]:+.1f})")
        print(f"fitted on {int((hv == 0).sum())} lakes:  LAG = {best[1]}   MELT = {best[2]}   (mae {best[0][0]:.4f})")
        return
    pred = LI.monthly_ice(tm)
    s_fit, s_test = score(pred[:, hv == 0], obs[:, hv == 0]), score(pred[:, hv == 1], obs[:, hv == 1])
    ice, ok = shipped_at(lakes)
    s_ship = score(ice[:, ok], obs[:, ok]) if ok.any() else (float("nan"),) * 3
    never = score(np.zeros_like(obs), obs)                                         # what "lakes never freeze" scores
    out = dict(lakeice_test_mae=round(s_test[0], 4), lakeice_test_days=round(s_test[1], 1), lakeice_shipped_mae=round(s_ship[0], 4),
               lakeice_shipped_days=round(s_ship[1], 1), lakeice_undrawn=int((~ok).sum()))
    if not as_json:
        print(f"lake ice against {len(lakes)} lakes' own records, 1980-81 to 2019-20 (NSIDC G01377)")
        print(f"  the model, on the {int((hv == 0).sum())} lakes it was fitted to:  mae {s_fit[0]:.3f} of a month, {s_fit[1]:.0f} days a year ({s_fit[2]:+.0f} mean)")
        print(f"  the model, on the {int((hv == 1).sum())} lakes it never saw:      mae {s_test[0]:.3f} of a month, {s_test[1]:.0f} days a year ({s_test[2]:+.0f} mean)")
        print(f"  what the atlas draws, at the {int(ok.sum())} lakes it has ice for: mae {s_ship[0]:.3f} of a month, {s_ship[1]:.0f} days a year ({s_ship[2]:+.0f} mean);  {int((~ok).sum())} lakes in cells it draws no ice in")
        print(f"  for scale, lakes that never freeze would score:           mae {never[0]:.3f} of a month, {never[1]:.0f} days a year")
        print("  month by month, share iced, record then model (all lakes): " + " ".join(f"{a:.2f}/{b:.2f}" for a, b in zip(obs.mean(1), pred.mean(1))))
        d = (pred * DAYS[:, None]).sum(0) - (obs * DAYS[:, None]).sum(0)
        for i in np.argsort(-np.abs(d))[:8]:
            print(f"    {lakes[i]['name'][:34]:34} {lakes[i]['lat']:6.2f} {lakes[i]['lon']:8.2f}  record {(obs[:, i] * DAYS).sum():4.0f} days  model {(pred[:, i] * DAYS).sum():4.0f}")
    if register:
        d = (pred * DAYS[:, None]).sum(0) - (obs * DAYS[:, None]).sum(0)
        with open(os.path.join(HERE, "REGISTER-lakeice.md"), "w") as fh:
            fh.write("# Lake ice against NSIDC G01377 (audit_lakeice.py)\n\n")
            fh.write("Records: Benson, B., Magnuson, J. and Sharma, S. (2000, updated 2020). Global Lake and River Ice Phenology Database, "
                     "Version 1. NSIDC, doi:10.7265/N5W66HP8. The 'record' column is a mean computed here from its freeze and thaw dates, 1980-81 to 2019-20.\n\n")
            fh.write(f"{len(lakes)} lakes. Test half: mae {s_test[0]:.3f} of a month, {s_test[1]:.0f} days a year. Shipped field: mae {s_ship[0]:.3f}, {s_ship[1]:.0f} days.\n\n")
            fh.write("| lake | lat | lon | seasons | days iced, record | model | shipped | half |\n|---|---|---|---|---|---|---|---|\n")
            for i in np.argsort(-np.abs(d)):
                fh.write(f"| {lakes[i]['name']} | {lakes[i]['lat']:.2f} | {lakes[i]['lon']:.2f} | {lakes[i]['seasons']} | {(obs[:, i] * DAYS).sum():.0f} | {(pred[:, i] * DAYS).sum():.0f} | {(ice[:, i] * DAYS).sum():.0f} | {'test' if hv[i] else 'fit'} |\n")
    print(json.dumps(out))
    return out


def selftest():
    # season_months: frozen 15 December to 15 April is half of December, all of January to March, half of April
    m = season_months(datetime.date(2000, 12, 16), datetime.date(2001, 4, 16))
    assert abs(m[11] - 16 / 31) < 1e-9 and m[0] == 1 and m[1] == 1 and m[2] == 1 and abs(m[3] - 15 / 30) < 1e-9 and m[5:11].sum() == 0, m
    assert season_months(None, None).sum() == 0
    # score: a prediction a month too long everywhere is off by about 30 days and a twelfth in mae
    obs = np.zeros((12, 4)); obs[[11, 0, 1]] = 1.0
    pred = obs.copy(); pred[2] = 1.0
    s = score(pred, obs)
    assert abs(s[0] - 1 / 12) < 1e-9 and abs(s[1] - 31) < 1e-9 and s[2] > 0, s
    # the halves are fixed and roughly even
    codes = [f"AB{i}" for i in range(200)]
    assert 70 < sum(half(c) for c in codes) < 130 and half("NG1") == half("NG1")
    LI.selftest()
    # the real table: a lake kept has dates for at least four fifths of the seasons it froze
    if os.path.exists(os.path.join(SRC, "liag_freeze_thaw_table.csv")):
        w = witness()
        assert len(w) > 150 and not any("CHAMPLAIN" in v["name"] for v in w.values()), "a lake with undated frozen seasons must not be scored as never freezing"
    print("audit_lakeice selftest: ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true"); ap.add_argument("--fit", action="store_true")
    ap.add_argument("--register", action="store_true"); ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    else:
        run(a.json, a.fit, a.register)
