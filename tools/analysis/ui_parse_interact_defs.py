#!/usr/bin/env python3
"""ui_parse_interact_defs — build databases/interaction_definitions.{json,csv}.

Parses every `game-interactable-def` entry (all 273 live in interactable.bin) straight
from the raw DC binary (0x200-byte struct, no field names are shipped), records EVERY
4-byte word raw (hex / i32 / f32) plus decoded pointers (strings) and SIDs, adds an
interpreted column set with per-field confidence, and cross-references every def name
against the dconstruct pseudo-code corpus (who draws / overrides / tests it) and the
data files (gui2-game photo-mode list, modules.bin export list).

Usage (repo root):  python3 -I tools/analysis/ui_parse_interact_defs.py
Env: TLOU2_PRIVATE (default <repo>/.private)
"""
import csv
import gzip
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
PRIV = os.environ.get("TLOU2_PRIVATE", os.path.join(REPO, ".private"))
sys.path.insert(0, HERE)
from dclib import DCFile, SidDB, fnv1a64, sidhex  # noqa: E402

BIN = os.path.join(PRIV, "extracted16", "dc1", "interactable.bin")
DCPL_ROOT = os.path.join(PRIV, "dconstruct_out", "dc1")
OUT_JSON = os.path.join(REPO, "databases", "interaction_definitions.json")
OUT_CSV = os.path.join(REPO, "databases", "interaction_definitions.csv")
SIZE = 0x200

