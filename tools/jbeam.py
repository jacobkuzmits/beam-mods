"""Lenient jbeam reader + part-config resolver (BeamNG).

jbeam is JSON with comments, trailing commas and optional commas, so this
tokenizer simply treats commas as whitespace.
"""
import glob
import json
import os
import re
import sys

_TOK = re.compile(r'''
    (?P<ws>\s+|,|//[^\n]*|/\*.*?\*/)
  | (?P<str>"(?:\\.|[^"\\])*")
  | (?P<num>-?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?)
  | (?P<lit>true|false|null)
  | (?P<punct>[{}\[\]:])
''', re.S | re.X)


def loads(text):
    toks = []
    pos = 0
    n = len(text)
    while pos < n:
        m = _TOK.match(text, pos)
        if not m:
            raise ValueError(f"bad jbeam at {pos}: {text[pos:pos+40]!r}")
        pos = m.end()
        k = m.lastgroup
        if k == "ws":
            continue
        toks.append((k, m.group(k)))
    i = 0

    def val():
        nonlocal i
        k, v = toks[i]
        i += 1
        if k == "str":
            return json.loads(v)
        if k == "num":
            return float(v) if any(c in v for c in ".eE") else int(v)
        if k == "lit":
            return {"true": True, "false": False, "null": None}[v]
        if v == "{":
            d = {}
            while toks[i][1] != "}":
                key = val()
                assert toks[i][1] == ":", toks[i]
                i += 1
                d[key] = val()
            i += 1
            return d
        if v == "[":
            a = []
            while toks[i][1] != "]":
                a.append(val())
            i += 1
            return a
        raise ValueError(f"unexpected token {v!r}")

    return val()


def load_parts(dirs):
    parts = {}
    for d in dirs:
        for f in sorted(glob.glob(os.path.join(d, "**", "*.jbeam"), recursive=True)):
            try:
                data = loads(open(f, encoding="utf-8", errors="replace").read())
            except Exception as e:  # noqa: BLE001
                print("WARN parse", f, e, file=sys.stderr)
                continue
            for name, p in data.items():
                if isinstance(p, dict):
                    p["__file__"] = f
                    parts[name] = p
    return parts


def slots_of(p):
    """Yield (slotName, defaultPart) for both slots and slots2 formats."""
    if "slots2" in p:
        rows = p["slots2"]
        for r in rows[1:]:
            if isinstance(r, list):
                yield r[0], r[3] if len(r) > 3 else ""
    for r in p.get("slots", [])[1:]:
        if isinstance(r, list):
            yield r[0], r[1] if len(r) > 1 else ""


def resolve(parts, main, chosen):
    """Return list of (slot, partName) actually used by a config."""
    by_slot = {}
    for name, p in parts.items():
        st = p.get("slotType")
        if isinstance(st, list):
            for s in st:
                by_slot.setdefault(s, []).append(name)
        elif st:
            by_slot.setdefault(st, []).append(name)
    out = []

    def walk(pname, slot):
        if pname not in parts:
            out.append((slot, pname + " (MISSING)"))
            return
        out.append((slot, pname))
        for s, default in slots_of(parts[pname]):
            sel = chosen.get(s, default)
            if sel:
                walk(sel, s)

    walk(main, "main")
    return out


def flexbody_meshes(part):
    meshes = []
    for r in part.get("flexbodies", [])[1:]:
        if isinstance(r, list) and r and isinstance(r[0], str):
            meshes.append(r[0])
    for r in part.get("props", [])[1:]:
        if isinstance(r, list) and len(r) > 1 and isinstance(r[1], str):
            meshes.append(r[1])
    return meshes


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("pc")
    ap.add_argument("dirs", nargs="+")
    a = ap.parse_args()
    pc = json.load(open(a.pc))
    parts = load_parts(a.dirs)
    used = resolve(parts, pc.get("mainPartName", pc.get("model")), pc["parts"])
    for slot, p in used:
        ms = flexbody_meshes(parts.get(p, {}))
        print(f"{slot:40s} {p:45s} {' '.join(ms)}")
