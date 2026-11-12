"""What cloud looks like at the zoom floor: the atlas against real satellite scenes at 2 km a pixel (register B1).

NASA EPIC resolves about 10 km, so it cannot say whether the atlas's cloud is right closer in. This
does: five cloud regimes, three days each, from VIIRS true colour (NASA GIBS, public domain), and the
atlas rendered over the same ground at the same scale and local time. Where a cloud is cannot match (a
typical year against a day) so nothing here compares position. It compares TEXTURE:

  bands      share of the luminance variance in each octave of wavelength, 4-8 km ... 128-256 km
  aniso      how far the 4-32 km structure is aligned in one direction (0 = none; streets score high)
  axis       WHICH direction that is, against the shipped monthly-mean wind's (the two cumulus scenes are scored)
  cover      share of the scene brighter than reflectance 0.30
  contrast   standard deviation of reflectance

The three reference days of a regime differ from each other; that spread is the noise floor, printed
beside every number. A difference smaller than the floor means nothing.

    ./venv/bin/python Research/modeling/cloud_texture.py --fetch            # 15 scenes, ~5 MB, reference/gibs_clouds/
    "$HOME/Modeling Studio/.venv/bin/python" Research/modeling/cloud_scenes_render.py cur
    ./venv/bin/python Research/modeling/cloud_texture.py --tag cur [--json]
    ./venv/bin/python Research/modeling/cloud_texture.py --selftest

Both pictures are put on one scale first: reflectance. VIIRS corrected reflectance is undone through
GIBS's published enhancement table; the atlas through its own display transform (shader_model).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
REF = os.path.join(ROOT, "reference", "gibs_clouds")
SHOTS = os.path.join(ROOT, "scratchpad")
FIG = os.path.join(ROOT, "Research", "figures", "clouds")
PX, KM = 1024, 2.0                       # every scene is PX x PX at KM per pixel
LAYER = "VIIRS_NOAA20_CorrectedReflectance_TrueColor"
# name: (lon, lat, the three days). Afternoon overpass, about 13:30 local time.
SCENES = {
    "amazon_cumulus": (-60.0, -5.0, ["2024-08-15", "2024-08-22", "2024-09-02"]),
    "congo_convective": (22.0, 1.0, ["2024-04-10", "2024-04-18", "2024-05-03"]),
    "natl_frontal": (-40.0, 45.0, ["2024-09-10", "2024-09-17", "2024-10-02"]),
    "sepac_stratocu": (-85.0, -20.0, ["2024-09-10", "2024-09-18", "2024-10-01"]),
    "trades_cumulus": (-52.0, 14.0, ["2024-02-10", "2024-02-18", "2024-03-03"]),
}
# Two more, added in the tenth round and scored APART from the five (their sums are a history that must stay
# comparable): the Southern Ocean in its summer. EPIC's December frames showed the atlas short of white there;
# these say whether it is short of LIGHT seen straight down, which is what the cloud climatology is checked by.
# They are rendered WITHOUT the atlas's air (cloud_scenes_render.py), so that mean light compares: VIIRS's
# corrected reflectance has the air's scattering taken out, and the atlas's air is not one offset. Measured on
# two scenes rendered both ways: it adds 0.026 to the mean over the mostly clear trades and takes 0.011 from the
# mostly overcast Southern Ocean (it dims bright cloud by more than it adds). The five keep their air, as scored
# since the second round; their mean light is printed raw.
EXTRA = {
    "socean_indian": (90.0, -52.0, ["2024-12-15", "2024-12-23", "2025-01-05"]),
    "socean_pacific": (-130.0, -55.0, ["2024-12-15", "2024-12-23", "2025-01-05"]),
}
BANDS = [(4, 8), (8, 16), (16, 32), (32, 64), (64, 128), (128, 256)]
LUMA = np.array([0.2126, 0.7152, 0.0722])


def bbox(lon, lat):
    half = PX * KM / 2 / 111.195
    return lat - half, lon - half / np.cos(np.radians(lat)), lat + half, lon + half / np.cos(np.radians(lat))


def fetch():
    os.makedirs(REF, exist_ok=True)
    for name, (lon, lat, days) in {**SCENES, **EXTRA}.items():
        b = bbox(lon, lat)
        for d in days:
            out = os.path.join(REF, f"{name}_{d}.jpg")
            if os.path.exists(out):
                continue
            url = ("https://gibs.earthdata.nasa.gov/wms/epsg4326/best/wms.cgi?SERVICE=WMS&REQUEST=GetMap&VERSION=1.3.0"
                   f"&LAYERS={LAYER}&CRS=EPSG:4326&BBOX={b[0]:.4f},{b[1]:.4f},{b[2]:.4f},{b[3]:.4f}&WIDTH={PX}&HEIGHT={PX}&FORMAT=image/jpeg&TIME={d}")
            r = subprocess.run(["curl", "-s", "-f", "-m", "120", "--retry", "3", "-o", out + ".part", url])
            if r.returncode == 0:
                os.replace(out + ".part", out)
            print(("ok   " if r.returncode == 0 else "FAIL ") + os.path.basename(out))


# GIBS corrected reflectance: reflectance x 255 goes through this piecewise-linear table to the picture.
_GX = np.array([0, 30, 60, 120, 190, 255.0]); _GY = np.array([0, 110, 160, 210, 240, 255.0])


def viirs_reflectance(img):
    return np.interp(np.asarray(img, dtype=np.float32), _GY, _GX) / 255.0 @ LUMA


def atlas_reflectance(img, mu0):
    sys.path.insert(0, HERE)
    import shader_model as S
    K = S.consts()
    return (S.from_display(np.asarray(img, dtype=np.float32), K) / K["SUN_E"] / max(mu0, 0.2)) @ LUMA


def measures(r):
    """r: (PX, PX) reflectance. Texture statistics; see the module docstring."""
    r = np.nan_to_num(r)
    w = np.hanning(r.shape[0])[:, None] * np.hanning(r.shape[1])[None, :]
    f = np.fft.fft2((r - r.mean()) * w)
    p = np.abs(f) ** 2
    fy = np.fft.fftfreq(r.shape[0], d=KM)[:, None]; fx = np.fft.fftfreq(r.shape[1], d=KM)[None, :]
    k = np.hypot(fx, fy)
    with np.errstate(divide="ignore"):
        lam = np.where(k > 0, 1.0 / k, np.inf)
    e = np.array([p[(lam >= lo) & (lam < hi)].sum() for lo, hi in BANDS])
    bands = e / e.sum()
    # anisotropy of the 4-32 km structure: second moment of the power over direction (0 isotropic, 1 one line)
    m = (lam >= 4) & (lam < 32)
    th = np.arctan2(np.broadcast_to(fy, p.shape), np.broadcast_to(fx, p.shape))[m]
    pw = p[m]
    aniso = float(np.hypot((pw * np.cos(2 * th)).sum(), (pw * np.sin(2 * th)).sum()) / pw.sum())
    return dict(bands=[float(x) for x in bands], aniso=aniso, cover=float((r > 0.30).mean()), contrast=float(r.std()), mean=float(r.mean()))


def axis(r):
    """The axis the 4-32 km structure runs along, as a bearing east of north (0..180), and how marked it is
    (the same second moment as `aniso`). Streets vary ACROSS themselves, so they run at right angles to the
    direction the power lies in. Image rows run south."""
    r = np.nan_to_num(r)
    w = np.hanning(r.shape[0])[:, None] * np.hanning(r.shape[1])[None, :]
    p = np.abs(np.fft.fft2((r - r.mean()) * w)) ** 2
    fy = np.fft.fftfreq(r.shape[0], d=KM)[:, None]; fx = np.fft.fftfreq(r.shape[1], d=KM)[None, :]
    k = np.hypot(fx, fy)
    with np.errstate(divide="ignore"):
        lam = np.where(k > 0, 1.0 / k, np.inf)
    m = (lam >= 4) & (lam < 32)
    th = np.arctan2(np.broadcast_to(-fy, p.shape), np.broadcast_to(fx, p.shape))[m]      # north up, counter-clockwise from east
    pw = p[m]; c, s_ = (pw * np.cos(2 * th)).sum(), (pw * np.sin(2 * th)).sum()
    along = 0.5 * np.degrees(np.arctan2(s_, c)) + 90.0
    return float((90.0 - along) % 180.0), float(np.hypot(c, s_) / pw.sum())


def wind_axis(lon, lat, month):
    """Bearing (0..180, east of north) of the axis the shipped monthly-mean surface wind blows along, and its
    speed, over a 9-degree box: read from the app's own field (web/fields/atmoA.png), as the shader reads it."""
    enc = json.load(open(os.path.join(ROOT, "web", "fields", "climate.json")))["encodings"]
    a = np.asarray(Image.open(os.path.join(ROOT, "web", "fields", "atmoA.png")).convert("RGB"), dtype=np.float32) / 255.0
    h = a.shape[0] // 12; a = a[month * h:(month + 1) * h]
    i, j = int((90 - lat) / 180 * h), int((lon + 180) / 360 * a.shape[1]) % a.shape[1]
    dec = lambda v, e: e["lo"] + (e["hi"] - e["lo"]) * v
    u = dec(float(a[i - 4:i + 5, j - 4:j + 5, 0].mean()), enc["u10"]); v = dec(float(a[i - 4:i + 5, j - 4:j + 5, 1].mean()), enc["v10"])
    return float(np.degrees(np.arctan2(u, v)) % 180.0), float(np.hypot(u, v))