# ---------------------------------------------------------------------------
# Field map.  kind: f32 | i32 | sid | ptr(str) | u8 (single byte flag)
# conf: CONFIRMED (read by DC code with this meaning) | HIGH | INFERRED | UNKNOWN
# ---------------------------------------------------------------------------
FIELDS = [
    (0x000, "sid", "name", "def id (= entry name)", "CONFIRMED"),
    (0x008, "f32", "interact_radius_m", "interact radius: prompt becomes pressable (default 1.8)", "HIGH"),
    (0x00C, "f32", "interact_height_min", "interaction height window min (object.y - player.y)", "INFERRED"),
    (0x010, "f32", "interact_height_max", "interaction height window max", "INFERRED"),
    (0x014, "f32", "interact_angle_a_deg", "angle limit A (-1 = none; 360 l3-inspect/contextual-look, 180 horse)", "INFERRED"),
    (0x018, "f32", "interact_angle_b_deg", "angle limit B (-1 = none; 20 horse)", "INFERRED"),
    (0x01C, "u8", "flag_01c_traversal", "set only on climb-up/down, rope-climb, horse", "INFERRED"),
    (0x020, "f32", "approach_angle_a_deg", "object-relative angle A (-1 none; 100 turret/dead-drop)", "INFERRED"),
    (0x024, "f32", "approach_angle_b_deg", "object-relative approach cone (-1 none; drawer 110, workbench 72.5, lockpick 80)", "INFERRED"),
    (0x028, "f32", "activation_radius_m", "activation radius: icon/prompt appears (default 1.5)", "HIGH"),
    (0x02C, "f32", "activation_height_min", "activation height window min (default -0.5)", "INFERRED"),
    (0x030, "f32", "activation_height_max", "activation height window max (default 2.5)", "INFERRED"),
    (0x034, "f32", "activation_angle_deg", "activation view/facing cone (default 80; doors 360; conversations 180)", "INFERRED"),
    (0x040, "f32", "f_040", "unknown (-0.4 snowball only)", "UNKNOWN"),
    (0x049, "u8", "flag_049_no_los_probe", "set on controller-shake, dropped pickups, l3-inspect, contextual-look; cleared by *-los variants", "INFERRED"),
    (0x04A, "u8", "flag_04a_door_like", "doors, rogue dead-drops, needs-key", "INFERRED"),
    (0x04C, "f32", "f_04c", "constant 0.9", "UNKNOWN"),
    (0x050, "sid", "anchor_joint", "joint used as interaction/icon anchor (handle, neck, lock, root...)", "HIGH"),
    (0x058, "u8", "flag_058_character", "conversations/pet-dog (anchor on character neck)", "INFERRED"),
    (0x059, "u8", "flag_059_station", "workbenches + turret", "INFERRED"),
    (0x05C, "f32", "offset_x", "interaction point offset from object locator (x)", "CONFIRMED"),
    (0x060, "f32", "offset_y", "interaction point offset (y)", "CONFIRMED"),
    (0x064, "f32", "offset_z", "interaction point offset (z)", "CONFIRMED"),
    (0x068, "f32", "offset2_x", "second offset vector x (bow pickups)", "INFERRED"),
    (0x06C, "f32", "offset2_y", "second offset vector y (0.09 collectibles/inspectables)", "INFERRED"),
    (0x070, "f32", "offset2_z", "second offset vector z", "INFERRED"),
    (0x074, "f32", "f_074", "0.15 default, 0.06 collectibles, 0 openables", "UNKNOWN"),
    (0x078, "i32", "i_078", "2 default, 1 pickups/lockpick/openable-object, 0 drawers/cabinet", "UNKNOWN"),
    (0x07C, "f32", "f_07c", "0.2 default, 0.15 pickups/openables", "UNKNOWN"),
    (0x081, "u8", "flag_081", "nor-pharmacy-note-enabled only", "UNKNOWN"),
    (0x084, "f32", "f_084", "0.1 default, 0.02 pickups/openables", "UNKNOWN"),
    (0x088, "f32", "f_088", "2.0 dropped pickups/tennis ball/turret", "UNKNOWN"),
    (0x08C, "u8", "flag_08c", "openable-object, lockpick, boat, machete, mp-scavenge", "UNKNOWN"),
    (0x090, "f32", "f_090", "constant 3.0", "UNKNOWN"),
    (0x094, "f32", "f_094", "constant 3.2", "UNKNOWN"),
    (0x098, "f32", "f_098", "1 default; 3 doors/conversations; 2 openables; 2-2.5 workbench", "UNKNOWN"),
    (0x09C, "f32", "f_09c", "1 default; 3 doors/conversations; 2 openables; 2.5 workbench", "UNKNOWN"),
    (0x0A0, "f32", "f_0a0", "1 (0.3/0.8 rare)", "UNKNOWN"),
    (0x0A4, "f32", "f_0a4", "1 (0.5 l3-inspect)", "UNKNOWN"),
    (0x0A8, "f32", "f_0a8", "constant 1", "UNKNOWN"),
    (0x0AC, "f32", "f_0ac", "constant 1", "UNKNOWN"),
    (0x0B0, "f32", "f_0b0", "constant -1", "UNKNOWN"),
    (0x0B4, "u8", "flag_0b4", "dropped-tomahawk only", "UNKNOWN"),
    (0x0B6, "u8", "flag_0b6", "84 defs: examine/inspect/collectible/conversation/workbench/door-fake...", "UNKNOWN"),
    (0x0B7, "u8", "flag_0b7_auto", "auto-interact-igc-object, auto-pickup-medium-radius", "INFERRED"),
    (0x0B8, "u8", "flag_0b8", "auto-interact-igc-object, fake-squeeze-through", "UNKNOWN"),
    (0x0B9, "u8", "flag_0b9_collectible", "all collectible/coin/card defs", "INFERRED"),
    (0x0BA, "u8", "flag_0ba_not_pickup", "205 defs; clear on every pickup/collectible def (pickup-scan default?)", "INFERRED"),
    (0x0BB, "u8", "flag_0bb_weapon_item", "weapon/holster/upgrade-manual/rogue recipe pickups", "INFERRED"),
    (0x0C8, "ptr", "hud_widget", "HUD widget override (pc/hud-interactable/..., button-mash-hold-hybrid)", "HIGH"),
    (0x0D0, "ptr", "button_icon", "button glyph id (gen:interact etc.), rendered as '%s@large'", "CONFIRMED"),
    (0x0D8, "ptr", "hud_icon_image", "prompt side image (investigate.png, dialogue.png, ...)", "HIGH"),
    (0x0E0, "ptr", "hud_icon_overlay", "secondary overlay image (wrench = upgrade affordable)", "HIGH"),
    (0x0E8, "f32", "f_0e8", "0.05-0.3, dropped pickups/turret/commentary/carry-rope-tall", "UNKNOWN"),
    (0x0EC, "u8", "flag_0ec_shows_unavailable", "doors, ammo pickups, dead-drops, needs-key (can show greyed/unavailable prompt?)", "INFERRED"),
    (0x0F0, "sid", "joypad_command", "joypad command polled (0 => native default, object-interact)", "CONFIRMED"),
    (0x0F8, "u8", "flag_0f8", "rogue-dead-drop-deposit only", "UNKNOWN"),
    (0x0F9, "u8", "flag_0f9", "99 defs (doors, pickups, conversations, ropes)", "UNKNOWN"),
    (0x0FC, "f32", "f_0fc", "15 on buddy-boost", "UNKNOWN"),
    (0x103, "u8", "flag_103", "constant 1", "UNKNOWN"),
    (0x108, "sid", "select_highlight_settings", "*select-highlight-settings* (outline when selected)", "HIGH"),
    (0x110, "sid", "interact_highlight_settings", "*interact-highlight-settings*", "HIGH"),
    (0x118, "f32", "f_118", "constant 0.5", "UNKNOWN"),
    (0x11C, "f32", "f_11c", "constant 0.3", "UNKNOWN"),
    (0x120, "sid", "sound_inventory_full", "sfx played when pickup refused (inventory full)", "HIGH"),
    (0x12D, "u8", "flag_12d_push", "push-far / push-generic", "INFERRED"),
    (0x12E, "u8", "flag_12e_openable", "openable drawer/cabinet/object, npc-blockable", "INFERRED"),
    (0x12F, "u8", "flag_12f_pickup", "37 pickup defs", "INFERRED"),
    (0x130, "u8", "flag_130", "interact-boat only", "UNKNOWN"),
    (0x138, "sid", "probe_layer_a", "collision layer name 'Interactive' (LOS probe filter)", "INFERRED"),
    (0x140, "sid", "probe_layer_b", "collision layer name 'Background'", "INFERRED"),
    (0x148, "u8", "flag_148_los_probe", "1 except plain ammo pickups (the -los variant sets it)", "INFERRED"),
    (0x160, "sid", "sound_select", "sfx-hud-conversation-option on conversation defs", "HIGH"),
    (0x168, "sid", "prompt_text_id", "custom prompt label text id (HUD_INTERACTABLE_CARRY ...)", "HIGH"),
    (0x178, "sid", "unavailable_text_id", "text shown when unavailable (HUD_INTERACT_LOCKED / NEEDS_POWER ...)", "HIGH"),
    (0x180, "u8", "flag_180", "1 except dead-drop-deposit-unavailable", "UNKNOWN"),
    (0x190, "u8", "flag_190_carry", "carry-rope*, snowball", "INFERRED"),
    (0x194, "f32", "f_194", "constant 1", "UNKNOWN"),
    (0x198, "sid", "prompt_style", "prompt layout: interact | double-dynamic | simple | double", "HIGH"),
    (0x1A0, "ptr", "str_1a0", "empty string on 19 defs", "UNKNOWN"),
    (0x1A9, "u8", "flag_1a9", "114 defs", "UNKNOWN"),
    (0x1AA, "u8", "flag_1aa", "72 defs (doors/conversations/workbench/boost)", "UNKNOWN"),
    (0x1AB, "u8", "allow_on_horse", "byte +427 read by accessibility-pathfind: 0 => systemic dismount needed", "CONFIRMED"),
    (0x1AE, "u8", "flag_1ae", "constant 1", "UNKNOWN"),
    (0x1AF, "u8", "flag_1af", "77 defs (doors/conversations/workbench/push)", "UNKNOWN"),
    (0x1B0, "sid", "acc_sound_distant", "accessibility cue when activated-but-distant", "HIGH"),
    (0x1C0, "sid", "acc_sound_distant_above", "distant cue variant when above", "HIGH"),
    (0x1C8, "f32", "acc_above_threshold_m", "height threshold for 'above' variant (2.0)", "INFERRED"),
    (0x1D0, "sid", "acc_sound_distant_below", "distant cue variant when below", "HIGH"),
    (0x1D8, "f32", "acc_below_threshold_m", "height threshold for 'below' variant (-0.25)", "INFERRED"),
    (0x1E0, "sid", "acc_sound_interact", "accessibility cue when pressable (triangle/square)", "HIGH"),
    (0x1E8, "sid", "acc_sound_sweetener", "per-type accessibility sweetener (door-open, cabinet-open...)", "HIGH"),
    (0x1F0, "sid", "acc_sound_error", "accessibility error sweetener", "HIGH"),
    (0x1F8, "u8", "flag_1f8", "constant 1", "UNKNOWN"),
    (0x1F9, "u8", "no_accessibility_ping", "set by *-no-ping/*-used, cleared by *-with-ping/*-progression-important", "HIGH"),
    (0x1FA, "u8", "special_item", "byte +506 read by blind-listen-mode: special vs pickup sonar sound", "CONFIRMED"),
    (0x1FB, "u8", "mash_hold_hybrid", "byte +507 read by draw-interactable-hud: show hold widget if mashes-are-holds", "CONFIRMED"),
    (0x1FC, "u8", "flag_1fc", "interact-unchain-infected only", "UNKNOWN"),
]

