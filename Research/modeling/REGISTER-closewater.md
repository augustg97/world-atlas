# Close in: land or water (register A12)

The app's rule (`web/js/detail.js :: waterFlag`, run under node) at 23 places, 19 m a texel, against JRC Global Surface Water (30 m, water at least half of 1984-2021).
Wrong = texels called water that are land, plus texels called land that are water, as a share of all texels in the box.

| place | water | rule: false | missed | IoU | MODIS alone: wrong | IoU | shipped 5 km: wrong | IoU |
|---|---|---|---|---|---|---|---|---|
| albany | 1.4% | 0.3% | 0.2% | 0.71 | 1.2% | 0.41 | 1.4% | 0.00 |
| amsterdam | 23.2% | 1.1% | 1.7% | 0.89 | 4.3% | 0.83 | 9.2% | 0.66 |
| boston | 31.7% | 1.0% | 2.1% | 0.91 | 4.9% | 0.85 | 14.2% | 0.58 |
| cairo | 2.9% | 0.7% | 0.4% | 0.69 | 2.5% | 0.38 | 2.9% | 0.00 |
| chittagong | 29.4% | 0.6% | 1.8% | 0.92 | 3.0% | 0.90 | 9.6% | 0.70 |
| cremona | 1.7% | 0.1% | 0.9% | 0.46 | 1.5% | 0.41 | 1.7% | 0.00 |
| deadsea | 58.0% | 0.0% | 0.8% | 0.99 | 3.5% | 0.94 | 11.5% | 0.83 |
| dhaka | 4.2% | 0.2% | 3.2% | 0.23 | 3.6% | 0.27 | 4.2% | 0.00 |
| garda | 45.5% | 0.1% | 0.3% | 0.99 | 1.1% | 0.98 | 8.1% | 0.85 |
| ismailia | 4.6% | 0.2% | 1.3% | 0.69 | 2.5% | 0.54 | 4.6% | 0.00 |
| laport | 43.0% | 0.3% | 0.7% | 0.98 | 3.6% | 0.92 | 6.4% | 0.86 |
| lyon | 2.1% | 0.5% | 0.8% | 0.53 | 2.3% | 0.30 | 2.1% | 0.00 |
| manaus | 36.9% | 1.4% | 2.3% | 0.90 | 6.4% | 0.84 | 24.1% | 0.42 |
| manhattan | 17.8% | 1.6% | 2.0% | 0.81 | 17.1% | 0.48 | 16.7% | 0.09 |
| mead | 19.5% | 0.1% | 3.0% | 0.85 | 5.4% | 0.78 | 14.3% | 0.56 |
| montreux | 27.3% | 0.3% | 0.3% | 0.98 | 1.1% | 0.96 | 10.2% | 0.69 |
| paris | 1.5% | 0.1% | 1.2% | 0.13 | 1.7% | 0.08 | 1.5% | 0.00 |
| portsaid | 63.3% | 6.4% | 2.7% | 0.87 | 12.8% | 0.82 | 26.2% | 0.70 |
| rotterdam | 8.6% | 2.4% | 1.3% | 0.66 | 6.0% | 0.53 | 8.6% | 0.00 |
| sandiego | 44.5% | 0.2% | 1.5% | 0.96 | 4.8% | 0.90 | 19.0% | 0.59 |
| santarem | 50.1% | 0.4% | 5.2% | 0.89 | 5.4% | 0.90 | 10.5% | 0.81 |
| venice | 59.8% | 0.9% | 4.8% | 0.91 | 7.9% | 0.88 | 27.2% | 0.60 |
| zermatt | 0.3% | 0.0% | 0.2% | 0.35 | 0.3% | 0.25 | 0.3% | 0.00 |
| **mean** | | 0.83% | 1.67% | 0.75 | 4.48% | 0.66 | 10.2% | 0.39 |

Wrong texels by texel size (the picture pooled): 19 m 2.5%, 76 m 2.5%, 152 m 2.57%, 304 m 2.83%, 494 m 2.82%.
Places where the rule is worse than the mask alone at any texel size: 1: venice at 494 m: 6.1% against 5.3%.
Slowest place: 163 ms for about a million texels.

Read the low rows for what they are. Paris, Lyon, Cremona, Dhaka, Zermatt: rivers and tarns MODIS has little or none of; the rule adds no water there by design. Manhattan: MODIS holds most of the island as water and the rule takes it back. Port Said, Venice, Chittagong, Lake Mead: salt pans, tidal flats and a fallen reservoir, where a 38-year record and one 2016 picture are different things.
