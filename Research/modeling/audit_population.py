"""Population: the shipped field summed per country against World Bank national totals (register F2).

The per-country sums are written by build/fields_human.py (step countries) from the same GHSL grid
and the same country raster the app ships, into data/_cache/pop_by_country.json. The witness is
web/data/stats.json (World Bank SP.POP.TOTL, most recent year), joined on the World Bank code the
app itself uses. GHSL is the 2025 epoch, so a few percent of drift from vintage alone is expected;
the audit lists every unit of more than 100,000 people that is off by more than 10%.

    ./venv/bin/python Research/modeling/audit_population.py [--json] [--selftest]
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
TOL = 0.10


def compare(field, witness, tol=TOL, floor=1e5):
    rows = []
    for code, (wb, name, got) in field.items():
        want = witness.get(wb)
        if want is None or want < floor:
            continue
        rows.append((abs(got - want) / want, code, name, got, want))
    rows.sort(reverse=True)
    return rows, [r for r in rows if r[0] > tol]


def selftest():
    f = {"AAA": ("AAA", "A", 1.0e6), "BBB": ("BBB", "B", 2.5e6), "CCC": ("CCC", "tiny", 9e4), "DDD": ("XXX", "no witness", 5e6)}
    w = {"AAA": 1.02e6, "BBB": 2.0e6, "CCC": 5e4}
    rows, off = compare(f, w)
    assert len(rows) == 2 and [r[1] for r in off] == ["BBB"], (rows, off)
    print("audit_population selftest: ok")


def main():
    if "--selftest" in sys.argv:
        return selftest()
    cache = os.path.join(ROOT, "data", "_cache", "pop_by_country.json")
    if not os.path.exists(cache):
        raise SystemExit(f"cannot run: {cache} is missing. Rebuild it with ./venv/bin/python build/fields_human.py countries")
    sums = json.load(open(cache))
    pol = json.load(open(os.path.join(ROOT, "web", "data", "political.json")))["countries"]
    stats = json.load(open(os.path.join(ROOT, "web", "data", "stats.json")))["by_code"]
    witness = {k: v["SP.POP.TOTL"][0] for k, v in stats.items() if v.get("SP.POP.TOTL")}
    field = {c["a3"]: (c["wb"], c["name"], sums[c["a3"]]) for c in pol if c["a3"] in sums and c.get("wb")}
    rows, off = compare(field, witness)
    tot_f, tot_w = sum(r[3] for r in rows), sum(r[4] for r in rows)
    res = {"units_off_10pct": len(off), "compared": len(rows), "total_err_pct": round(abs(tot_f - tot_w) / tot_w * 100, 2)}
    lines = ["# Population: GHSL field summed per country against World Bank totals", "",
             f"{len(rows)} units compared; summed field {tot_f/1e9:.3f} bn against {tot_w/1e9:.3f} bn ({(tot_f-tot_w)/tot_w*100:+.2f}%). "
             f"{len(off)} units differ by more than {TOL*100:.0f}%.", "", "| unit | field | World Bank | difference |", "|---|---|---|---|"]
    for e, code, name, got, want in off:
        lines.append(f"| {name} ({code}) | {got:,.0f} | {want:,.0f} | {(got-want)/want*100:+.0f}% |")
    open(os.path.join(HERE, "REGISTER-population.md"), "w").write("\n".join(lines) + "\n")
    if "--json" not in sys.argv:
        print("\n".join(lines))
    print(json.dumps(res))


if __name__ == "__main__":
    main()
