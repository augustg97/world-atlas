#!/usr/bin/env python3
"""Lake ice from air temperature: the share of each month a lake is frozen, in a typical year. MODELLED.

Why it exists. The atlas's sea ice is NSIDC's and stops at the sea. Inland, the only gridded ice in hand
is OISST's, which covers the Great Lakes, Ladoga and little else, shows 9% ice on Lake Ontario in July,
and has none at all on the north Caspian or the Sea of Azov, which freeze every winter. Baikal, Great
Bear, Great Slave and every smaller lake had nothing and never froze on screen (register A5).

The model is the oldest one there is, run a day at a time on the month's mean air temperature:

    freeze-up   when the air's mean over the last N days falls below freezing: the lake has to give
                up its summer heat first, and N grows with its mean depth (13 days at 1.5 m, 39 at 7,
                95 at 25, never more than 160)
    growth      Stefan's law: thickness squared grows by ALPHA^2 for each degree-day of frost
    melt        MELT metres for each degree-day of thaw; break-up when nothing is left

Years differ, and a lake whose typical January is just above freezing still freezes in the cold ones.
So the year is run five times, colder and warmer by up to two standard deviations of a month's
mean temperature (`spread`), and the answers are weighted as a normal distribution weights them: the result is how OFTEN a
day is frozen, which is what a mean ice concentration is.

The depth rule's two numbers and MELT are fitted, to the lakes of known depth in half of NSIDC's Global
Lake and River Ice Phenology Database; the other half is the test (Research/modeling/audit_lakeice.py).
ALPHA is ice physics; the spread is round figures. Depth is HydroLAKES's mean depth for the lake, or the
sea floor's where ETOPO has one (the Caspian, Baikal, the Great Lakes); a great lake still freezes whole
or not at all, cell by cell, where a real one freezes in part.
"""
from __future__ import annotations

import numpy as np

# Freeze-up lag: the days of mean air temperature a lake answers to. A lake must give up its summer heat
# before it can freeze, and how much it holds goes with its depth: LAG_A * depth^LAG_P days, to LAG_MAX
# (below the depth the autumn overturn reaches, more water adds little). Against 102 lakes whose mean depth
# is recorded, one lag for all (48 days) was 10 days a year short on lakes under 6 m and 50 long on lakes over
# 25 m; its error went with the logarithm of depth at r = 0.76.
LAG_A = 10.0         # FITTED (audit_lakeice.py --fit): the 48 lakes of the fitting half whose depth is recorded
LAG_P = 0.7          # FITTED, the same lakes
LAG_MAX = 160.0      # days. Set on the 8 recorded lakes deeper than 25 m, BOTH halves: too few to split
DEPTH_UNKNOWN = 7.0  # metres: the median recorded mean depth, used where a lake's depth is not known (lag 39 days)
MELT = 0.012         # metres of ice lost per degree-day of thaw. FITTED with LAG_A and LAG_P
ALPHA = 0.020        # metres per sqrt(degree-day): Stefan growth under a snow cover (clear ice: 0.027 to 0.035)
# Year-to-year spread of a month's mean temperature, degrees C: 0.6 + a tenth of the place's annual range,
# kept between 0.8 and 3.5. Round figures: about 1 in the tropics, 2 by a mid-latitude sea, 3.5 deep in a
# continent. One number for everywhere (2.5) put ice on Lake Titicaca, where July is +2 C every year.
def spread(tm):
    return np.clip(0.6 + 0.1 * (tm.max(0) - tm.min(0)), 0.8, 3.5)
H0 = 0.02            # metres: the skin of ice a lake freezes over with
_NODES = np.array([-2.0202, -0.9586, 0.0, 0.9586, 2.0202]) * 1.0          # Gauss-Hermite, in standard deviations
_WEIGHTS = np.array([0.01126, 0.22208, 0.53333, 0.22208, 0.01126]); _WEIGHTS = _WEIGHTS / _WEIGHTS.sum()
_MID = np.array([15.5, 45.0, 74.5, 105.0, 135.5, 166.0, 196.5, 227.5, 258.0, 288.5, 319.0, 349.5])   # mid-month, day of year
_MONTH_OF_DAY = np.repeat(np.arange(12), [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31])


def daily(tm):
    """(12, n) monthly means to (365, n) daily values: straight lines between mid-months, round the year."""
    tm = np.asarray(tm, dtype=np.float64)
    d = np.arange(365) + 0.5
    x = np.concatenate([[_MID[-1] - 365], _MID, [_MID[0] + 365]])
    y = np.concatenate([tm[-1:], tm, tm[:1]], 0)
    k = np.clip(np.searchsorted(x, d) - 1, 0, 12)
    f = ((d - x[k]) / (x[k + 1] - x[k]))[:, None]
    return y[k] * (1 - f) + y[k + 1] * f


def lag_days(depth, a=LAG_A, p=LAG_P):
    """Freeze-up lag in whole days for a mean depth in metres (NaN or None: depth not known)."""
    d = np.where(np.isfinite(np.asarray(depth, dtype=np.float64)), np.asarray(depth, dtype=np.float64), DEPTH_UNKNOWN) if depth is not None else DEPTH_UNKNOWN
    return np.clip(np.round(a * np.maximum(d, 0.3) ** p), 3, LAG_MAX).astype(int)


