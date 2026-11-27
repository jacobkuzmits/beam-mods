"""Generate the Aria '83 Hatch add-on: jbeam parts, materials, config, zip.

All new parts are copies of the Aria's own parts (same nodes, beams,
triangles, mass, slots and light bulbs), so physics are unchanged; only the
visual meshes, light glow materials and (for the exhaust) sound differ.

python3 -I package_h83.py --aria ARIA_VEHICLES_DIR --build BUILD_DIR --out DIST_DIR [--thumb thumb.jpg] [--bundle ARIA.zip]
"""
import argparse
import copy
import json
import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "tools"))
import jbeam  # noqa: E402

VDIR = "vehicles/ariahatch"
SUB = VDIR + "/hatch83"
AUTH = "kajzer (original Aria), '83 Hatch add-on"
PC_NAME = "h83_hatch_M"

# ------------------------------------------------------------ materials
def mat(name, stage, **top):
    d = {"name": name, "mapTo": name, "class": "Material", "Stages": [stage, {}, {}, {}],
         "dynamicCubemap": True, "materialTag0": "beamng", "materialTag1": "vehicle", "version": 1.5}
    d.update(top)
    return d




def lens(name, color, emissive, opacity, nits, prism=False):
    extra = {"normalMap": PRISM_N} if prism else {}
    off = mat(name, dict({"baseColorFactor": color + [1], "metallicFactor": 0, "roughnessFactor": 0.05,
                          "opacityFactor": opacity}, **extra), translucent=True, translucentZWrite=False)
    on = mat(name + "_on", dict({"baseColorFactor": color + [1], "metallicFactor": 0, "roughnessFactor": 0.05,
                                 "opacityFactor": opacity, "emissiveFactor": emissive,
                                 "emissiveIntensityNits": nits}, **extra), translucent=True, translucentZWrite=False)
    return {name: off, name + "_on": on}


PRISM_N = "/vehicles/ariahatch/hatch83/h83_lens_prism_n.png"

MATERIALS = {
    "h83_black_plastic": mat("h83_black_plastic", {"baseColorFactor": [0.035, 0.035, 0.037, 1],
                                                   "metallicFactor": 0, "roughnessFactor": 0.55}),
    "h83_black_trim": mat("h83_black_trim", {"baseColorFactor": [0.02, 0.02, 0.021, 1],
                                             "metallicFactor": 0, "roughnessFactor": 0.35}),
    "h83_grille_black": mat("h83_grille_black", {"baseColorFactor": [0.025, 0.025, 0.026, 1],
                                                 "metallicFactor": 0.1, "roughnessFactor": 0.45}),
    "h83_chrome": mat("h83_chrome", {"baseColorFactor": [0.95, 0.95, 0.97, 1],
                                     "metallicFactor": 1, "roughnessFactor": 0.05}),
    "h83_reflector": mat("h83_reflector", {"baseColorFactor": [0.9, 0.9, 0.92, 1],
                                           "metallicFactor": 1, "roughnessFactor": 0.12}),
    "h83_wheel_silver": mat("h83_wheel_silver", {"baseColorFactor": [0.62, 0.63, 0.65, 1],
                                                 "metallicFactor": 0.8, "roughnessFactor": 0.35,
                                                 "clearCoatFactor": 0.5, "clearCoatRoughnessFactor": 0.1}),
    "h83_bumper_strip": mat("h83_bumper_strip", {"baseColorFactor": [0.78, 0.79, 0.81, 1],
                                                 "metallicFactor": 0.9, "roughnessFactor": 0.22}),
    "h83_lamp_back": mat("h83_lamp_back", {"baseColorFactor": [0.85, 0.85, 0.87, 1],
                                           "metallicFactor": 1, "roughnessFactor": 0.22}),
    "h83_lamp_frame": mat("h83_lamp_frame", {"baseColorFactor": [0.06, 0.06, 0.065, 1],
                                             "metallicFactor": 0, "roughnessFactor": 0.4}),
    "h83_reflector_red": mat("h83_reflector_red", {"baseColorFactor": [0.45, 0.02, 0.02, 1],
                                                   "metallicFactor": 0.3, "roughnessFactor": 0.15,
                                                   "clearCoatFactor": 1, "clearCoatRoughnessFactor": 0.02,
                                                   "normalMap": PRISM_N}),
}
MATERIALS.update(lens("h83_lens_clear", [0.92, 0.93, 0.95], [1.0, 0.95, 0.85], 0.45, 7500))
MATERIALS.update(lens("h83_lens_clear_prism", [0.92, 0.93, 0.95], [1.0, 0.95, 0.85], 0.35, 6000, prism=True))
MATERIALS.update(lens("h83_lens_red", [0.62, 0.02, 0.02], [1.0, 0.04, 0.02], 0.72, 4000, prism=True))
MATERIALS.update(lens("h83_lens_amber", [0.95, 0.45, 0.02], [1.0, 0.45, 0.02], 0.72, 4000, prism=True))


