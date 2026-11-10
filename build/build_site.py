#!/usr/bin/env python3
"""Build the published site: docs/ from web/. GitHub Pages serves main:/docs.

    ./venv/bin/python build/build_site.py            # audits first, then builds
    SKIP_AUDIT=1 ./venv/bin/python build/build_site.py

Three things it does that a plain copy would not:

1. It refuses to build if the audit suite has moved backwards (Research/modeling/audit_all.py).
2. It stamps the CODE. Fields, data and shaders already carry ?v=<data stamp> at run time, but a static
   host serves .js and .css with a cache lifetime, so a returning browser could run last week's code
   against this week's fields. Every module import, the stylesheet and the entry script get ?v=<code
   stamp> here. version.json is written BEFORE anything else is copied, and carries both stamps.
3. It leaves development-only files out: the EPIC camera list and the reference-render helper.

It never pushes. Publishing is `git push`, and CLAUDE.md rule 16 says who decides that.
"""
from __future__ import annotations

import datetime
import json
import os
import re
import shutil
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
WEB, DOCS = os.path.join(ROOT, "web"), os.path.join(ROOT, "docs")
LEAVE_OUT = {"dev", os.path.join("js", "refshots.js")}


def main():
    if os.environ.get("SKIP_AUDIT") != "1":
        r = subprocess.run([os.path.join(ROOT, "venv", "bin", "python"), os.path.join(ROOT, "Research", "modeling", "audit_all.py")], cwd=ROOT)
        if r.returncode != 0:
            print("build_site: the audit suite failed; nothing built")
            return 1
    else:
        print("SKIP_AUDIT=1 - building without the audits. Say so out loud, and say why.")

    data_v = json.load(open(os.path.join(WEB, "version.json")))["data"]
    code_v = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    if os.path.isdir(DOCS):
        shutil.rmtree(DOCS)
    os.makedirs(DOCS)
    # the stamp first: if the copy dies half way, the half-built site still cannot claim to be the old one
    with open(os.path.join(DOCS, "version.json"), "w") as fh:
        json.dump({"data": data_v, "code": code_v}, fh)
    open(os.path.join(DOCS, ".nojekyll"), "w").close()          # Pages must not run Jekyll over the tree

    n_files = n_stamped = 0
    for dirpath, dirnames, filenames in os.walk(WEB):
        rel = os.path.relpath(dirpath, WEB)
        rel = "" if rel == "." else rel
        dirnames[:] = [d for d in dirnames if os.path.join(rel, d) not in LEAVE_OUT]
        os.makedirs(os.path.join(DOCS, rel), exist_ok=True)
        for f in filenames:
            r = os.path.join(rel, f)
            if r in LEAVE_OUT or f == "version.json" or f.startswith("."):
                continue
            src, dst = os.path.join(dirpath, f), os.path.join(DOCS, r)
            if f.endswith(".js"):
                s = open(src).read()
                s, k = re.subn(r"""(from\s+['"])(\.{1,2}/[\w./-]+\.js)(['"])""", rf"\1\2?v={code_v}\3", s)
                n_stamped += k
                open(dst, "w").write(s)
            elif f == "index.html":
                s = open(src).read()
                s, k1 = re.subn(r'(href="css/[\w.-]+\.css)(")', rf"\1?v={code_v}\2", s)
                s, k2 = re.subn(r'(src="js/[\w.-]+\.js)(")', rf"\1?v={code_v}\2", s)
                assert k1 == 1 and k2 == 1, "index.html no longer has one stylesheet and one entry script: fix the stamping"
                n_stamped += k1 + k2
                open(dst, "w").write(s)
            else:
                shutil.copy2(src, dst)
            n_files += 1

    # what must be true of the result
    idx = open(os.path.join(DOCS, "index.html")).read()
    assert f"js/main.js?v={code_v}" in idx
    unstamped = []
    for d, _, fs in os.walk(os.path.join(DOCS, "js")):
        for f in fs:
            if not f.endswith(".js"):
                continue
            for m in re.finditer(r"""from\s+['"](\.{1,2}/[\w./-]+\.js)(\?v=[\w]+)?['"]""", open(os.path.join(d, f)).read()):
                if not m.group(2):
                    unstamped.append((f, m.group(1)))
    assert not unstamped, f"imports without a stamp: {unstamped}"
    assert not os.path.exists(os.path.join(DOCS, "dev")) and not os.path.exists(os.path.join(DOCS, "js", "refshots.js"))
    size = sum(os.path.getsize(os.path.join(d, f)) for d, _, fs in os.walk(DOCS) for f in fs)
    print(f"docs/: {n_files} files, {size / 1e6:.1f} MB; {n_stamped} code URLs stamped; data {data_v}, code {code_v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