# joypad command -> (input action, mode) from joypad.bin *joypad-default* (mode 8=press, 2=hold<s>)
COMMANDS = {
    None: ("gen:interact", "tap (object-interact, press)"),
    "object-interact": ("gen:interact", "tap (press)"),
    "interact-hold": ("gen:interact", "hold 0.30 s"),
    "weapon-pickup-swap": ("gen:interact", "hold 0.25 s"),
    "melee-repeat": ("gen:attack", "mash (press or hold 0.30 s)"),
    "interact-wall": ("gen:attack", "press / hold 0.30 s"),
    "jump": ("gen:jump", "tap"),
    "crouch-press": ("gen:crouch", "tap"),
    "igc-squeeze-through": ("gen:jump", "tap"),
    "look-at-mark": ("gen:look-at", "tap"),
    "vehicle-enter": ("gen:interact", "tap"),
    "horse-conversation-interact": ("?", "?"),
    "cancel-hold": ("?", "?"),
}

ICON_STICK = re.compile(r"analog|stick|dpad|touchpad|r1|r2|l1|shake|swipe")


def load_sids():
    s = SidDB()
    s.load_tsv(os.path.join(PRIV, "sid", "sid_full.tsv"))
    return s


def raw_words(dc, p, sids):
    """Every word of the struct: pointer strings and SIDs at 8-aligned slots, else 4-byte words."""
    raw = {}
    o = 0
    while o < SIZE:
        if o % 8 == 0 and dc.is_ptr(p + o):
            raw[f"0x{o:03X}"] = {"ptr": dc.cstr(dc.u64(p + o))}
            o += 8
            continue
        if o % 8 == 0:
            q = dc.u64(p + o)
            nm = sids.get(q) if q else None
            if nm is not None:
                raw[f"0x{o:03X}"] = {"sid": nm}
                o += 8
                continue
        u = dc.u32(p + o)
        raw[f"0x{o:03X}"] = {"u32": f"0x{u:08X}", "i32": dc.i32(p + o), "f32": round(dc.f32(p + o), 6)}
        o += 4
    return raw