def glow(fn, off, on, scale=1.0):
    return {"simpleFunction": fn, "off": off, "on": on, "materialEmissiveScaling": {"on_max": scale}}


GLOW = {
    "h83_glass_headlight": glow({"custom_lowbeam": 0.49, "custom_highbeam": 1.0}, "h83_lens_clear", "h83_lens_clear_on"),
    "h83_glass_taillight": glow({"custom_lowhighbeam": 0.49, "custom_brake": 1.0}, "h83_lens_red", "h83_lens_red_on"),
    "h83_glass_signal_L": glow({"custom_signal_L": 1.0}, "h83_lens_amber", "h83_lens_amber_on", 0.49),
    "h83_glass_signal_R": glow({"custom_signal_R": 1.0}, "h83_lens_amber", "h83_lens_amber_on", 0.49),
    "h83_glass_reverse": glow({"custom_reverse": 1.0}, "h83_lens_clear_prism", "h83_lens_clear_prism_on"),
    "h83_glass_parking": glow({"custom_lowhighbeam": 1.0}, "h83_lens_clear_prism", "h83_lens_clear_prism_on", 0.3),
}


# ------------------------------------------------------------ part helpers
def clone(parts, src, name, label, value=None):
    p = copy.deepcopy(parts[src])
    p.pop("__file__", None)
    p["information"] = dict(p.get("information", {}), authors=AUTH, name=label)
    if value is not None:
        p["information"]["value"] = value
    return name, p


def set_bulb(p, slot, pos):
    for r in p.get("slots2", [])[1:]:
        if r[0] == slot:
            v = r[5]["variables"]
            v["$posX"], v["$posY"], v["$posZ"] = pos
            return
    raise KeyError(slot)


def drop_slots(p, names):
    p["slots2"] = [p["slots2"][0]] + [r for r in p["slots2"][1:] if r[0] not in names]


def flex(rows):
    return [["mesh", "[group]:", "nonFlexMaterials"]] + rows