def off_axis(a, b):
    """Angle between two axes (each 0..180), 0..90."""
    return float(abs((a - b + 90.0) % 180.0 - 90.0))


STREETS = ("trades_cumulus", "amazon_cumulus")        # the scenes of broken low cloud, where streets lie along the wind


def dist(a, b):
    return dict(bands=float(np.abs(np.array(a["bands"]) - np.array(b["bands"])).sum()), aniso=abs(a["aniso"] - b["aniso"]),
                cover=abs(a["cover"] - b["cover"]), contrast=abs(a["contrast"] - b["contrast"]))


def mu0_at(lon, lat, day):
    """Cosine of the Sun's zenith angle at 13:30 local solar time, to put the atlas on the reflectance scale."""
    n = int(day[5:7]) * 30.4 + int(day[8:10]) - 30
    dec = np.radians(23.44) * np.sin(2 * np.pi * (n - 81) / 365)
    h = np.radians(15 * 1.5)
    return float(np.sin(np.radians(lat)) * np.sin(dec) + np.cos(np.radians(lat)) * np.cos(dec) * np.cos(h))


def run(tag, as_json=False):
    rows, out = {}, {}
    os.makedirs(FIG, exist_ok=True)
    for name, (lon, lat, days) in {**SCENES, **EXTRA}.items():
        refs, ref_axes = [], []
        for d in days:
            p = os.path.join(REF, f"{name}_{d}.jpg")
            if not os.path.exists(p):
                raise SystemExit(f"missing {p}; run --fetch")
            rr = viirs_reflectance(Image.open(p).convert("RGB"))
            refs.append(measures(rr)); ref_axes.append(axis(rr)[0])
        shot = os.path.join(SHOTS, f"cloudscene_{tag}_{name}.jpg")
        if not os.path.exists(shot):
            raise SystemExit(f"no atlas render {shot}; run cloud_scenes_render.py {tag}")
        im = Image.open(shot).convert("RGB").resize((PX, PX), Image.BOX)
        ar = atlas_reflectance(im, mu0_at(lon, lat, days[0]))
        at = measures(ar)
        wb, ws = wind_axis(lon, lat, int(days[0][5:7]) - 1)
        street = dict(wind_axis=wb, wind_speed=ws, atlas_axis=axis(ar)[0], atlas_off=off_axis(axis(ar)[0], wb), ref_off=[off_axis(b, wb) for b in ref_axes])
        mean = {k: (np.mean([r[k] for r in refs], 0).tolist() if k == "bands" else float(np.mean([r[k] for r in refs]))) for k in refs[0]}
        floor = {k: float(np.mean([dist(refs[i], refs[j])[k] for i in range(3) for j in range(i + 1, 3)])) for k in ("bands", "aniso", "cover", "contrast")}
        floor["mean"] = float(np.mean([abs(refs[i]["mean"] - refs[j]["mean"]) for i in range(3) for j in range(i + 1, 3)]))
        d = dist(at, mean)
        d["mean"] = at["mean"] - mean["mean"]                           # signed: the atlas's light less the photographs'

        rows[name] = dict(atlas=at, ref=mean, floor=floor, dist=d, street=street)
        pair = Image.new("RGB", (PX * 2, PX)); pair.paste(Image.open(os.path.join(REF, f"{name}_{days[0]}.jpg")), (0, 0)); pair.paste(im, (PX, 0))
        pair.resize((PX, PX // 2), Image.LANCZOS).save(os.path.join(FIG, f"{name}_{tag}.jpg"), quality=88)
    # the score: by how much each distance exceeds its noise floor, summed over the regimes (0 = inside the floor everywhere)
    for k in ("bands", "aniso", "cover", "contrast"):
        out[f"texture_{k}_excess"] = round(float(sum(max(0.0, rows[n]["dist"][k] - rows[n]["floor"][k]) for n in SCENES)), 3)
    # Cumulus along the wind (tenth round): in the two scenes of broken low cloud, how far the axis the atlas's
    # 4-32 km structure runs along lies from the axis of the shipped wind, in degrees (0-90; 45 is no relation).
    # VIIRS's own days there: the trades 10, 41 and 1; the Amazon 21, 4 and 8.
    out["street_off_wind_deg"] = round(float(np.mean([rows[n]["street"]["atlas_off"] for n in STREETS])), 1)
    # the Southern Ocean scenes, apart: how far the atlas's light and its bright cover sit outside the photographs' days
    out["socean_light_excess"] = round(float(sum(max(0.0, abs(rows[n]["dist"]["mean"]) - rows[n]["floor"]["mean"]) for n in EXTRA)), 3)
    out["socean_cover_excess"] = round(float(sum(max(0.0, rows[n]["dist"]["cover"] - rows[n]["floor"]["cover"]) for n in EXTRA)), 3)
    if not as_json:
        print("share of variance by wavelength (km), then anisotropy, cover, contrast;  ref = mean of three days, floor = day-to-day")
        for name, r in rows.items():
            print(f"\n{name}")
            print("          " + " ".join(f"{lo:>3}-{hi:<3}" for lo, hi in BANDS) + "   aniso  cover  contrast")
            for who in ("ref", "atlas"):
                m = r[who]
                print(f"  {who:6}  " + " ".join(f"{x:7.2f}" for x in m["bands"]) + f"   {m['aniso']:5.2f}  {m['cover']:5.2f}  {m['contrast']:6.3f}")
            print(f"  distance: bands {r['dist']['bands']:.2f} (floor {r['floor']['bands']:.2f})  aniso {r['dist']['aniso']:.2f} ({r['floor']['aniso']:.2f})"
                  f"  cover {r['dist']['cover']:.2f} ({r['floor']['cover']:.2f})  contrast {r['dist']['contrast']:.3f} ({r['floor']['contrast']:.3f})")
            st = r["street"]
            print(f"  axis of the 4-32 km structure, off the shipped wind's ({st['wind_axis']:.0f} degrees, {st['wind_speed']:.1f} m/s): photographs "
                  + ", ".join(f"{x:.0f}" for x in st["ref_off"]) + f"; atlas {st['atlas_off']:.0f}")
            print(f"  mean light: photographs {r['ref']['mean']:.3f}, atlas {r['atlas']['mean']:.3f} ({r['dist']['mean']:+.3f}; day to day {r['floor']['mean']:.3f})"
                  + ("" if name in EXTRA else "   [atlas with its air: about +0.03 over clear sea]"))
    with open(os.path.join(HERE, f"cloud_texture_{tag}.json"), "w") as fh:
        json.dump(dict(tag=tag, summary=out, scenes=rows), fh, indent=1)
    print(json.dumps(out))
    return out


def selftest():
    n = PX
    yy, xx = np.mgrid[0:n, 0:n]
    # 1. a 20 km wave: all the variance in the 16-32 km band; a 12 km wave: the 8-16 band, and one direction
    m = measures(0.3 + 0.2 * np.sin(2 * np.pi * xx * KM / 20.0))
    assert m["bands"][2] > 0.97, m
    m2 = measures(0.3 + 0.2 * np.sin(2 * np.pi * xx * KM / 12.0))
    assert m2["bands"][1] > 0.97 and m2["aniso"] > 0.9, m2
    # 2. white noise: isotropic, and each octave holds four times the modes of the one below
    rng = np.random.default_rng(3)
    m3 = measures(rng.normal(0.3, 0.1, (n, n)))
    assert m3["aniso"] < 0.03 and m3["bands"][0] > 0.70, m3
    # 3. half the scene bright: cover 0.5
    r = np.where(xx < n // 2, 0.6, 0.05)
    assert abs(measures(r)["cover"] - 0.5) < 0.01
    # 4. the enhancement table round-trips
    v = np.interp(np.array([0.0, 0.2, 0.5, 0.9]) * 255, _GX, _GY)
    assert np.allclose(np.interp(v, _GY, _GX) / 255, [0.0, 0.2, 0.5, 0.9], atol=1e-6)
    # 5. the axis: stripes that run toward bearing 30 (north-north-east) read 30, whatever their width; and two axes 170 apart are 10 apart
    for bearing in (0.0, 30.0, 90.0, 135.0):
        b = np.radians(bearing)
        x, y = xx * KM, -(yy * KM)
        got, strength = axis(0.3 + 0.2 * np.sin(2 * np.pi * (x * np.cos(b) - y * np.sin(b)) / 12.0))
        assert off_axis(got, bearing) < 0.5 and strength > 0.9, (bearing, got, strength)
    assert abs(off_axis(175.0, 5.0) - 10.0) < 1e-9
    # 6. the shipped wind: the north-east trades blow from the east-north-east in February (an axis between 45 and 90)
    wb, ws = wind_axis(-52.0, 14.0, 1)
    assert 45 < wb < 90 and ws > 5, (wb, ws)
    print("cloud_texture selftest: ok")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--fetch", action="store_true"); ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--tag", default="cur"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
    elif a.fetch:
        fetch()
    else:
        run(a.tag, a.json)
