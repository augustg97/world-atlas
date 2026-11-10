#!/usr/bin/env python3
"""Stamp the data version. Every build step calls stamp() when it finishes; the app fetches
web/version.json uncached and appends ?v=<stamp> to every field and data URL, so a browser
can never show a field older than the last build (TRAPS D2 - it has happened here once already:
a cached climate.json with two of twelve encodings crashed the tracers).
    ./venv/bin/python build/stamp.py
"""
import datetime, json, os

def stamp():
    p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "version.json")
    v = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json.dump({"data": v}, open(p, "w"))
    print(f"  data version {v}")
    return v

if __name__ == "__main__":
    stamp()
