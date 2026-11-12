# Streets and buildings against WorldCover's built-up ground

Written by `audit_streets.py`. OpenStreetMap's building footprints (OpenFreeMap, zoom 14), read by the page's own decoder and frame, against ESA WorldCover 2021 class 50, over the middle 5 km of each place.

| place | tiles | footprint share of the ground | slide for best agreement, east (m) | south (m) | footprint not on built-up | on water | correlation falls when slid 60 m |
|---|---|---|---|---|---|---|---|
| manhattan | 16 | 33% | -2 | -7 | 4% | 0.2% | 12% |
| paris | 16 | 48% | -3 | -7 | 2% | 0.0% | 39% |
| boston | 16 | 23% | -6 | -9 | 5% | 0.5% | 23% |
| amsterdam | 20 | 8% | -3 | -4 | 21% | 0.6% | 31% |
| rotterdam | 16 | 15% | -4 | -4 | 10% | 0.7% | 29% |
| lyon | 16 | 29% | -8 | -9 | 9% | 0.2% | 44% |
| sandiego | 12 | 15% | -10 | -5 | 5% | 0.8% | 11% |
| albany | 12 | 12% | -4 | -6 | 16% | 0.1% | 30% |

Summary: `{"off_m": 12.3, "off_mean_m": 8.4, "built_miss_pct": 9.1, "on_water_pct": 0.39, "slid_drop_pct": 27.2, "places": 8}`
