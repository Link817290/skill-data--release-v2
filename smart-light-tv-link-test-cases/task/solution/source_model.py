import sys
sys.dont_write_bytecode = True
import re
from pathlib import Path

from docx import Document


def document_text(path):
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs]
    tables = [[c.text for c in row.cells] for table in doc.tables for row in table.rows]
    return "\n".join(paragraphs + [" | ".join(row) for row in tables])


def normalize(text):
    return text.replace("\u2264", "<=").replace("\u2265", ">=").replace("\u2013", "-").replace("\u2019", "'")


def sections(path):
    result, current = {}, "intro"
    for paragraph in Document(path).paragraphs:
        text = normalize(paragraph.text)
        match = re.match(r"^(\d+\.\d+)\s+(.+)$", text.strip())
        if match:
            current = match.group(1)
            result[current] = []
        result.setdefault(current, []).append(text)
    return {key: "\n".join(value) for key, value in result.items()}


def number(text, pattern, label):
    match = re.search(pattern, text, re.I)
    if not match:
        raise ValueError(f"Source requirement could not be parsed: {label}")
    return float(match.group(1))


def load_model(materials):
    materials = Path(materials)
    documents = {path: document_text(path) for path in materials.glob("*.docx")}
    # The product guide cites the Ambilight document number in its references;
    # require the actual functional-spec section so material ordering cannot
    # select the wrong source document.
    spec_path = next(path for path, text in documents.items()
                     if "SPEC-HUE-AMB-001" in text and "6.1 End-to-End Latency Requirements" in text)
    sop_path = next(path for path, text in documents.items() if "SOP-HUE-AMB-003-EN" in text)
    product_path = next(path for path, text in documents.items() if "SPEC-HUE-PROD-001" in text)
    spec = sections(spec_path)
    sop_text = normalize(documents[sop_path])
    modes = {mode.lower(): number(spec["6.1"], rf"{mode} Mode:\s*<=\s*([\d.]+)\s*ms", mode)
             for mode in ["Game", "Movie", "Music"]}
    model = {
        "mode_ms": modes,
        "hue_e2e_s": number(spec["7.4"], r"End-to-End[^\n]*?<=\s*([\d.]+)\s*s", "Hue end-to-end"),
        "max_lights": number(spec["7.1"], r"Max Supported Hue Lamps:\s*([\d.]+)", "scene light capacity"),
        "recovery_s": number(spec["12.1"], r"reconnect within\s*([\d.]+)s", "network recovery"),
        "network_prompt_s": number(spec["12.1"], r"offline prompt within\s*([\d.]+)s", "network prompt"),
        "lamp_prompt_s": number(spec["12.2"], r"notification within\s*([\d.]+)s", "lamp prompt"),
        "voice_s": number(spec["10.3"], r"Completion:\s*<=\s*([\d.]+)s", "voice completion"),
        "priority_transition_s": number(spec["12.4"], r"transition time\s*<=\s*([\d.]+)s", "mode transition"),
        "upgrade_timeout_s": number(spec["12.3"], r"upgrade exceeds\s*([\d.]+)s", "upgrade timeout"),
        "memory_growth_pct": number(sop_text, r"memory growth\s*<\s*([\d.]+)%", "memory growth"),
        "stability_h": number(sop_text, r"after\s*([\d.]+)h stress test", "stability duration"),
        "day_lux": number(spec["9.2"], r"Daytime\s*\(>\s*([\d.]+)\s*lux", "daylight threshold"),
        "night_lux": number(spec["9.2"], r"Night\s*\(<\s*([\d.]+)\s*lux", "night threshold"),
        "black_lux": number(spec["9.2"], r"Pitch Black\s*\(<\s*([\d.]+)\s*lux", "pitch black threshold"),
        "priority_order": re.search(r"Priority \(High to Low\):\s*([^\n]+)", spec["12.4"]).group(1).strip(),
        "source_files": {"spec": spec_path.name, "sop": sop_path.name, "product": product_path.name},
        "sections": spec,
        "source_status": "Supplied expert source documents; test design is authored and not an independent solver result."
    }
    reduction = re.search(r"reduce brightness by\s*([\d.]+)%-([\d.]+)%", spec["9.2"], re.I)
    if not reduction:
        raise ValueError("Night reduction could not be parsed")
    model["night_reduction_pct"] = list(map(float, reduction.groups()))
    return model