def build_parts(parts, meta):
    out = {}

    def put(kv):
        out[kv[0]] = kv[1]
        return kv[1]

    for s, side in (("L", "Left"), ("R", "Right")):
        F = "F" + s
        p = put(clone(parts, f"ariahatch_headlight_{F}_late", f"ariahatch_headlight_{F}_h83",
                      f"'83 Hatch {side} Headlight (Sealed Beam)"))
        p["flexbodies"] = flex([
            {"deformGroup": f"headlightglass_{s}_break"},
            [f"ariahatch_h83_headlight_{F}", [f"ariahatch_headlight_{F}"]],
            [f"ariahatch_h83_headlightglass_{F}", [f"ariahatch_headlight_{F}"], [],
             {"deformSound": "event:>Destruction>Vehicle>Glass>extglassbreaksound4", "deformVolume": 0.5}],
            {"deformGroup": ""}])
        p["glowMap"] = {"h83_glass_headlight": GLOW["h83_glass_headlight"]}
        hx = 0.5125 if s == "L" else -0.5125
        for b in ("low", "high"):
            set_bulb(p, f"ariahatch_headlight_{s}_{b}_bulb", (hx, -1.672, 0.673))

        p = put(clone(parts, f"ariahatch_fender_{s}_late", f"ariahatch_fender_{s}_h83",
                      f"'83 Hatch {side} Front Fender (Flush Shoulder)"))
        p["flexbodies"] = flex([
            [f"ariahatch_h83_fender_{F}", ["ariahatch_body"]],
            {"deformGroup": f"signal_{s}_break"},
            [f"ariahatch_h83_fender_marker_{F}", ["ariahatch_body"], [],
             {"deformSound": "event:>Destruction>Vehicle>Glass>extglassbreaksound4", "deformVolume": 0.8}],
            {"deformGroup": ""}])
        mk = meta["fender_marker_L"]
        set_bulb(p, f"ariahatch_fender_{s}_bulb", tuple(mk) if s == "L" else (-mk[0], mk[1], mk[2]))
        p["glowMap"] = {f"h83_glass_signal_{s}": GLOW[f"h83_glass_signal_{s}"]}

        R = "R" + s
        p = put(clone(parts, f"ariahatch_taillight_{R}_late", f"ariahatch_taillight_{R}_h83",
                      f"'83 Hatch {side} Taillight (Wraparound)"))
        p["flexbodies"] = flex([
            {"deformGroup": f"taillightglass_{s}_break"},
            [f"ariahatch_h83_taillight_{R}", [f"ariahatch_taillight_{R}"], [],
             {"deformSound": "event:>Destruction>Vehicle>Glass>extglassbreaksound4", "deformVolume": 0.5}],
            [f"ariahatch_h83_taillight_gate_{R}", ["ariahatch_tailgate"], [],
             {"deformSound": "event:>Destruction>Vehicle>Glass>extglassbreaksound4", "deformVolume": 0.5}],
            {"deformGroup": ""}])
        b = meta["taillight_bulbs_L"]
        mir = (lambda q: q) if s == "L" else (lambda q: (-q[0], q[1], q[2]))
        set_bulb(p, f"ariahatch_taillight_{s}_brake_bulb", mir(b["brake"]))
        set_bulb(p, f"ariahatch_taillight_{s}_signal_bulb", mir(b["signal"]))
        set_bulb(p, f"ariahatch_taillight_{s}_reverse_bulb", mir(b["reverse"]))
        p["glowMap"] = {k: GLOW[k] for k in ("h83_glass_taillight", f"h83_glass_signal_{s}", "h83_glass_reverse")}

    p = put(clone(parts, "ariahatch_hood_late", "ariahatch_hood_h83", "'83 Hatch Flat Hood (Cowl Louvres)"))
    p["flexbodies"] = flex([["ariahatch_h83_hood", ["ariahatch_hood"]]])

    p = put(clone(parts, "ariahatch_frontpanel_late", "ariahatch_frontpanel_h83", "'83 Hatch Front Panel"))
    p["flexbodies"] = flex([["ariahatch_h83_frontpanel", ["ariahatch_body"]]])
    defaults = {"ariahatch_bumper_F": "ariahatch_bumper_F_h83", "ariahatch_fascia_F_late": "ariahatch_fascia_F_h83",
                "ariahatch_headlight_FR_late": "ariahatch_headlight_FR_h83",
                "ariahatch_headlight_FL_late": "ariahatch_headlight_FL_h83"}
    p["slots"] = [p["slots"][0]] + [[r[0], defaults.get(r[0], r[1])] + r[2:] for r in p["slots"][1:]]

    p = put(clone(parts, "ariahatch_fascia_F_late", "ariahatch_fascia_F_h83", "'83 Hatch Chrome Header Fascia"))
    p["flexbodies"] = flex([["ariahatch_h83_fascia_F", ["ariahatch_fascia_F"]]])
    p["slots"] = [p["slots"][0]] + [[r[0], "ariahatch_grille_F_h83" if r[0] == "ariahatch_grille_F_late" else r[1]] + r[2:]
                                    for r in p["slots"][1:]]

    p = put(clone(parts, "ariahatch_grille_F_late_a", "ariahatch_grille_F_h83", "'83 Hatch Bar Grille"))
    p["flexbodies"] = flex([["ariahatch_h83_grille_F", ["ariahatch_fascia_F"]]])
    p["slots"] = [p["slots"][0]] + [[r[0], ""] + r[2:] for r in p["slots"][1:]]  # badge empty by default

    p = put(clone(parts, "ariahatch_bumper_F_late", "ariahatch_bumper_F_h83", "'83 Hatch Wraparound Front Bumper"))
    p["flexbodies"] = flex([
        ["ariahatch_h83_bumper_F", ["ariahatch_bumper_F"]],
        {"deformGroup": "bumperlight_FL_break"},
        ["ariahatch_h83_bumper_lamps_FL", ["ariahatch_bumper_F"], [],
         {"deformSound": "event:>Destruction>Vehicle>Glass>extglassbreaksound4", "deformVolume": 0.5}],
        {"deformGroup": "bumperlight_FR_break"},
        ["ariahatch_h83_bumper_lamps_FR", ["ariahatch_bumper_F"], [],
         {"deformSound": "event:>Destruction>Vehicle>Glass>extglassbreaksound4", "deformVolume": 0.5}],
        {"deformGroup": ""}])
    drop_slots(p, {"ariahatch_bumper_FL_fog_bulb", "ariahatch_bumper_FR_fog_bulb"})
    sx, sy, sz = meta["bumper_signal_L"]
    set_bulb(p, "ariahatch_bumper_FL_signal_bulb", (round(sx, 3), round(sy, 3), sz))
    set_bulb(p, "ariahatch_bumper_FR_signal_bulb", (round(-sx, 3), round(sy, 3), sz))
    for r in p["slots2"][1:]:
        if r[0] == "ariahatch_licenseplate_F":
            r[5]["nodeOffset"]["y"] = -0.035
    p["glowMap"] = {k: GLOW[k] for k in ("h83_glass_signal_L", "h83_glass_signal_R", "h83_glass_parking")}

    p = put(clone(parts, "ariahatch_bumper_R_late", "ariahatch_bumper_R_h83", "'83 Hatch Wraparound Rear Bumper"))
    p["flexbodies"] = flex([["ariahatch_h83_bumper_R", ["ariahatch_bumper_R"]],
                            ["ariahatch_h83_rear_panel", ["ariahatch_body"]]])

    p = put(clone(parts, "ariahatch_licenseplate_R_EU", "ariahatch_licenseplate_R_h83",
                  "'83 Hatch Rear License Plate (raised)"))
    px, py, pz = meta["plate_R_pos"]
    p["flexbodies"][1][3]["pos"] = {"x": px, "y": py, "z": pz}

    p = put(clone(parts, "ariahatch_trim_late", "ariahatch_trim_h83", "'83 Hatch Side Mouldings, Markers & Fuel Door"))
    p["flexbodies"] = flex([
        ["ariahatch_h83_trim_fender_L", ["ariahatch_fender_L"]], ["ariahatch_h83_trim_fender_R", ["ariahatch_fender_R"]],
        ["ariahatch_h83_trim_door_L", ["ariahatch_door_L"]], ["ariahatch_h83_trim_door_R", ["ariahatch_door_R"]],
        ["ariahatch_h83_trim_body_L", ["ariahatch_body"]], ["ariahatch_h83_trim_body_R", ["ariahatch_body"]],
        ["ariahatch_h83_trim_body_extra_L", ["ariahatch_body"]], ["ariahatch_h83_trim_body_extra_R", ["ariahatch_body"]]])

    for a in ("F", "R"):
        p = put(clone(parts, f"ariahatch_wheel_01b_13x5_{a}", f"ariahatch_wheel_h83_13x5_{a}",
                      f"13x5 '83 Hatch Steel {'Front' if a == 'F' else 'Rear'} Wheels (Silver)"))
        for r in p["flexbodies"][1:]:
            if isinstance(r, list):
                r[0] = "ariahatch_h83_steel_13x5"

    # sound-only exhaust: stock exhaust mechanics, sportier tuned-4-cylinder sound
    p = put(clone(parts, "ariahatch_exhaust_stock_ohv", "ariahatch_exhaust_h83_ohv",
                  "'83 Hatch Sport-Tuned Exhaust (sound only)"))
    p["mainEngine"] = dict(p["mainEngine"])  # identical torqueModExhaust to stock
    p["mainEngine"].update({
        "starterSample": "event:>Engine>Starter>i4_1991_eng",
        "starterSampleExhaust": "event:>Engine>Starter>i4_1991_exh",
        "$*instantAfterFireCoef": 1.5,
        "$*sustainedAfterFireCoef": 1.5,
    })
    p["soundConfig"] = {
        "sampleName": "i4p_02000cc_endurance_02_engine",
        "intakeMuffling": 0.25,
        "mainGain": -3,
        "onLoadGain": 1,
        "offLoadGain": 0.5,
        "maxLoadMix": 0.7,
        "minLoadMix": 0,
        "lowShelfGain": 3, "lowShelfFreq": 150,
        "highShelfGain": 3, "highShelfFreq": 5000,
        "eqLowGain": -4, "eqLowFreq": 500, "eqLowWidth": 0.3,
        "eqHighGain": -4, "eqHighFreq": 2500, "eqHighWidth": 0.1,
        "fundamentalFrequencyCylinderCount": 4,
        "eqFundamentalGain": -2,
    }
    p["soundConfigExhaust"] = {
        "sampleName": "i4p_2000_02000cc_modified_01_exhaust",
        "mainGain": 3,
        "onLoadGain": 1,
        "offLoadGain": 0.5,
        "maxLoadMix": 0.7,
        "minLoadMix": 0,
        "lowShelfGain": 4, "lowShelfFreq": 60,
        "highShelfGain": 2, "highShelfFreq": 3000,
        "eqLowGain": 1, "eqLowFreq": 90, "eqLowWidth": 0.5,
        "eqHighGain": -2, "eqHighFreq": 4000, "eqHighWidth": 0.1,
        "fundamentalFrequencyCylinderCount": 4,
        "eqFundamentalGain": 1,
    }
    return out


