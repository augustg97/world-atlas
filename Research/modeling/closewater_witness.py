"""Fetch the INDEPENDENT witness for audit_closewater.py: ESA WorldCover 2021 v200 (Zanaga et al. 2022),
a 10 m land-cover map made from Sentinel-1 radar and Sentinel-2, class 80 = "Permanent water bodies".
JRC Global Surface Water (Landsat) was the witness and is becoming the page's source; this one shares
neither its satellite nor its method. It is measure-against only: not shipped, and the page never asks its
host. Free to use with attribution (CC BY 4.0, (c) ESA WorldCover project 2021 / Contains modified
Copernicus Sentinel data (2021) processed by ESA WorldCover consortium).

For every reference/closewater/<name>.npz it writes reference/closewater/<name>.wc.npz, on the same H x W grid:

    water   float32  the share (0..1) of each texel's footprint (centre +- half the spacing of lons / lats)
                     covered by 10 m pixels of class 80; an exact area average, no-data counting as not water
    cls     uint8    the WorldCover class at the texel centre: 10 trees, 20 shrub, 30 grass, 40 crop, 50 built-up,
                     60 bare, 70 snow and ice, 80 water, 90 herbaceous wetland, 95 mangroves, 100 moss, 0 no data
    valid   bool     False where WorldCover has no data (class 0) at the texel centre

The map is served as 3 x 3 degree cloud-optimised GeoTIFFs of 50-300 MB. None is downloaded whole: the header
is read through HTTP range requests, then only the internal 1024 px tiles under a box, about 1 MB a place.
Each tile's place on Earth is taken from its own tags (ModelTiepoint, ModelPixelScale) and checked against its
name. Every byte range fetched is kept in reference/worldcover/ (ignored by git), so a second run asks nobody.

    ./venv/bin/python Research/modeling/closewater_witness.py              # all places; one already done is skipped
    ./venv/bin/python Research/modeling/closewater_witness.py mead --force # these places, again
    ./venv/bin/python Research/modeling/closewater_witness.py --selftest   # no network: a synthetic map, known shares

Each place prints the water share by WorldCover and by JRC, the texels where the two agree (water >= 0.5
against truth), and how far WorldCover's water lies east and south of JRC's, in texels, by correlation.
Agreement far below 90% with a large offset would be a frame error. Offsets of one or two texels are real:
measured against the picture in the same file (s2), WorldCover sits within a third of a texel of it at the places
with a clear shore, and JRC, made from Landsat, sits 10-30 m off it at many (2026-11-11).
"""
from __future__ import annotations

import io
import math
import os
import sys
import threading
import time
import warnings

warnings.filterwarnings("ignore")
import numpy as np
import requests
import tifffile
from scipy import sparse
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
REF = os.path.join(ROOT, "reference", "closewater")
CACHE = os.path.join(ROOT, "reference", "worldcover")
BASE = "https://esa-worldcover.s3.eu-central-1.amazonaws.com/v200/2021/map/"
WATER = 80
DEG = 3                                  # a WorldCover tile is 3 x 3 degrees, named by its south-west corner
BLOCK = 1 << 16                          # the header is read in blocks of this many bytes

S = requests.Session(); S.headers["User-Agent"] = "python-requests"
LOCK = threading.Lock()
FETCHED = dict(bytes=0, requests=0)


def tile_name(lat, lon):
    return f"ESA_WorldCover_10m_2021_v200_{'S' if lat < 0 else 'N'}{abs(lat):02d}{'W' if lon < 0 else 'E'}{abs(lon):03d}_Map.tif"


