# Sea-ice extent: shipped field against NSIDC (1991-2020 means), million km2

| month | Arctic atlas | NSIDC | error | Antarctic atlas | NSIDC | error |
|---|---|---|---|---|---|---|
| Jan | 13.97 | 13.98 | -0.07% | 5.04 | 5.04 | -0.00% |
| Feb | 14.85 | 14.87 | -0.07% | 3.09 | 3.09 | -0.01% |
| Mar | 15.02 | 15.03 | -0.07% | 4.08 | 4.08 | +0.01% |
| Apr | 14.31 | 14.32 | -0.07% | 6.95 | 6.95 | +0.01% |
| May | 12.92 | 12.93 | -0.08% | 10.29 | 10.29 | +0.00% |
| Jun | 11.29 | 11.30 | -0.09% | 13.46 | 13.46 | +0.00% |
| Jul | 8.74 | 8.75 | -0.11% | 16.07 | 16.07 | +0.00% |
| Aug | 6.42 | 6.43 | -0.14% | 17.84 | 17.84 | -0.00% |
| Sep | 5.58 | 5.58 | -0.16% | 18.61 | 18.61 | +0.00% |
| Oct | 7.48 | 7.49 | -0.13% | 18.22 | 18.23 | -0.00% |
| Nov | 10.13 | 10.14 | -0.10% | 15.87 | 15.87 | +0.00% |
| Dec | 12.39 | 12.40 | -0.08% | 10.40 | 10.40 | -0.00% |

Largest error: Arctic 0.2%, Antarctic 0.0%; mean absolute 0.1%.

Before 2026-11-10 (NOAA OISST long-term-mean ice): largest error Arctic 31.5%, Antarctic 93.5%; mean absolute 29.3%.