def build_pc(base_pc):
    pc = copy.deepcopy(base_pc)
    P = pc["parts"]
    P.update({
        "ariahatch_hood": "ariahatch_hood_h83",
        "ariahatch_fender_L": "ariahatch_fender_L_h83", "ariahatch_fender_R": "ariahatch_fender_R_h83",
        "ariahatch_frontpanel": "ariahatch_frontpanel_h83",
        "ariahatch_fascia_F_late": "ariahatch_fascia_F_h83",
        "ariahatch_licenseplate_R": "ariahatch_licenseplate_R_h83",
        "ariahatch_trim": "ariahatch_trim_h83",
        "ariahatch_headlight_FL_late": "ariahatch_headlight_FL_h83",
        "ariahatch_headlight_FR_late": "ariahatch_headlight_FR_h83",
        "ariahatch_grille_F_late": "ariahatch_grille_F_h83",
        "ariahatch_badge_F": "",
        "ariahatch_bumper_F": "ariahatch_bumper_F_h83",
        "ariahatch_bumper_R": "ariahatch_bumper_R_h83",
        "ariahatch_taillight_RL": "ariahatch_taillight_RL_h83",
        "ariahatch_taillight_RR": "ariahatch_taillight_RR_h83",
        "wheel_F_4": "ariahatch_wheel_h83_13x5_F",
        "wheel_R_4": "ariahatch_wheel_h83_13x5_R",
        "ariahatch_exhaust_ohv": "ariahatch_exhaust_h83_ohv",
        "ariahatch_mudflap_FL": "", "ariahatch_mudflap_FR": "", "ariahatch_mudflap_R": "",
        "ariahatch_lettering_F": "", "ariahatch_lettering_tailgate": "",
        "ariahatch_licenseplate_F": "",
        "ariahatch_mirror_R": "ariahatch_mirror_R",
    })
    for k in ("ariahatch_bumper_FL_fog_bulb", "ariahatch_bumper_FR_fog_bulb"):
        P.pop(k, None)
    blue = {"baseColor": [0.40, 0.55, 0.74, 1.2], "metallic": 0.55, "roughness": 0.35,
            "clearcoat": 0.8, "clearcoatRoughness": 0.04}
    pc["paints"] = [blue, dict(blue), dict(blue)]
    return pc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aria", required=True, help="the Aria mod's extracted vehicles/ dir")
    ap.add_argument("--build", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--thumb")
    ap.add_argument("--bundle", help="original Aria mod zip: also write a standalone bundle")
    a = ap.parse_args()
    parts = jbeam.load_parts([os.path.join(a.aria, "ariahatch"), os.path.join(a.aria, "common")])
    meta = json.load(open(os.path.join(a.build, "meta.json")))
    new = build_parts(parts, meta)

    # sanity: every referenced mesh exists in our DAE, every glow material is defined
    meshes = set(meta["meshes"])
    for p in parts.values():
        meshes.update(jbeam.flexbody_meshes(p))   # meshes the Aria already ships
    for name, p in new.items():
        for r in p.get("flexbodies", [])[1:]:
            if isinstance(r, list):
                assert r[0] in meshes, (name, r[0])
        for g in p.get("glowMap", {}).values():
            assert g["off"] in MATERIALS and g["on"] in MATERIALS, g
    aria_mats = {"ariahatch_main"}   # the Aria's own body material (paint), defined in its main.materials.json
    assert set(meta["materials"]) <= set(MATERIALS) | set(GLOW) | aria_mats, \
        set(meta["materials"]) - set(MATERIALS) - set(GLOW) - aria_mats

    base_pc = json.load(open(os.path.join(a.aria, "ariahatch", "120_super_late_M.pc")))
    pc = build_pc(base_pc)
    for slot, part in pc["parts"].items():
        assert part == "" or part in parts or part in new or part.startswith(("tire_", "brakepad_", "soundscape", "incandescent", "headlightBulb", "sealedBeam", "occupant", "licenseplate_design", "gps", "n2o", "paint_design")), (slot, part)

    info = json.load(open(os.path.join(a.aria, "ariahatch", "info_120_super_late_M.json")))
    info.update({"Configuration": "'83 Hatch Sport (M)",
                 "Description": "Restyled late Aria in the spirit of an early-80s Japanese 3-door hatch: "
                                "sealed-beam headlights, slat grille, wraparound bumpers and corner taillights, "
                                "silver steel wheels and a sport-tuned exhaust note. Mechanics as the 120 Super.",
                 "Config Type": "Custom", "Years": {"min": 1983, "max": 1983}})
    info.pop("defaultPaintName1", None)

    files = {}
    blob = json.dumps(new, indent=1)
    files[f"{SUB}/ariahatch_h83.jbeam"] = blob.encode()
    files[f"{SUB}/hatch83.materials.json"] = json.dumps(MATERIALS, indent=1).encode()
    files[f"{SUB}/hatch83.dae"] = open(os.path.join(a.build, "hatch83.dae"), "rb").read()
    files[f"{SUB}/h83_lens_prism_n.png"] = open(os.path.join(a.build, "tex", "h83_lens_prism_n.png"), "rb").read()
    files[f"{VDIR}/{PC_NAME}.pc"] = json.dumps(pc, indent=2).encode()
    files[f"{VDIR}/info_{PC_NAME}.json"] = json.dumps(info, indent=2).encode()
    if a.thumb:
        files[f"{VDIR}/{PC_NAME}.jpg"] = open(a.thumb, "rb").read()

    # the generated jbeam must round-trip through our parser
    assert jbeam.loads(blob).keys() == new.keys()
    json.dump(GLOW, open(os.path.join(a.build, "preview_glow.json"), "w"))
    os.makedirs(a.out, exist_ok=True)
    for p, d in files.items():
        dst = os.path.join(a.build, "mod", p)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        open(dst, "wb").write(d)
    z = os.path.join(a.out, "aria_83_hatch_addon.zip")
    with zipfile.ZipFile(z, "w", zipfile.ZIP_DEFLATED) as zf:
        for p, d in sorted(files.items()):
            zf.writestr(p, d)
    print("parts:", ", ".join(new))
    print("wrote", z, os.path.getsize(z))

    if a.bundle:
        # standalone: the whole Aria (credited, per its author's reupload terms) + our files
        b = os.path.join(a.out, "aria_83_hatch_standalone.zip")
        with zipfile.ZipFile(a.bundle) as src, zipfile.ZipFile(b, "w", zipfile.ZIP_STORED) as dst:
            for info_ in src.infolist():
                # drop repo metadata so BeamNG's repo manager doesn't treat (and
                # "update") this bundle as the official Aria download
                if info_.filename.startswith("mod_info/") or info_.filename in files:
                    continue
                dst.writestr(info_, src.read(info_.filename))
            for p, d in sorted(files.items()):
                dst.writestr(p, d, compress_type=zipfile.ZIP_DEFLATED)
            dst.writestr("vehicles/ariahatch/hatch83/CREDITS.txt", CREDITS, compress_type=zipfile.ZIP_DEFLATED)
        print("wrote", b, os.path.getsize(b))


CREDITS = """Aria '83 Hatch (standalone bundle)

Base vehicle: "1972 Autobello Aria" v1.0.5 by Kajzer
  https://www.beamng.com/resources/1972-autobello-aria.35232/
  All Aria models, textures, jbeam, physics, lua and configs are Kajzer's work,
  included unmodified (the author permits reuploads with credit).

'83 Hatch restyle (hatch83/ folder, h83_hatch_M config): new headlights, grille,
bumpers, taillights, steel wheels, materials and sport exhaust sound tune.
Source: https://github.com/jacobkuzmits/beam-mods/tree/main/aria-83-hatch

Do not install this bundle together with the separate Aria mod.
"""


if __name__ == "__main__":
    main()