def field_value(dc, p, off, kind, sids):
    if kind == "f32":
        return round(dc.f32(p + off), 6)
    if kind == "i32":
        return dc.i32(p + off)
    if kind == "u8":
        return dc.b[p + off]
    if kind == "sid":
        q = dc.u64(p + off)
        return None if q == 0 else sids.name(q)
    if kind == "ptr":
        return dc.cstr(dc.u64(p + off)) if dc.is_ptr(p + off) else None
    raise ValueError(kind)


# ---------------------------------------------------------------------------
# corpus cross-reference
# ---------------------------------------------------------------------------
FN_HDR = re.compile(r"^[a-z0-9?*][^\s]*\??\s+([^\s(]+)\(.*\)\s*\{\s*$")
STATE_HDR = re.compile(r"^\s+state\s+(\S+)\s*\{")
TOKEN = re.compile(r"[a-z0-9][a-z0-9?!*/<>=-]*")


def enclosing_call(line, pos):
    depth = 0
    i = pos - 1
    while i >= 0:
        c = line[i]
        if c == ")":
            depth += 1
        elif c == "(":
            if depth == 0:
                j = i
                k = j - 1
                while k >= 0 and (line[k].isalnum() or line[k] in "-?!*/<>_:"):
                    k -= 1
                return line[k + 1:j] or None
            depth -= 1
        i -= 1
    return None


