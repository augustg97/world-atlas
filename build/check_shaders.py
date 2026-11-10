#!/usr/bin/env python3
"""Pre-flight: resolve #includes and compile every shader in web/shaders with glslangValidator.
    ./venv/bin/python build/check_shaders.py        exit 1 on any error
Shaders are separate .glsl files fetched at runtime, so the backtick-in-a-template-literal
failure (TRAPS C6) cannot happen here; this catches everything else before the browser does.
"""
import os, re, subprocess, sys, tempfile, glob
D = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "shaders")

def load(p):
    out = []
    for line in open(p).read().split("\n"):
        m = re.match(r'\s*#include\s+"([^"]+)"', line)
        out.append(load(os.path.join(D, m.group(1))) if m else line)
    return "\n".join(out)

bad = 0
for p in sorted(glob.glob(os.path.join(D, "*.vert.glsl")) + glob.glob(os.path.join(D, "*.frag.glsl"))):
    stage = "vert" if p.endswith(".vert.glsl") else "frag"
    with tempfile.NamedTemporaryFile("w", suffix="." + stage, delete=False) as t:
        t.write(load(p))
    r = subprocess.run(["glslangValidator", t.name], capture_output=True, text=True)
    os.unlink(t.name)
    print(f"  {'ok  ' if r.returncode == 0 else 'FAIL'} {os.path.basename(p)}")
    if r.returncode:
        bad += 1
        print(r.stdout)
    # WebGL2 guarantees 16 texture units to a fragment shader and real GPUs (ANGLE Metal on Apple silicon)
    # give exactly 16; the software GL the headless audits run on gives 32. A seventeenth sampler therefore
    # passes every headless check and is a black page on a real machine. It happened once (2026-11-10).
    n = len(re.findall(r"^\s*uniform\s+(?:lowp|mediump|highp)?\s*sampler\w+\s+\w+", load(p), re.M))
    if n > 16:
        bad += 1
        print(f"  FAIL {os.path.basename(p)} declares {n} samplers; the limit is 16 (MAX_TEXTURE_IMAGE_UNITS)")
    elif n:
        print(f"       {os.path.basename(p)} uses {n} of 16 texture units")
sys.exit(1 if bad else 0)