def frozen_days(td, lag, melt=MELT, alpha=ALPHA):
    """td: (365, n) daily air temperature, one typical year. lag: days, one number or one per lake.
    Returns (365, n) booleans: iced or not. The year is run twice round so that the state on 1 January is
    the state the year itself leaves."""
    n = td.shape[1]
    lag = np.broadcast_to(np.asarray(lag, dtype=int), (n,))
    lmax = int(lag.max())
    cs = np.cumsum(np.concatenate([np.zeros((1, n)), td[-lmax:], td], 0), 0)       # cs[k] = sum of the k days before day k - lmax
    cols = np.arange(n)
    frozen = np.zeros(n, bool); h = np.zeros(n)
    out = np.zeros((365, n), bool)
    for lap in range(2):
        for d in range(365):
            t = td[d]
            tmean = (cs[d + lmax, cols] - cs[d + lmax - lag, cols]) / lag               # mean of the `lag` days before this one
            start = ~frozen & (tmean < 0.0) & (t < 0.0)
            frozen |= start; h = np.where(start, H0, h)
            grow = frozen & (t < 0.0)
            h = np.where(grow, np.sqrt(h * h + alpha * alpha * np.maximum(-t, 0.0)), h)
            thaw = frozen & (t >= 0.0)
            h = np.where(thaw, h - melt * t, h)
            gone = frozen & (h <= 0.0)
            frozen &= ~gone; h = np.where(gone, 0.0, h)
            if lap == 1:
                out[d] = frozen
    return out


def monthly_ice(tm, depth=None, lag=None, melt=MELT, alpha=ALPHA, sigma=None):
    """(12, n) monthly mean air temperature at the lake, degrees C, and its mean depth in metres (n,), to
    (12, n): the share of each month the lake is frozen, averaged over colder and warmer years.
    `lag` overrides the depth rule (for fitting)."""
    tm = np.asarray(tm, dtype=np.float64)
    td = daily(tm)
    lg = lag_days(depth) if lag is None else lag
    sg = spread(tm)[None] if sigma is None else sigma
    acc = np.zeros(td.shape)
    for z, w in zip(_NODES, _WEIGHTS):
        acc += w * frozen_days(td + z * sg, lg, melt, alpha)
    return np.stack([acc[_MONTH_OF_DAY == m].mean(0) for m in range(12)])


def selftest():
    warm = np.full((12, 1), 8.0)
    assert monthly_ice(warm).max() == 0.0, "a lake that never sees frost never freezes, in any of the five years"
    polar = np.full((12, 1), -15.0)
    assert monthly_ice(polar).min() > 0.99, "a lake in permanent frost is always iced"
    # a continental lake: -15 in January, +18 in July. Frozen all of January to March, open all of June to September
    cont = (1.5 - 16.5 * np.cos(2 * np.pi * (_MID - 15) / 365))[:, None]
    m = monthly_ice(cont)[:, 0]
    assert m[0] > 0.99 and m[1] > 0.99 and m[2] > 0.95 and m[5:9].max() < 0.01, m
    # colder is longer, month by month
    m2 = monthly_ice(cont - 4.0)[:, 0]
    assert (m2 >= m - 1e-9).all() and m2.sum() > m.sum() + 0.5, (m, m2)
    # depth: a deep lake under the same air freezes later and is iced for less of the year (under this air, -15 C in
    # January, even a 300 m lake freezes for three and a half months, as Baikal does)
    by_depth = [monthly_ice(cont, depth=np.array([dpt])).sum() for dpt in (2.0, 7.0, 30.0, 300.0)]
    assert by_depth[0] > by_depth[1] > by_depth[2] > by_depth[3] and by_depth[3] < 0.7 * by_depth[1], by_depth
    assert list(lag_days(np.array([1.5, 7.0, 25.0, 1000.0, np.nan]))) == [13, 39, 95, 160, 39], lag_days(np.array([1.5, 7.0, 25.0, 1000.0, np.nan]))
    mixed = monthly_ice(np.concatenate([cont, cont], 1), depth=np.array([2.0, 30.0]))          # per-lake lags in one call agree with one at a time
    assert np.allclose(mixed[:, 0], monthly_ice(cont, depth=np.array([2.0]))[:, 0]) and np.allclose(mixed[:, 1], monthly_ice(cont, depth=np.array([30.0]))[:, 0])
    # a marginal lake (+1 in the coldest month) freezes in some years and not in others
    marg = (10.0 - 9.0 * np.cos(2 * np.pi * (_MID - 15) / 365))[:, None]
    mm = monthly_ice(marg)[:, 0]
    assert 0.02 < mm[0] < 0.6 and mm[6] == 0.0, mm
    # a high tropical lake: +2 C in its coldest month, +7.5 in its warmest, every year alike. It does not freeze.
    trop = (4.75 - 2.75 * np.cos(2 * np.pi * (_MID - 15) / 365))[:, None]
    assert monthly_ice(trop).max() < 0.02, monthly_ice(trop)[:, 0]
    # daily(): the mean of the daily values in a month is near the month's mean, and the year closes
    td = daily(cont)
    assert abs(td[:31].mean() - cont[0, 0]) < 1.2 and abs(td[0, 0] - td[-1, 0]) < 0.5
    # the southern hemisphere needs nothing special: shift the year by six months and the ice shifts with it
    south = np.roll(cont, 6, 0)
    assert np.allclose(monthly_ice(south)[:, 0], np.roll(m, 6), atol=0.06)
    print("lakeice selftest: ok")


if __name__ == "__main__":
    selftest()