def scan_corpus(names):
    refs = defaultdict(list)
    for root, _, files in os.walk(DCPL_ROOT):
        for fn in files:
            if not fn.endswith(".dcpl"):
                continue
            path = os.path.join(root, fn)
            rel = os.path.relpath(path, DCPL_ROOT)[:-5]
            ctx = "?"
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                continue
            if not any(n in text for n in ("interact", "int-", "joe-evidence", "nor-pharmacy", "melee-interact", "auto-pickup")):
                continue
            for ln, line in enumerate(text.split("\n"), 1):
                m = FN_HDR.match(line)
                if m:
                    ctx = "fn:" + m.group(1)
                m = STATE_HDR.match(line)
                if m:
                    ctx = "state:" + m.group(1)
                for t in TOKEN.finditer(line):
                    tok = t.group(0)
                    if tok in names:
                        call = enclosing_call(line, t.start()) or "(value: assignment/compare/return)"
                        refs[tok].append({"file": rel, "ctx": ctx, "line": ln, "call": call})
    return refs


def gui2_photo_list():
    path = os.path.join(DCPL_ROOT, "gui2-game.bin.asm")
    out = []
    if not os.path.exists(path):
        return out
    lines = open(path, encoding="utf-8").read().split("\n")
    for i, l in enumerate(lines):
        if l.startswith("  [0x5E0] string-array"):
            for l2 in lines[i + 1:]:
                if l2.startswith("  [0x5E8]"):
                    break
                m = re.search(r'string: "([^"]+)"', l2)
                if m:
                    out.append(m.group(1))
            break
    return out


def data_refs():
    p = os.path.join(PRIV, "db", "xref_inverted.json.gz")
    return json.load(gzip.open(p, "rt")) if os.path.exists(p) else {}


# ---------------------------------------------------------------------------
STICK_WORDS = [("rotate", "rotate"), ("left-stick", "left stick"), ("right-stick", "right stick"), ("-ls-", "left stick "),
               ("-rs-", "right stick "), ("ccw", "counter-clockwise"), ("-cw", "clockwise"), ("updown", "up/down"),
               ("leftright", "left/right"), ("move", "move"), ("dpad", "d-pad"), ("touchpad", "touchpad"),
               ("swipe", "swipe"), ("shake", "controller shake (gyro/stick)"), ("kbm", "mouse/keyboard")]


def stick_desc(name, icon):
    parts = [txt for key, txt in STICK_WORDS if key in name]
    for d in ("left", "right", "up", "down", "forward"):
        if name.endswith("-" + d):
            parts.append(d)
    desc = " ".join(p.strip() for p in parts) or name
    return f"{desc} (icon {icon})" if icon and not icon.startswith("gen:") else f"{desc} (from def name; icon {icon})"


