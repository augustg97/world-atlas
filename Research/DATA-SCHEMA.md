# Data schema — World Atlas

The shapes every data file uses. Keep this next to the data, and keep the schema visible in each
file's own header comment too — a contributor reads the file, not the docs.

---

## The universal fields

Every entity, of every kind, carries these:

```js
{
  id:      "unique-slug",          // stable; referenced by other records. NEVER recycle.
  name:    "Display Name",
  kind:    "city" | "treaty" | ... // drives the eyebrow, the icon and the layer toggle
  from:    1630,                   // enters the model
  to:      2026,                   // leaves it; omit or null for "still present"
  confidence: "good",              // good | moderate | contested — a FIELD, not a footnote
  sources: ["Author (year), Title", ...]
}
```

Rules:

- **`from`/`to` are the drawing window**, and must sit inside whatever lifetime the research
  models assert. The existence-window audit checks exactly this.
- **`confidence` is required** on anything the record does not settle. The UI renders it; an
  audit checks that contested things are not stated flatly.
- **`sources` is required.** A card without a source is an assertion.

## Time-aware prose

Anything that persists across eras carries an `eras` array rather than one description:

```js
eras: [
  {from: 1750, to: 1775, text: "…"},
  {from: 1775, to: 1830, text: "…"},
]
```

- The eras must **tile the entity's life with no gaps and no overlaps** — audited.
- `eraSpanFor(obj, t)` shows the reader which span they are looking at, so a 19th-century
  paragraph is never mistaken for a current description.

## Fact rows

```js
facts: [["Founded", "1630, Massachusetts Bay Colony"],
        ["Role",    "Colonial port; cradle of the Revolution"]]
```

Two to four. Label short, value specific and dated.

## Series

```js
pop: [[1750, 15000], [1800, 24937], [1850, 136881], …]
```

Sparse, ascending, `[t, value]`. One interpolator (`interpSeries`) reads all of them; one
last-value-at-or-before reader (`lastLE`) reads the step-valued ones. Never write a second.

## Geometry

```js
geom: {type: "Polygon"|"LineString"|"Point", coordinates: [...]}   // GeoJSON, lon/lat, WGS84
```

- **One canonical frame** — see `SCOPE.md` §5. Any source in a different frame is converted on
  the way in, by tested code, never by eye.
- **Authored geometry is labelled as authored** in the card, with what it was traced along.
- **Geometry that changes shape is resolved by rules** from one modern source, not stored once
  per time step.

## Curated overrides

Where a model generates the default:

```js
{ …, exception: true, why: "atypical for its province — that is the point of the entry" }
```

- `exception: true` means the model must **never** speak over this entry.
- An audit checks the flag against a reading of the entry, so a new curated entry **has to
  declare itself**.

## Files

- One file per kind: `data/<kind>.js`, assigning into a single namespace object.
- **The schema is visible in each file's header comment.** To add an item, append an object.
- Contiguity requirements stated where they exist ("`eras` must be contiguous and end at
  {{END_YEAR}}").
- If the app must run from `file://`, data ships as `.js` literals rather than fetched `.json`.
