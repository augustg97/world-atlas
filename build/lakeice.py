#!/usr/bin/env python3
"""Lake ice from air temperature: the share of each month a lake is frozen, in a typical year. MODELLED.

Why it exists. The atlas's sea ice is NSIDC's and stops at the sea. Inland, the only gridded ice in hand
is OISST's, which covers the Great Lakes, Ladoga and little else, shows 9% ice on Lake Ontario in July,
and has none at all on the north Caspian or the Sea of Azov, which freeze every winter. Baikal, Great
Bear, Great Slave and every smaller lake had nothing and never froze on screen (register A5).

The model is the oldest one there is, run a day at a time on the month's mean air temperature:

    freeze-up   when the air's mean over the last LAG days falls below freezing (the lake has to
                give up its summer heat first)
    growth      Stefan's law: thickness squared grows by ALPHA^2 for each degree-day of frost
    melt        MELT metres for each degree-day of thaw; break-up when nothing is left

Years differ, and a lake whose typical January is just above freezing still freezes in the cold ones.
So the year is run five times, colder and warmer by up to two standard deviations of a month's
mean temperature (`spread`), and the answers are weighted as a normal distribution weights them: the result is how OFTEN a
day is frozen, which is what a mean ice concentration is.

LAG and MELT are fitted, to half of the lakes in NSIDC's Global Lake and River Ice Phenology Database;
the other half is the test (Research/modeling/audit_lakeice.py). ALPHA is ice physics; the spread is
round figures. Nothing here knows a lake's depth: a deep lake freezes later
than this says (Baikal, by weeks) and a great lake only in part.
"""
from __future__ import annotations

import numpy as np

LAG = 48             # days of mean air temperature a lake answers to. FITTED (audit_lakeice.py --fit): 91 lakes
MELT = 0.016         # metres of ice lost per degree-day of thaw. FITTED, the same 91 lakes
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


def frozen_days(td, lag=LAG, melt=MELT, alpha=ALPHA):
    """td: (365, n) daily air temperature, one typical year. Returns (365, n) booleans: iced or not.
    The year is run twice round so that the state on 1 January is the state the year itself leaves."""
    n = td.shape[1]
    lag = int(max(1, round(lag)))
    ext = np.concatenate([td[-lag:], td], 0)
    cs = np.cumsum(ext, 0)
    tmean = (cs[lag:] - cs[:-lag]) / lag                       # mean of the `lag` days before each day
    frozen = np.zeros(n, bool); h = np.zeros(n)
    out = np.zeros((365, n), bool)
    for lap in range(2):
        for d in range(365):
            t = td[d]
            start = ~frozen & (tmean[d] < 0.0) & (t < 0.0)
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


def monthly_ice(tm, lag=LAG, melt=MELT, alpha=ALPHA, sigma=None):
    """(12, n) monthly mean air temperature at the lake, degrees C, to (12, n): the share of each month
    the lake is frozen, averaged over colder and warmer years."""
    tm = np.asarray(tm, dtype=np.float64)
    td = daily(tm)
    sg = spread(tm)[None] if sigma is None else sigma
    acc = np.zeros(td.shape)
    for z, w in zip(_NODES, _WEIGHTS):
        acc += w * frozen_days(td + z * sg, lag, melt, alpha)
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
