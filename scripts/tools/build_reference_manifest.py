#!/usr/bin/env python3
"""Builds references/manifest.json and the contact sheets from references/originals.

Originals are never modified; this script only reads them.
"""
import hashlib, json, pathlib
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[2]
ORIG = ROOT / "references" / "originals"

# Stable IDs. APT = canonical apartment camera view, KIT = asset-kit overview of the
# same apartment, MOOD = night / atmosphere reference from other projects, UI = interface mood.
CLASSIFICATION = [
    ("UI01",  "9f716b4d-image.jpg", "ui_mood",   "Third-party game UI screenshot (NAKWON). Mood/UI-density reference only; not the apartment."),
    ("APT01", "1acbca99-image.jpg", "apartment", "High angle from inside bathroom looking out through doorway: washer, vanity, mirror, toilet, white tile; living area beyond (sofa, floor lamp, TV unit, plates)."),
    ("KIT01", "a4f1f4c0-image.jpg", "asset_kit", "Overview of the apartment's prop/architecture kit laid out on platforms. Object identity + proportion reference."),
    ("APT02", "3ad2b00b-image.jpg", "apartment", "Sleeping-end corner: brick window wall (2 windows, blinds, radiator), desk + green banker lamp + chair, blue bookcase in corner, plaster end wall with AC unit and posters, CRT on floor, boxes, nightstand + lamp, dumbbells."),
    ("APT03", "3c6babac-image.jpg", "apartment", "Closer view of blue bookcase, CRT with box, cardboard boxes, posters, nightstand, bed corner."),
    ("APT04", "4a744ff9-image.jpg", "apartment", "High-angle kitchen counter: steel sink, green kettle, toaster, coffee maker, white gas stove, open shelves on brick, blue cabinets, range hood, side counter, microwave."),
    ("APT05", "2b8b1f8a-image.jpg", "apartment", "High overhead of nearly the whole room: bookcase/bed end at top, sofa centre, barn door + bathroom, fridge, kitchen run on right wall, dining table, round side table + lamp lower-left near window wall, TV unit on left wall."),
    ("APT06", "06bb4a35-image.jpg", "apartment", "Floor-level view along the room toward the bookcase end: round table foreground left, plates wall, fan, barn door, kitchen table + stools on right."),
    ("APT07", "13104115-image.jpg", "apartment", "From floor-lamp/window side toward the kitchen wall: sofa + coffee table, barn door to tiled bathroom, wall clock, fridge, kitchen, dining table + stools, entrance door at far right, electrical panel."),
    ("APT08", "d1e4c74a-image.jpg", "apartment", "Long view from the bed/metal-shelf end toward the kitchen + entrance end: metal shelf, barn door, washer visible, sofa, coffee table, kitchen, white entrance door, easel, plates wall, TV."),
    ("APT09", "69f514f7-image.jpg", "apartment", "From the bed looking toward kitchen end: metal shelf, plates, TV unit, windows, desk with green lamp, ceiling fan."),
    ("APT10", "9d683694-image.jpg", "apartment", "From the kitchen side toward the bookcase end: easel, round table, windows, radiator, plates, TV unit, dining table, sofa, bookcase, metal shelf."),
    ("APT11", "e4a1682d-image.jpg", "apartment", "From behind the sofa facing the brick window wall: round table + lamp, plate collection, TV unit, windows, desk, bookcase, AC, posters, CRT."),
    ("MOOD01", "0218a1db-image.jpg", "night_mood", "Dim Japanese domestic kitchen at night: low-key practical lighting, cluttered lived-in tableware."),
    ("MOOD02", "514f02cb-image.jpg", "night_mood", "Worn apartment interior (ArtStation, M. Khalifa): desaturated grime, window light, lived-in detail. Third-party artwork - mood only."),
    ("MOOD03", "d3e9827e-image.jpg", "night_mood", "Teal attic bedroom, warm window bounce, clutter density."),
    ("MOOD04", "419985f7-image.jpg", "night_mood", "Attic bedroom with red curtains, warm late light, CRT glow."),
    ("MOOD05", "58f13b37-image.jpg", "night_mood", "Attic den: single bare bulb, warm low key, strong practical-light falloff."),
    ("MOOD06", "fcc697dd-image.jpg", "night_mood", "Bedroom lit by bedside lamp: warm pool of practical light, soft fabric."),
    ("MOOD07", "eab2cda4-image.png", "night_mood", "Dim dining room under a single pendant: cool shadow, newspapers, horror tone."),
]

# Role of each reference under the 2026-10-11 scope (all rooms except the living room).
ROLES = {
    "APT01": "canonical:bathroom",
    "MOOD03": "canonical:bedroom_1",
    "MOOD04": "canonical:bedroom_2",
    "MOOD06": "canonical:bedroom_3",
    "MOOD01": "canonical:kitchen",
    "MOOD07": "canonical:hall_tone",
    "MOOD02": "mood:lighting",
    "MOOD05": "mood:lighting",
    "UI01": "mood:ui",
}

def main():
    entries = []
    for rid, name, kind, desc in CLASSIFICATION:
        p = ORIG / name
        data = p.read_bytes()
        with Image.open(p) as im:
            w, h = im.size
        entries.append({"id": rid, "file": f"originals/{name}", "kind": kind, "width": w, "height": h,
                        "sha256": hashlib.sha256(data).hexdigest(),
                        "role": ROLES.get(rid, "living_room:out_of_scope"), "description": desc})
    on_disk = sorted(x.name for x in ORIG.iterdir())
    assert sorted(e["file"].split("/")[1] for e in entries) == on_disk, "manifest/originals mismatch"
    (ROOT / "references" / "manifest.json").write_text(json.dumps({
        "note": "Pixels and filenames are preserved exactly as supplied. 'role' gives each image's use under the current scope (every room except the living room; see docs/CONVENTIONS.md section 0). None of these images may be used as runtime textures or billboards.",
        "references": entries}, indent=2) + "\n")
    sheets = (
        (lambda e: e["role"].startswith("canonical:"), "contact_sheet_canonical_rooms.jpg"),
        (lambda e: e["role"] == "living_room:out_of_scope", "contact_sheet_living_room_out_of_scope.jpg"),
        (lambda e: e["role"].startswith("mood:"), "contact_sheet_mood.jpg"),
    )
    for keep, out in sheets:
        sel = [e for e in entries if keep(e)]
        tw, th, cols = 480, 270, 4
        rows = (len(sel) + cols - 1) // cols
        sheet = Image.new("RGB", (cols * tw, rows * (th + 24)), (18, 18, 18))
        d = ImageDraw.Draw(sheet)
        try:
            font = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        except OSError:
            font = ImageFont.load_default()
        for i, e in enumerate(sel):
            with Image.open(ROOT / "references" / e["file"]) as im:
                im = im.convert("RGB")
                im.thumbnail((tw, th))
                x, y = (i % cols) * tw, (i // cols) * (th + 24)
                sheet.paste(im, (x + (tw - im.width) // 2, y + 24 + (th - im.height) // 2))
                d.text((x + 6, y + 3), f'{e["id"]}  {e["role"]}', fill=(235, 235, 235), font=font)
        sheet.save(ROOT / "references" / out, quality=90)
    print(f"{len(entries)} references; apartment views: {sum(e['kind']=='apartment' for e in entries)}")

if __name__ == "__main__":
    main()