def interpret(f, name):
    cmd = f["joypad_command"]
    action, mode = COMMANDS.get(cmd, ("?", "?"))
    icon = f["button_icon"] or ""
    stick = None
    if ICON_STICK.search(icon) or re.search(r"stick|-ls-|-rs-|rotate|analog|dpad|touchpad|shake|-kbm-|swipe", name):
        stick = stick_desc(name, icon)
    if f["mash_hold_hybrid"]:
        behaviour = "mash/hold hybrid (hold if accessibility 'button mashes are holds')"
    elif "hold" in mode:
        behaviour = "hold"
    elif "mash" in mode:
        behaviour = "mash"
    else:
        behaviour = "tap"
    if stick and not cmd:
        behaviour = "stick/gesture prompt (input polled by owning script; def supplies icon only)"
    widget = f["hud_widget"] or ""
    progress = None
    if "mash-hold" in widget or f["mash_hold_hybrid"]:
        progress = "radial hold/mash widget (button-mash-hold-hybrid / button-hold-pc), progress set by script via set-progress"
    elif "hold" in mode:
        progress = "native hold ring (command threshold)"
    cond = []
    if f["unavailable_text_id"]:
        cond.append(f"unavailable text {f['unavailable_text_id']}")
    if f["allow_on_horse"]:
        cond.append("allowed while on horse")
    if f["flag_148_los_probe"] and not f["flag_049_no_los_probe"]:
        cond.append("LOS probe (Interactive/Background layers) [INFERRED]")
    if f["approach_angle_b_deg"] > 0 or f["approach_angle_a_deg"] > 0:
        cond.append(f"approach cone {max(f['approach_angle_a_deg'], f['approach_angle_b_deg'])} deg [INFERRED]")
    if f["interact_height_min"] > -9999 or f["interact_height_max"] < 9999:
        cond.append(f"interact height {f['interact_height_min']}..{f['interact_height_max']} m [INFERRED]")
    # type
    n = name
    if f["flag_0b9_collectible"] or "collect" in n or "coin" in n or "card" in n:
        typ = "collectible"
    elif f["flag_12f_pickup"] or "pickup" in n or "ammo" in n:
        typ = "pickup"
    elif "door" in n:
        typ = "door"
    elif "conversation" in n or f["prompt_style"] == "double-dynamic":
        typ = "conversation"
    elif "openable" in n or "drawer" in n or "cabinet" in n:
        typ = "openable"
    elif "workbench" in n or "vendor" in n:
        typ = "workbench/vendor"
    elif "inspect" in n or "examine" in n or "translation" in n or "look" in n:
        typ = "inspect/examine"
    elif "rope" in n or "climb" in n or "squeeze" in n or "boost" in n or "ladder" in n or "plank" in n:
        typ = "traversal"
    elif "push" in n or "carry" in n or "puzzle" in n:
        typ = "puzzle/physics"
    elif "mash" in n or "melee" in n or "attack" in n or "struggle" in n:
        typ = "struggle/mash"
    elif stick:
        typ = "input-gesture"
    elif "safe" in n or "lock" in n:
        typ = "safe/lock"
    else:
        typ = "generic"
    return {
        "input_action": action, "input_mode": mode, "behaviour": behaviour, "stick_movement": stick,
        "progress_indicator": progress, "availability_conditions": cond, "interaction_type": typ,
    }


