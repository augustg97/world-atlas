# The atlas on a real GPU (audit_gpu.py)

Renderer: ANGLE (Apple, ANGLE Metal Renderer: Apple M5 Ultra, Unspecified Version). Texture units: 16.

| frame | verdict | mean difference, levels | pixels more than 24 levels apart |
|---|---|---|---|
| globe-default | ok | 0.18 | 0.03% |
| globe-night-asia | ok | 0.14 | 0.04% |
| globe-motion-atlantic | ok | 0.48 | 0.14% |
| region-himalaya | ok | 0.28 | 0.20% |
| sheet-atlas | ok | 0.73 | 0.59% |
| sheet-lens-temp | ok | 0.33 | 0.05% |

Lights into the imagery texture's alpha: worst error 0.40 of 255; colour moved by 0; GL state restored: True.