def http_range(url, a, b):
    """Bytes a .. b-1 of url, and the length of the whole file. Three tries on a dropped line or a 5xx."""
    for attempt in range(3):
        try:
            r = S.get(url, headers={"Range": f"bytes={a}-{b - 1}"}, timeout=120)
        except (requests.ConnectionError, requests.Timeout):
            if attempt == 2:
                raise
            time.sleep(2 + 4 * attempt); continue
        if r.status_code < 500 or attempt == 2:
            break
        time.sleep(2 + 4 * attempt)
    if r.status_code != 206:
        raise RuntimeError(f"{url} bytes {a}-{b - 1}: HTTP {r.status_code}" + (" (WorldCover has no tile where a 3-degree cell is all ocean)" if r.status_code in (403, 404) else ""))
    total = int(r.headers["Content-Range"].rsplit("/", 1)[1])
    if len(r.content) != min(b, total) - a:
        raise RuntimeError(f"{url} bytes {a}-{b - 1}: got {len(r.content)} bytes")
    with LOCK:
        FETCHED["bytes"] += len(r.content); FETCHED["requests"] += 1
    return r.content, total


class Ranged:
    """A read-only seekable file over fetch(a, b) -> bytes a .. b-1, read in whole blocks; what tifffile
    needs to walk a header it cannot have all of."""

    def __init__(self, fetch, size, block=BLOCK):
        self.fetch, self.size, self.block, self.pos, self.got = fetch, size, block, 0, {}

    def seek(self, offset, whence=0):
        self.pos = offset + (0 if whence == 0 else self.pos if whence == 1 else self.size)
        return self.pos

    def tell(self):
        return self.pos

    def read(self, n=-1):
        end = self.size if n is None or n < 0 else min(self.size, self.pos + n)
        out = []
        for k in range(self.pos // self.block, (end - 1) // self.block + 1 if end > self.pos else 0):
            if k not in self.got:
                self.got[k] = self.fetch(k * self.block, min(self.size, (k + 1) * self.block))
            out.append(self.got[k][max(self.pos - k * self.block, 0):end - k * self.block])
        self.pos = max(self.pos, end)
        return b"".join(out)


class Source:
    """One WorldCover tile behind fetch(key, a, b): where it lies, from its own tags, and any window of it."""

    def __init__(self, lat, lon, fetch, size, block=BLOCK):
        self.name = tile_name(lat, lon); self.fetch = fetch
        self.tif = tifffile.TiffFile(Ranged(lambda a, b: fetch(f"head_{a // block}", a, b), size, block), name=self.name)
        p = self.page = self.tif.pages[0]
        g = p.geotiff_tags
        if not p.is_tiled or p.dtype != np.uint8 or p.ndim != 2:
            raise RuntimeError(f"{self.name}: not a tiled single-band uint8 raster ({p.shape}, {p.dtype})")
        if int(g.get("GeographicTypeGeoKey", 0)) != 4326 or int(g.get("GTRasterTypeGeoKey", 0)) != 1:
            raise RuntimeError(f"{self.name}: not WGS 84 with pixel-is-area ({g})")
        tie, (self.sx, self.sy) = g["ModelTiepoint"], g["ModelPixelScale"][:2]
        if len(tie) != 6 or tuple(tie[:3]) != (0, 0, 0):
            raise RuntimeError(f"{self.name}: the tiepoint is not the top-left corner ({tie})")
        self.west, self.north = tie[3], tie[4]
        self.height, self.width = p.shape
        self.th, self.tw = p.tilelength, p.tilewidth
        self.across = -(-self.width // self.tw)
        # the name says the south-west corner and 3 degrees a side: hold the tags to it
        got = (self.west, self.north - self.height * self.sy, self.west + self.width * self.sx, self.north)
        if max(abs(x - y) for x, y in zip(got, (lon, lat, lon + DEG, lat + DEG))) > 1e-6:
            raise RuntimeError(f"{self.name}: its tags place it at west, south, east, north = {got}")

    def block(self, ij):
        i, j = ij; k = i * self.across + j
        n = self.page.databytecounts[k]
        if n == 0:                       # a tile the writer left out: nothing there
            return np.zeros((self.th, self.tw), np.uint8)
        a = self.page.decode(self.fetch(f"tile_{i}_{j}", self.page.dataoffsets[k], self.page.dataoffsets[k] + n), k)[0]
        return a.reshape(self.th, self.tw)

    def read(self, r0, r1, c0, c1):
        """Rows r0 .. r1-1 and columns c0 .. c1-1 of the tile, row 0 north."""
        out = np.zeros((r1 - r0, c1 - c0), np.uint8)
        jobs = [(i, j) for i in range(r0 // self.th, (r1 - 1) // self.th + 1) for j in range(c0 // self.tw, (c1 - 1) // self.tw + 1)]
        with ThreadPoolExecutor(8) as ex:
            for (i, j), a in zip(jobs, ex.map(self.block, jobs)):
                y0, y1, x0, x1 = max(r0, i * self.th), min(r1, (i + 1) * self.th), max(c0, j * self.tw), min(c1, (j + 1) * self.tw)
                out[y0 - r0:y1 - r0, x0 - c0:x1 - c0] = a[y0 - i * self.th:y1 - i * self.th, x0 - j * self.tw:x1 - j * self.tw]
        return out


_OPEN = {}


def remote(lat, lon):
    """The WorldCover tile with that south-west corner, over HTTP, every range it gives kept on disk."""
    if (lat, lon) in _OPEN:
        return _OPEN[lat, lon]
    name = tile_name(lat, lon); d = os.path.join(CACHE, name[:-4]); url = BASE + name
    os.makedirs(d, exist_ok=True)

    def keep(key, data):
        with open(os.path.join(d, key + ".part"), "wb") as fh:
            fh.write(data)
        os.replace(os.path.join(d, key + ".part"), os.path.join(d, key + ".bin"))

    def fetch(key, a, b):
        p = os.path.join(d, key + ".bin")
        if os.path.exists(p):
            with open(p, "rb") as fh:
                data = fh.read()
            if len(data) == b - a:
                return data
        data, _ = http_range(url, a, b)
        keep(key, data)
        return data

    ps = os.path.join(d, "size.txt")
    if not os.path.exists(ps):
        data, total = http_range(url, 0, BLOCK)
        keep("head_0", data[:BLOCK])
        with open(ps, "w") as fh:
            fh.write(str(total))
    with open(ps) as fh:
        size = int(fh.read())
    _OPEN[lat, lon] = Source(lat, lon, fetch, size)
    return _OPEN[lat, lon]


def gather(open_tile, west, east, south, north):
    """The class raster under a box, pieced from every tile the box touches (one, two or four), with a pixel
    to spare all round. Returns it with the lon / lat of its top-left corner and its pixel size in degrees."""
    parts = []
    for la in range(DEG * math.floor(south / DEG), DEG * math.ceil(north / DEG), DEG):
        for lo in range(DEG * math.floor(west / DEG), DEG * math.ceil(east / DEG), DEG):
            t = open_tile(la, lo)
            c0 = max(0, math.floor((west - t.west) / t.sx) - 1); c1 = min(t.width, math.ceil((east - t.west) / t.sx) + 1)
            r0 = max(0, math.floor((t.north - north) / t.sy) - 1); r1 = min(t.height, math.ceil((t.north - south) / t.sy) + 1)
            if c1 > c0 and r1 > r0:
                parts.append((t, r0, c0, t.read(r0, r1, c0, c1)))
    if not parts:
        raise RuntimeError(f"no WorldCover tile under {west}..{east}, {south}..{north}")
    sx, sy = parts[0][0].sx, parts[0][0].sy
    if any(t.sx != sx or t.sy != sy for t, *_ in parts):
        raise RuntimeError("the tiles under one box differ in pixel size: " + ", ".join(f"{t.name} {t.sx} x {t.sy}" for t, *_ in parts))
    w0 = min(t.west + c0 * sx for t, _, c0, _ in parts); n0 = max(t.north - r0 * sy for t, r0, _, _ in parts)
    at = [((n0 - (t.north - r0 * sy)) / sy, (t.west + c0 * sx - w0) / sx) for t, r0, c0, _ in parts]
    if max(abs(v - round(v)) for rc in at for v in rc) > 1e-4:
        raise RuntimeError(f"the tiles under one box do not share a pixel grid: offsets {at}")
    at = [(round(r), round(c)) for r, c in at]
    out = np.zeros((max(r + a.shape[0] for (r, _), (*_, a) in zip(at, parts)), max(c + a.shape[1] for (_, c), (*_, a) in zip(at, parts))), np.uint8)
    for (r, c), (*_, a) in zip(at, parts):
        out[r:r + a.shape[0], c:c + a.shape[1]] = a
    if sum(a.size for *_, a in parts) != out.size:
        raise RuntimeError(f"the pieces under one box leave a gap or overlap: {[a.shape for *_, a in parts]} into {out.shape}")
    return out, w0, n0, sx, sy


def edges(c):
    """Texel edges from texel centres: half a spacing either side."""
    return np.concatenate(([c[0] - (c[1] - c[0]) / 2], (c[:-1] + c[1:]) / 2, [c[-1] + (c[-1] - c[-2]) / 2]))


def overlap(e, origin, step, n):
    """Sparse (texels, n): the share of each texel's extent, between consecutive edges e, lying in each of n
    source pixels, pixel k spanning origin + k * step .. origin + (k + 1) * step. step may be negative."""
    p = (np.asarray(e, np.float64) - origin) / step
    a, b = np.minimum(p[:-1], p[1:]), np.maximum(p[:-1], p[1:])
    k = np.floor(a)[:, None] + np.arange(int(np.ceil((b - a).max())) + 1)[None, :]
    w = np.clip(np.minimum(b[:, None], k + 1) - np.maximum(a[:, None], k), 0, None)
    w[w < 1e-7] = 0                      # an edge that lies on a pixel edge, give or take the last digit of a double
    if ((w > 0) & ((k < 0) | (k >= n))).any():
        raise RuntimeError("a texel reaches outside the source raster")
    if abs(w.sum(axis=1) / (b - a) - 1).max() > 1e-5:
        raise RuntimeError("the overlaps of a texel do not add up to its extent")
    w /= w.sum(axis=1, keepdims=True)
    keep = w > 0
    rows = np.broadcast_to(np.arange(len(a))[:, None], w.shape)
    m = sparse.csr_matrix((w[keep], (rows[keep], k[keep].astype(np.int64))), shape=(len(a), n))
    return m


def resample(cls, west, north, sx, sy, lons, lats):
    """A class raster (row 0 north, top-left corner at west, north, pixels sx by sy degrees) onto the grid of
    texel centres lons, lats. Returns the water share of each texel's footprint, the class at its centre,
    and whether that class is data."""
    wx = overlap(edges(lons), west, sx, cls.shape[1])
    wy = overlap(edges(lats), north, -sy, cls.shape[0])
    water = (wx @ (wy @ (cls == WATER).astype(np.float32)).T).T
    ix = np.floor((np.asarray(lons) - west) / sx).astype(int); iy = np.floor((north - np.asarray(lats)) / sy).astype(int)
    centre = cls[iy][:, ix]
    return np.clip(water, 0, 1).astype(np.float32), centre, centre != 0


def register(a, b, reach=3):
    """How far the pattern in a lies east and south of the same pattern in b, in texels: the whole-texel shift
    of best correlation within reach, refined by a parabola through its two neighbours on each axis. A shore
    that has really moved between the two (a falling lake) reads as a shift too. nan where either is flat."""
    h, w = a.shape; r = reach
    B = b[r:h - r, r:w - r].astype(np.float64); B -= B.mean()
    g = np.zeros((2 * r + 1, 2 * r + 1))
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            A = a[r + dy:h - r + dy, r + dx:w - r + dx].astype(np.float64); A -= A.mean()
            n = np.sqrt((A * A).sum() * (B * B).sum())
            if n == 0:
                return float("nan"), float("nan")
            g[dy + r, dx + r] = (A * B).sum() / n
    iy, ix = np.unravel_index(g.argmax(), g.shape)

    def fine(v, i):
        d = v[i - 1] - 2 * v[i] + v[i + 1] if 0 < i < len(v) - 1 else 0
        return i - r + (0.5 * (v[i - 1] - v[i + 1]) / d if d < 0 else 0)

    return fine(g[iy], ix), fine(g[:, ix], iy)


def line(name, truth, wc):
    w, valid = wc["water"] >= 0.5, wc["valid"]
    if not valid.any():
        return f"  {name:11s} {truth.shape[1]:4d} x {truth.shape[0]:4d}   WorldCover has no data anywhere in the box"
    east, south = register(wc["water"], truth)
    return (f"  {name:11s} {truth.shape[1]:4d} x {truth.shape[0]:4d}   water {100 * wc['water'][valid].mean():5.1f}% by WorldCover, {100 * truth[valid].mean():5.1f}% by JRC"
            f"   agree {100 * (w == truth)[valid].mean():6.2f}%   no data {100 * (~valid).mean():4.1f}%   WorldCover lies {east:+.2f} texel east, {south:+.2f} south of JRC")


def selftest():
    """No network. Four synthetic tiles round lon 0, lat 0 (0.01 degree pixels, 48 px internal tiles, so every
    read crosses tile and header-block seams), written as real tiled GeoTIFFs and read back through Source,
    gather and resample. Water is the quarter north-west of lon 0.10, lat -0.20; a block of no data sits in the land."""
    px, n, x0, y0 = 0.01, 300, 0.10, -0.20
    nodata = (0.30, 0.40, 0.10, 0.20)    # west, east, south, north

    def world(lon, lat):
        c = np.where((lon < x0) & (lat > y0), WATER, 10)
        return np.where((lon >= nodata[0]) & (lon < nodata[1]) & (lat >= nodata[2]) & (lat < nodata[3]), 0, c).astype(np.uint8)

    files = {}
    for la in (-3, 0):
        for lo in (-3, 0):
            lon = lo + (np.arange(n) + 0.5) * px; lat = la + DEG - (np.arange(n) + 0.5) * px
            buf = io.BytesIO()
            tifffile.imwrite(buf, world(lon[None, :], lat[:, None]), tile=(48, 48), compression="zlib", photometric="minisblack",
                             extratags=[(33550, "d", 3, (px, px, 0.0), True), (33922, "d", 6, (0.0, 0.0, 0.0, float(lo), float(la + DEG), 0.0), True),
                                        (34735, "H", 16, (1, 1, 0, 3, 1024, 0, 1, 2, 1025, 0, 1, 1, 2048, 0, 1, 4326), True)])
            files[tile_name(la, lo)] = buf.getvalue()
    assert sorted(files) == sorted(f"ESA_WorldCover_10m_2021_v200_{t}_Map.tif" for t in ("S03W003", "S03E000", "N00W003", "N00E000")), sorted(files)
    asked = []

    def open_tile(la, lo):
        b = files[tile_name(la, lo)]; asked.append((la, lo))
        return Source(la, lo, lambda key, a, c: b[a:c], len(b), block=512)

    def run(lons, lats):
        e, f = edges(lons), edges(lats)
        cls, west, north, sx, sy = gather(open_tile, e.min(), e.max(), f.min(), f.max())
        return resample(cls, west, north, sx, sy, lons, lats), e, f

    # 1. a grid like the real ones (2.06 source pixels a texel, off the pixel grid), across all four tiles
    lons = -0.5 + 0.0206 * (np.arange(50) + 0.5) + 0.00123; lats = 0.4 - 0.0206 * (np.arange(40) + 0.5) - 0.0007
    (water, cls, valid), e, f = run(lons, lats)
    assert sorted(set(asked)) == [(-3, -3), (-3, 0), (0, -3), (0, 0)], asked
    fx = np.clip((x0 - e[:-1]) / (e[1:] - e[:-1]), 0, 1); fy = np.clip((f[:-1] - y0) / (f[:-1] - f[1:]), 0, 1)
    want = fy[:, None] * fx[None, :]
    assert water.shape == (40, 50) and water.dtype == np.float32 and cls.dtype == np.uint8 and valid.dtype == bool
    assert abs(water - want).max() < 1e-5, f"water share off by {abs(water - want).max()}"
    assert ((want > 0) & (want < 1)).sum() > 40 and (want == 1).any() and (want == 0).any()
    assert (cls == world(lons[None, :], lats[:, None])).all(), "class at the texel centre"
    hole = (lons[None, :] >= nodata[0]) & (lons[None, :] < nodata[1]) & (lats[:, None] >= nodata[2]) & (lats[:, None] < nodata[3])
    assert hole.sum() > 10 and (valid == ~hole).all(), "valid"
    # 2. a mirrored or transposed frame must not pass: the shares are told apart from their flips
    assert abs(water - want[::-1]).max() > 0.5 and abs(water - want[:, ::-1]).max() > 0.5
    # 3. texels of exactly two source pixels with the shore down the middle of one: a half, between a one and a nought
    lons = -0.30 + 0.02 * np.arange(40); lats = 0.39 - 0.02 * np.arange(20)
    (water, cls, valid), e, f = run(lons, lats)
    k = int(np.argmin(abs(lons - x0)))
    assert abs(e[k] - 0.09) < 1e-9 and abs(e[k + 1] - 0.11) < 1e-9
    assert np.allclose(water[:5, k - 1:k + 2], [1, 0.5, 0], atol=1e-6), water[:5, k - 1:k + 2]
    # 4. a box inside one tile asks for one tile; a grid running south to north and east to west gives the same answer flipped
    del asked[:]
    lons = 1.0 + 0.0206 * np.arange(30); lats = 1.5 - 0.0206 * np.arange(30)
    (a, ca, va), _, _ = run(lons, lats)
    assert set(asked) == {(0, 0)}, asked
    (b, cb, vb), _, _ = run(lons[::-1], lats[::-1])
    assert np.allclose(a, b[::-1, ::-1], atol=1e-6) and (ca == cb[::-1, ::-1]).all() and a.max() == 0
    # 5. the register: a disc moved two texels east and one north is found there, and one moved half a texel is found near a half
    yy, xx = np.mgrid[:60, :80]
    disc = lambda cx, cy: ((xx - cx) ** 2 + (yy - cy) ** 2 < 15 ** 2).astype(np.float32)
    east, south = register(disc(42, 29), disc(40, 30))
    assert abs(east - 2) < 0.05 and abs(south + 1) < 0.05, (east, south)
    east, south = register((disc(40, 30) + disc(41, 30)) / 2, disc(40, 30))
    assert abs(east - 0.5) < 0.1 and abs(south) < 0.05, (east, south)
    assert np.isnan(register(np.zeros((20, 20)), disc(10, 10)[:20, :20])[0])
    print("closewater_witness selftest: ok (four-tile straddle, half-covered texel, flips told apart, class and no-data at the centre, register)")


def main():
    args = sys.argv[1:]
    if "--selftest" in args:
        return selftest()
    force = "--force" in args
    bad = [a for a in args if a.startswith("-") and a != "--force"]
    if bad:
        raise SystemExit(f"closewater_witness: unknown option {bad[0]} (there are --force and --selftest)")
    names = [a for a in args if not a.startswith("-")] or sorted(f[:-4] for f in os.listdir(REF) if f.endswith(".npz") and "." not in f[:-4])     # the places; not their .wc or .jrc companions
    made = 0
    for n in names:
        d = np.load(os.path.join(REF, f"{n}.npz")); out = os.path.join(REF, f"{n}.wc.npz")
        if force or not os.path.exists(out):
            e, f = edges(d["lons"]), edges(d["lats"])
            cls, west, north, sx, sy = gather(remote, e.min(), e.max(), f.min(), f.max())
            water, centre, valid = resample(cls, west, north, sx, sy, d["lons"], d["lats"])
            assert water.shape == centre.shape == valid.shape == d["truth"].shape, (n, water.shape, d["truth"].shape)
            np.savez_compressed(out, water=water, cls=centre, valid=valid)
            made += 1
        print(line(n, d["truth"], np.load(out)), flush=True)
    print(f"closewater witness: {len(names) - made} already there, {made} made; {FETCHED['bytes']} bytes fetched in {FETCHED['requests']} requests")


if __name__ == "__main__":
    main()
