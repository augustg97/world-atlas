# Close in: land or water (registers A12, A15)

At 23 places, 19 m a texel, against ESA WorldCover 2021 (10 m; class 80, permanent water). **Tiles**: JRC Global Surface Water as the page reads it (water in at least half of 1984-2021), the page's source since release 1.7. **Rule**: NASA's MODIS mask sharpened by the picture (`water.js :: waterFlag`, run under node), release 1.6's source and the stand-in where the record has no tiles.
Wrong = texels called water that are land, plus texels called land that are water, as a share of all texels in the box. Frame = texels where the tiles differ from the record's own 30 m file.

| place | water | tiles: false | missed | IoU | rule: wrong | IoU | MODIS alone: wrong | IoU | shipped 5 km: wrong | frame |
|---|---|---|---|---|---|---|---|---|---|---|
| albany | 1.8% | 0.0% | 0.5% | 0.74 | 0.6% | 0.71 | 1.3% | 0.42 | 1.8% | 0.14% |
| amsterdam | 25.1% | 0.5% | 2.4% | 0.89 | 4.1% | 0.84 | 6.1% | 0.77 | 11.2% | 0.75% |
| boston | 32.6% | 0.5% | 1.4% | 0.94 | 3.0% | 0.91 | 5.4% | 0.84 | 14.9% | 0.72% |
| cairo | 4.0% | 0.1% | 1.2% | 0.68 | 0.9% | 0.78 | 2.8% | 0.40 | 4.0% | 0.39% |
| chittagong | 30.7% | 0.3% | 1.7% | 0.94 | 3.7% | 0.88 | 4.2% | 0.86 | 10.6% | 0.46% |
| cremona | 2.3% | 0.0% | 0.6% | 0.72 | 1.5% | 0.37 | 1.8% | 0.40 | 2.3% | 0.22% |
| deadsea | 56.6% | 1.4% | 0.0% | 0.98 | 0.7% | 0.99 | 4.7% | 0.92 | 12.8% | 0.15% |
| dhaka | 5.7% | 0.5% | 2.3% | 0.55 | 4.7% | 0.18 | 4.9% | 0.23 | 5.7% | 0.77% |
| garda | 45.8% | 0.0% | 0.4% | 0.99 | 0.6% | 0.99 | 1.2% | 0.97 | 8.2% | 0.15% |
| ismailia | 6.5% | 0.2% | 2.3% | 0.62 | 3.2% | 0.51 | 4.2% | 0.42 | 6.5% | 0.48% |
| laport | 43.6% | 0.2% | 0.9% | 0.98 | 1.1% | 0.97 | 3.9% | 0.91 | 6.9% | 0.46% |
| lyon | 2.8% | 0.1% | 0.8% | 0.68 | 1.5% | 0.52 | 2.6% | 0.31 | 2.8% | 0.39% |
| manaus | 33.4% | 4.5% | 1.2% | 0.85 | 6.3% | 0.83 | 8.9% | 0.77 | 22.2% | 0.94% |
| manhattan | 18.8% | 0.4% | 1.6% | 0.90 | 4.0% | 0.80 | 17.7% | 0.47 | 17.7% | 0.79% |
| mead | 16.9% | 2.7% | 0.1% | 0.86 | 0.6% | 0.97 | 7.9% | 0.68 | 16.1% | 0.33% |
| montreux | 27.7% | 0.0% | 0.4% | 0.98 | 0.7% | 0.97 | 1.3% | 0.95 | 10.5% | 0.17% |
| paris | 2.0% | 0.1% | 0.7% | 0.63 | 1.9% | 0.12 | 2.2% | 0.08 | 2.0% | 0.38% |
| portsaid | 61.6% | 4.1% | 2.6% | 0.90 | 12.8% | 0.82 | 16.4% | 0.78 | 28.5% | 1.28% |
| rotterdam | 10.6% | 0.2% | 2.3% | 0.77 | 4.7% | 0.63 | 7.2% | 0.50 | 10.6% | 0.74% |
| sandiego | 45.4% | 0.1% | 1.1% | 0.97 | 2.3% | 0.95 | 5.2% | 0.89 | 19.7% | 0.52% |
| santarem | 46.7% | 4.8% | 1.6% | 0.88 | 7.6% | 0.85 | 8.7% | 0.83 | 12.9% | 0.65% |
| venice | 61.3% | 0.8% | 2.4% | 0.95 | 6.9% | 0.89 | 8.7% | 0.87 | 28.4% | 1.25% |
| zermatt | 0.6% | 0.1% | 0.3% | 0.40 | 0.5% | 0.21 | 0.5% | 0.15 | 0.6% | 0.07% |
| **mean** | | 0.93% | 1.25% | 0.82 | 3.21% | 0.73 | 5.58% | 0.63 | 11.17% | worst 1.28% |

The tiles' wrong texels by texel size (pooled): 19 m 2.19%, 76 m 2.08%, 152 m 1.92%, 304 m 1.85%, 494 m 1.77%.
Places where the tiles are worse than the MODIS mask alone at any texel size: 0.

Places where the tiles are worse than release 1.6's rule by over 0.4 points, each a difference of DATE and not of place: cairo (1.3% against 0.9%); deadsea (1.4% against 0.7%); mead (2.8% against 0.6%). The record's shore there is the 1984-2021 majority; the witness (2021) and the picture (2016) both have the water lower (Lake Mead, the Dead Sea) or the ground reworked (Cairo's canals). The rule followed the picture.

Read the low rows for what they are. Manaus, Santarem: seasonally flooded forest, wetland to the witness and water to the record. Port Said: salt pans and basins flooded since. Venice, Chittagong: tidal flats. Zermatt: 0.3% of the box is water, and as much again is the witness's own false water in mountain shadow.
