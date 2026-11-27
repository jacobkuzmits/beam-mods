"""Generate Kestrel K5 jbeam + materials and package the mod.

Physics for every size is copied verbatim from the pack's CN505 parts (same
mounting geometry), only the part keys, display names and mesh names change.

Usage:
  python3 -I package.py --cn505 DIR --dae kestrel_k5.dae --out OUTDIR
"""
import argparse
import json
import os
import re
import zipfile

SIZES = ["15x8", "15x9", "15x10", "16x8", "18x8", "18x9", "18x10"]
FINISHES = {"s": "Polished", "b": "Black", "c": "Colorable"}
MOD_DIR = "vehicles/common/wheels/wheels_5lug/kestrel_k5"
BRAND = "Kestrel K5 Vintage 5-Spoke"

MATERIALS = {
    "kestrel_k5_polished": dict(baseColorFactor=[0.86, 0.87, 0.89, 1], metallicFactor=1, roughnessFactor=0.13),
    "kestrel_k5_chrome":   dict(baseColorFactor=[0.95, 0.95, 0.97, 1], metallicFactor=1, roughnessFactor=0.04),
    "kestrel_k5_black":    dict(baseColorFactor=[0.02, 0.02, 0.022, 1], metallicFactor=0, roughnessFactor=0.3,
                                clearCoatFactor=0.6, clearCoatRoughnessFactor=0.05),
    "kestrel_k5_paint":    dict(baseColorFactor=[1, 1, 1, 1], metallicFactor=0.2, roughnessFactor=0.3,
                                clearCoatFactor=1, clearCoatRoughnessFactor=0.03, instanceDiffuse=True),
}


def split_blocks(text):
    """Return {key: block_text} for the top-level parts of a jbeam file."""
    out = {}
    pat = re.compile(r'^"([^"]+)"\s*:\s*\{.*?^\},?\s*$', re.S | re.M)
    for m in pat.finditer(text):
        out[m.group(1)] = m.group(0).rstrip().rstrip(",")
    return out


def find(blocks, size, front):
    want = f"cn505_{size}_f" if front else f"cn505_{size}"
    for k, b in blocks.items():
        if k.lower() == want:
            return b
    raise KeyError(f"cn505 {size} {'F' if front else 'R'} not found")


def convert(block, size, fin, front):
    pos = "Front" if front else "Rear"
    key = f"kestrel_k5_{fin}_{size}_{'F' if front else 'R'}"
    mesh = f"kestrel_k5_{size}_{fin}"
    b = re.sub(r'^"[^"]+"', f'"{key}"', block, count=1)
    b, n = re.subn(r'"name"\s*:\s*"[^"]*"',
                   f'"name":"{size} {BRAND} {pos} Wheels ({FINISHES[fin]})"', b, count=1)
    assert n == 1
    b = re.sub(r'"authors"\s*:\s*"[^"]*"', '"authors":"BeamNG, Kestrel K5 add-on"', b, count=1)
    b, n = re.subn(r'\["cn505_' + re.escape(size) + r'"', f'["{mesh}"', b)
    assert n == 2, (size, fin, front, n)
    # drop CN505-only extra meshes (e.g. the 16x8 "insert") that don't fit this wheel
    b = re.sub(r'^[ \t]*\["cn505_[^"]*",[^\n]*\n', "", b, flags=re.M)
    assert "cn505" not in b.lower(), b
    return b


def lenient_json(text):
    """Very small jbeam -> JSON normaliser used only as a syntax sanity check."""
    t = re.sub(r"//[^\n]*", "", text)
    t = re.sub(r"/\*.*?\*/", "", t, flags=re.S)
    t = re.sub(r",(\s*[}\]])", r"\1", t)
    return json.loads(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cn505", required=True)
    ap.add_argument("--dae", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    fb = split_blocks(open(os.path.join(a.cn505, "wheels_F_5_cn505.jbeam"), encoding="utf-8").read())
    rb = split_blocks(open(os.path.join(a.cn505, "wheels_R_5_cn505.jbeam"), encoding="utf-8").read())

    files = {}
    for fin in FINISHES:
        for front, src, tag in ((True, fb, "F"), (False, rb, "R")):
            parts = [convert(find(src, s, front), s, fin, front) for s in SIZES]
            txt = "{\n" + ",\n\n".join(parts) + "\n}\n"
            parsed = lenient_json(txt)
            assert len(parsed) == len(SIZES)
            for k, v in parsed.items():
                assert v["slotType"] == f"wheel_{tag}_5", k
            files[f"{MOD_DIR}/wheels_{tag}_5_kestrel_k5_{fin}.jbeam"] = txt.encode()

    mats = {}
    for name, stage0 in MATERIALS.items():
        mats[name] = {
            "name": name, "mapTo": name, "class": "Material",
            "Stages": [stage0, {}, {}, {}],
            "dynamicCubemap": True, "materialTag0": "beamng", "materialTag1": "vehicle",
            "version": 1.5,
        }
    files[f"{MOD_DIR}/kestrel_k5.materials.json"] = json.dumps(mats, indent=2).encode()
    files[f"{MOD_DIR}/kestrel_k5.dae"] = open(a.dae, "rb").read()

    os.makedirs(a.out, exist_ok=True)
    addon = os.path.join(a.out, "vintage_wheels_kestrel_k5_addon.zip")
    with zipfile.ZipFile(addon, "w", zipfile.ZIP_DEFLATED) as z:
        for p, data in sorted(files.items()):
            z.writestr(p, data)
    print("wrote", addon, os.path.getsize(addon))


if __name__ == "__main__":
    main()