def main():
    sids = load_sids()
    dc = DCFile(BIN)
    T = fnv1a64("game-interactable-def")
    entries = [(sids.name(n), p) for n, t, p, _ in dc.entries() if t == T]
    names = {n for n, _ in entries}
    photo = set(gui2_photo_list())
    inv = data_refs()
    refs = scan_corpus(names)

    rows = []
    for name, p in sorted(entries):
        f = {fname: field_value(dc, p, off, kind, sids) for off, kind, fname, _, _ in FIELDS}
        r = refs.get(name, [])
        calls = Counter(x["call"] for x in r)
        files = sorted({x["file"] for x in r})
        overrides = sorted({f"{x['file']}::{x['ctx']}" for x in r if x["call"] in ("override-interact-def", "interactable-use-def-from-other")})
        draws = sorted({f"{x['file']}::{x['ctx']}" for x in r if ("draw" in x["call"] or "hud" in x["call"] or "show" in x["call"])})
        compares = sorted({f"{x['file']}::{x['ctx']}" for x in r if x["call"] not in ("override-interact-def", "interactable-use-def-from-other") and not ("draw" in x["call"] or "hud" in x["call"] or "show" in x["call"])})
        rec = {
            "name": name,
            "sid": sidhex(fnv1a64(name)),
            "source_file": "interactable.bin",
            "struct_offset": f"0x{p:05X}",
            "in_gui2_photo_mode_list": name in photo,
            "data_referenced_in": sorted(inv.get(sidhex(fnv1a64(name)), [])),
            "fields": f,
            "interpreted": interpret(f, name),
            "references": {
                "n_code_refs": len(r),
                "by_call": dict(calls.most_common()),
                "files": files,
                "override_callers": overrides,
                "hud_draw_callers": draws,
                "other_refs": compares,
            },
            "raw": raw_words(dc, p, sids),
        }
        rows.append(rec)

    meta = {
        "source": "interactable.bin (all 273 game-interactable-def entries; struct size 0x200)",
        "generator": "tools/analysis/ui_parse_interact_defs.py",
        "field_map": [{"offset": f"0x{o:03X}", "kind": k, "name": n, "meaning": m, "confidence": c}
                      for o, k, n, m, c in FIELDS],
        "joypad_commands": {str(k): v for k, v in COMMANDS.items()},
        "gui2_photo_mode_list": sorted(photo),
        "gui2_photo_mode_list_not_defs": sorted(photo - names),
        "notes": [
            "Def assignment to a world object comes from the object's level-data tag `interactable-def` "
            "(read in DC via tag-symbol(interactable-def, obj)); scripts swap it with override-interact-def.",
            "raw = every word; ptr = decoded string pointer; sid = resolved 64-bit SID; u32/i32/f32 otherwise. "
            "Flag words are byte-packed bools; see field_map u8 entries.",
        ],
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump({"meta": meta, "definitions": rows}, fh, indent=1)

    cols = ["name", "struct_offset", "interaction_type", "input_action", "input_mode", "joypad_command", "button_icon",
            "behaviour", "stick_movement", "progress_indicator", "hud_widget", "hud_icon_image", "hud_icon_overlay",
            "prompt_style", "prompt_text_id", "unavailable_text_id", "interact_radius_m", "activation_radius_m",
            "interact_height_min", "interact_height_max", "activation_height_min", "activation_height_max",
            "activation_angle_deg", "approach_angle_a_deg", "approach_angle_b_deg", "anchor_joint",
            "offset_x", "offset_y", "offset_z", "allow_on_horse", "special_item", "mash_hold_hybrid",
            "no_accessibility_ping", "acc_sound_sweetener", "availability_conditions", "in_gui2_photo_mode_list",
            "n_code_refs", "override_callers", "hud_draw_callers", "ref_files"]
    extra = [fn for _, _, fn, _, _ in FIELDS if fn not in cols and fn != "name"]
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(cols + extra)
        for r in rows:
            f, it, rf = r["fields"], r["interpreted"], r["references"]
            src = {**f, **it, "struct_offset": r["struct_offset"], "in_gui2_photo_mode_list": r["in_gui2_photo_mode_list"],
                   "n_code_refs": rf["n_code_refs"], "override_callers": " | ".join(rf["override_callers"]),
                   "hud_draw_callers": " | ".join(rf["hud_draw_callers"]), "ref_files": " | ".join(rf["files"]),
                   "availability_conditions": "; ".join(it["availability_conditions"])}
            w.writerow([src.get(c, "") if src.get(c) is not None else "" for c in cols + extra])
    print(f"{len(rows)} defs -> {OUT_JSON}, {OUT_CSV}; photo-mode list {len(photo)} (non-def: {len(photo - names)})")


if __name__ == "__main__":
    main()