The build solves for this table (it takes the most often iced cells until their area reaches NSIDC's mean extent), so it guards the shipped bytes and is not independent evidence. The sections below are.

## Ice area (concentration x cell area inside the 15% line), not solved for

| month | Arctic atlas | NSIDC | error | Antarctic atlas | NSIDC | error |
|---|---|---|---|---|---|---|
| Jan | 12.29 | 12.23 | +0.5% | 2.84 | 3.32 | -14.4% |
| Feb | 13.07 | 13.01 | +0.5% | 1.71 | 2.02 | -15.3% |
| Mar | 13.23 | 13.17 | +0.4% | 2.36 | 2.74 | -14.0% |
| Apr | 12.58 | 12.52 | +0.5% | 4.77 | 5.16 | -7.6% |
| May | 11.12 | 11.06 | +0.5% | 7.59 | 8.00 | -5.0% |
| Jun | 8.91 | 8.93 | -0.3% | 10.25 | 10.67 | -3.9% |
| Jul | 5.92 | 6.05 | -2.2% | 12.48 | 12.87 | -3.0% |
| Aug | 4.13 | 4.27 | -3.2% | 13.84 | 14.21 | -2.6% |
| Sep | 3.75 | 3.93 | -4.7% | 14.29 | 14.66 | -2.5% |
| Oct | 5.57 | 5.88 | -5.3% | 13.77 | 14.13 | -2.5% |
| Nov | 8.62 | 8.66 | -0.4% | 11.20 | 11.61 | -3.6% |
| Dec | 10.79 | 10.75 | +0.3% | 6.24 | 6.91 | -9.7% |

The shipped concentration is the 30-year mean inside the typical line. Where the ice is somewhere else every year (the Antarctic summer) that mean is diluted by the open years, and the ice outside the line in any one year is not counted, so area runs low there. NSIDC's area leaves out the Arctic pole hole (0.03-0.31 million km2 in these years); the atlas fills it.

## Per-year check of the conversion (720 monthly grids, each on its own, 15% threshold, no fitting)

Percent error in extent. `--peryear` recomputes this from data/nsidc.

| comparison | hemisphere | median | 5th pct | 95th pct | worst |
|---|---|---|---|---|---|
| canonical raster, no atlas mask, against the grid on NSIDC's own cells | north | -0.76 | -0.90 | -0.67 | -0.97 |
| canonical raster, no atlas mask, against the grid on NSIDC's own cells | south | -0.68 | -0.81 | -0.60 | -0.86 |
| canonical raster as the dashboard counts (atlas ocean mask, coast fill), against the grid on NSIDC's own cells | north | +0.58 | +0.20 | +0.86 | +0.93 |
| canonical raster as the dashboard counts (atlas ocean mask, coast fill), against the grid on NSIDC's own cells | south | +0.69 | +0.34 | +2.85 | +3.65 |
| the monthly-mean grid on NSIDC's own cells, against NSIDC's published monthly extent | north | +1.62 | +0.62 | +7.00 | +20.32 |
| the monthly-mean grid on NSIDC's own cells, against NSIDC's published monthly extent | south | +3.74 | +1.12 | +11.38 | +15.33 |
| canonical raster as the dashboard counts, against NSIDC's published monthly extent | north | +2.26 | +1.11 | +7.42 | +20.74 |
| canonical raster as the dashboard counts, against NSIDC's published monthly extent | south | +4.71 | +1.69 | +12.96 | +18.36 |

Row 1 is the projection alone. It is not zero because the atlas measures area on a 6371.0088 km sphere and NSIDC on the Hughes ellipsoid: spherical cells poleward of 60 degrees are 0.7-0.9% smaller (build/test_frames.py asserts the figure).
Row 2 adds the atlas's ocean mask: it gains the fjords and channels NSIDC's 25 km mask calls coast and loses the cells OISST calls land.
Row 3 has no conversion in it at all. NSIDC's monthly extent is the mean of the daily extents; a monthly-mean grid clears 15% wherever ice sat for a fifth of the month, so it overshoots most in the months the edge moves fastest (Arctic October, Antarctic March and December).

## Why the 15% line is not the median ice edge

Million km2, counted on NSIDC's cells. The shipped line is the ice-frequency contour that encloses NSIDC's mean extent; `frequency` is the share of the thirty years iced at that line (0.50 would be the median edge).

| Arctic | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NSIDC mean of yearly extents | 13.98 | 14.87 | 15.03 | 14.32 | 12.93 | 11.30 | 8.75 | 6.43 | 5.58 | 7.49 | 10.14 | 12.40 |
| mean concentration >= 15% | +4% | +4% | +4% | +4% | +4% | +7% | +12% | +14% | +19% | +20% | +7% | +5% |
| median ice edge | +2% | +1% | +1% | +1% | +1% | +5% | +4% | +2% | +2% | +14% | +4% | +3% |
| shipped line | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| frequency at the shipped line | 0.60 | 0.58 | 0.58 | 0.56 | 0.55 | 0.68 | 0.59 | 0.53 | 0.52 | 0.73 | 0.64 | 0.65 |
| iced cells borrowed at coasts | 0.41 | 0.43 | 0.43 | 0.40 | 0.34 | 0.29 | 0.22 | 0.15 | 0.12 | 0.18 | 0.26 | 0.34 |
| iced NSIDC cells the atlas calls land | 0.19 | 0.20 | 0.20 | 0.19 | 0.17 | 0.15 | 0.11 | 0.08 | 0.07 | 0.10 | 0.13 | 0.16 |

| Antarctic | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| NSIDC mean of yearly extents | 5.04 | 3.09 | 4.08 | 6.95 | 10.29 | 13.46 | 16.07 | 17.84 | 18.61 | 18.23 | 15.87 | 10.40 |
| mean concentration >= 15% | +28% | +24% | +30% | +18% | +13% | +10% | +7% | +6% | +6% | +6% | +8% | +21% |
| median ice edge | +0% | -8% | +13% | +9% | +8% | +5% | +3% | +3% | +2% | +2% | +4% | +13% |
| shipped line | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% | +0.0% |
| frequency at the shipped line | 0.51 | 0.45 | 0.62 | 0.65 | 0.68 | 0.65 | 0.63 | 0.61 | 0.57 | 0.57 | 0.61 | 0.68 |
| iced cells borrowed at coasts | 0.18 | 0.12 | 0.17 | 0.21 | 0.21 | 0.22 | 0.22 | 0.23 | 0.23 | 0.23 | 0.22 | 0.20 |
| iced NSIDC cells the atlas calls land | 0.03 | 0.02 | 0.02 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 | 0.03 |
