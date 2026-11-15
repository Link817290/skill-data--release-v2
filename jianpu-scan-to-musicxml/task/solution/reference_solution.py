#!/usr/bin/env python3
"""Build a material-bound diplomatic MEI transcription from expert annotation."""

from __future__ import annotations

import hashlib
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


MEI = "http://www.music-encoding.org/ns/mei"
XML = "http://www.w3.org/XML/1998/namespace"
PAGE_WIDTH = 800
SCAN_HASHES = {
    "source_page_01.png": "07d2f714777b9ae1cf2cfc1cf67b1267f8d2b189682a12f0ed02dbbe20f0aca8",
    "source_page_02.png": "342f405755c426ad220a08684521b8b569d16122db0587f5e0952a610da818e1",
}


def qname(name: str) -> str:
    return f"{{{MEI}}}{name}"


def add(parent: ET.Element, name: str, text: str | None = None, **attrs: str) -> ET.Element:
    node = ET.SubElement(parent, qname(name), attrs)
    if text is not None:
        node.text = text
    return node


def page_and_box(box: list[list[int]]) -> tuple[int, list[int]]:
    x1, y1 = box[0]
    x2, y2 = box[1]
    page = 1 if x1 >= PAGE_WIDTH else 2
    offset = PAGE_WIDTH if page == 1 else 0
    return page, [x1 - offset, y1, x2 - offset, y2]


def add_zone(surface: ET.Element, zone_id: str, box: list[int], zone_type: str) -> None:
    add(
        surface,
        "zone",
        **{
            f"{{{XML}}}id": zone_id,
            "type": zone_type,
            "ulx": str(box[0]),
            "uly": str(box[1]),
            "lrx": str(box[2]),
            "lry": str(box[3]),
        },
    )


def verify_materials(workspace: Path) -> None:
    for name, expected in SCAN_HASHES.items():
        path = workspace / "materials" / name
        if not path.is_file():
            raise SystemExit(f"missing source image: {path}")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise SystemExit(f"source image does not match retained page: {name}")


def build_mei(annotation: dict, output: Path) -> None:
    ET.register_namespace("", MEI)
    root = ET.Element(qname("mei"), {"meiversion": "5.0"})
    head = add(root, "meiHead")
    file_desc = add(head, "fileDesc")
    title_stmt = add(file_desc, "titleStmt")
    add(title_stmt, "title", "揚州慢")
    add(title_stmt, "composer", annotation.get("composer", ""))
    pub_stmt = add(file_desc, "pubStmt")
    add(pub_stmt, "availability", "Diplomatic transcription for archival interchange")
    encoding = add(head, "encodingDesc")
    project = add(encoding, "projectDesc")
    add(project, "p", "Source-faithful vertical Chinese suzipu transcription with facsimile zones")

    facsimile = add(root, "facsimile")
    surfaces = {}
    for page, (name, height) in enumerate((("source_page_01.png", 1233), ("source_page_02.png", 1274)), 1):
        surface = add(
            facsimile,
            "surface",
            **{f"{{{XML}}}id": f"p{page:02d}", "n": str(page), "ulx": "0", "uly": "0", "lrx": "800", "lry": str(height)},
        )
        add(surface, "graphic", target=f"../materials/{name}", width="800px", height=f"{height}px")
        surfaces[page] = surface

    music = add(root, "music")
    body = add(music, "body")
    mdiv = add(body, "mdiv", type="suzipu")
    score = add(mdiv, "score")
    add(score, "scoreDef", type="suzipu")
    section = add(score, "section")
    metadata = add(section, "div", type="source-metadata")
    for index, entry in enumerate(annotation.get("attribution_characters", [])):
        zone = f"attribution-{index}"
        add_zone(surfaces[entry["page"]], zone, entry["box"], "attribution-text")
        add(metadata, "annot", entry["text"], type="attribution", n=str(index), facs=f"#{zone}")
    staff = add(section, "staff", n="1")
    layer = add(staff, "layer", n="1")

    event_number = 0
    current_page = 1
    for source_index, item in enumerate(annotation.get("content", []), 1):
        box_type = item.get("box_type", "")
        text_box = item.get("text_coordinates")
        notation_box = item.get("notation_coordinates")
        text_zone = ""
        notation_zone = ""
        item_page = current_page
        if text_box:
            item_page, local = page_and_box(text_box)
            text_zone = f"tx{source_index:03d}"
            add_zone(surfaces[item_page], text_zone, local, f"{box_type.lower()}-text")
        if notation_box:
            note_page, local = page_and_box(notation_box)
            item_page = note_page
            notation_zone = f"nt{source_index:03d}"
            add_zone(surfaces[note_page], notation_zone, local, "suzipu-sign")

        if box_type != "Music":
            attrs = {"type": box_type.lower(), "n": str(source_index), "data-line-break": str(bool(item.get("is_line_break"))).lower()}
            if text_zone:
                attrs["facs"] = f"#{text_zone}"
            add(metadata, "annot", item.get("text_content") or "", **attrs)
            continue

        event_number += 1
        if item_page != current_page:
            add(layer, "pb", n=str(item_page), facs=f"#p{item_page:02d}")
            current_page = item_page
        notation = item.get("notation_content") or {}
        attrs = {
            f"{{{XML}}}id": f"e{event_number:03d}",
            "n": str(event_number),
            "type": "excluded" if item.get("is_excluded_from_dataset") else "included",
            "data-line-break": str(bool(item.get("is_line_break"))).lower(),
            "data-page": str(item_page),
        }
        if text_zone:
            attrs["facs"] = f"#{text_zone}"
        syllable = add(layer, "syllable", **attrs)
        verse = add(syllable, "verse", n="1")
        add(verse, "syl", item.get("text_content") or "")
        neume = add(syllable, "neume")
        nc_attrs = {"label": str(notation.get("pitch") or ""), "type": "suzipu-pitch"}
        if notation_zone:
            nc_attrs["facs"] = f"#{notation_zone}"
        nc = add(neume, "nc", **nc_attrs)
        if notation.get("secondary"):
            add(nc, "annot", str(notation["secondary"]), type="secondary-sign")
        if item.get("is_line_break"):
            add(layer, "cb", n=str(sum(1 for x in annotation["content"][:source_index] if x.get("box_type") == "Music" and x.get("is_line_break"))))

    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root, space="  ")
    output.write_bytes(ET.tostring(root, encoding="utf-8", xml_declaration=True))


def main(workspace: Path) -> None:
    verify_materials(workspace)
    annotation_path = Path(__file__).with_name("source_annotation.json")
    annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
    build_mei(annotation, workspace / "output" / "揚州慢.mei")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/workspace"))
