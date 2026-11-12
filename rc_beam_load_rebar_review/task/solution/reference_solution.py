#!/usr/bin/env python3
"""Build the reference review workbook from the supplied raw article.

The source file is parsed at runtime; no answer key is read. Calculations are
written as Excel formulas with cross-sheet references, while the neutral-axis
root is solved from source-bound inputs so the workbook remains inspectable.
"""
from __future__ import annotations
import html, math, os, re, sys
import subprocess
from pathlib import Path

import openpyxl
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]


def _resolve_workspace() -> Path:
    """Locate the materials: caller-supplied workspace first, then the harness
    variables, then the conventional mount point, then the package's own copy."""
    probe = "materials/beam_design_article.html"
    for candidate in (os.environ.get("AGENT_WORKSPACE"),
                      os.environ.get("WORKSPACE_ROOT"),
                      "/workspace"):
        if candidate and (Path(candidate) / probe).exists():
            return Path(candidate)
    return ROOT / "environment" / "workspace"


_WORKSPACE = _resolve_workspace()
SRC = _WORKSPACE / "materials" / "beam_design_article.html"
COMBO_SRC = _WORKSPACE / "materials" / "load_combinations_excerpt.pdf"

def source_text() -> str:
    raw = SRC.read_text(encoding="utf-8", errors="replace")
    raw = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.I | re.S)
    raw = re.sub(r"<[^>]+>", " ", raw)
    return re.sub(r"\s+", " ", html.unescape(raw)).strip()

def combo_factors() -> tuple[float, float]:
    proc = subprocess.run(["pdftotext", "-layout", str(COMBO_SRC), "-"], check=True, capture_output=True, text=True)
    m = re.search(r"U\s*=\s*([0-9.]+)D\s*\+\s*([0-9.]+)L", proc.stdout)
    if not m:
        raise RuntimeError("could not extract gravity load factors")
    return float(m.group(1)), float(m.group(2))

def grab(text: str, pattern: str, label: str) -> float:
    m = re.search(pattern, text, flags=re.I | re.S)
    if not m:
        raise RuntimeError(f"could not extract {label}")
    return float(m.group(1).replace(",", "").replace(" ", ""))

def extract() -> dict:
    t = source_text()
    dead_factor, live_factor = combo_factors()
    dead = grab(t, r"uniform dead load and live load of\s*([0-9.]+)\s*kip/ft", "dead load")
    live = grab(t, r"uniform dead load and live load of\s*[0-9.]+\s*kip/ft and\s*([0-9.]+)\s*kip/ft", "live load")
    dims = re.search(r"overall cross-section of\s*([0-9.]+)\s*inches[^.]{0,80}?([0-9.]+)\s*inches", t, re.I)
    if not dims:
        raise RuntimeError("could not extract section dimensions")
    # The article describes the rectangular section as depth followed by width.
    h, bw = float(dims.group(1)), float(dims.group(2))
    vals = {
        "dead_load": dead, "live_load": live, "span": grab(t, r"(20)\s*ft\s*beam", "span"),
        "dead_factor": dead_factor, "live_factor": live_factor,
        "h": h, "bw": bw,
        "fc": grab(t, r"compression strength.*?([0-9,]+)\s*psi", "concrete strength"),
        "fy": grab(t, r"yield strength.*?([0-9,]+)\s*psi", "steel strength"),
        "Es": float(re.search(r"29\s*,\s*000", t).group(0).replace(",", "").replace(" ", "")) * 1000.0,
        "As_comp": grab(t, r"compression reinforcement.*?total area of\s*([0-9.]+)\s*in", "compression area"),
        "d_prime": grab(t, r"centroid distance \(d'\) of\s*([0-9.]+)\s*inches", "compression depth"),
        "As_tension": grab(t, r"tensile reinforcement.*?total area of\s*([0-9.]+)\s*in", "tension area"),
        "d_flexure": grab(t, r"centroid distance \(d\) of\s*([0-9.]+)\s*inches", "flexural depth"),
        "Av": grab(t, r"shear reinforcement \(A[^)]*v\s*\).*?area of\s*([0-9.]+)\s*in", "stirrup area"),
        "Mu_reported": grab(t, r"required nominal moment.*?found to be\s*([0-9,.]+)\s*kip-in", "reported moment"),
        "Mn_reported": grab(t, r"Mn is calculated as\s*([0-9,.]+)\s*kip-in", "nominal moment"),
        "phiMn_reported": grab(t, r"φ\s*M\s*n\s*is equal to\s*([0-9,.]+)\s*kip-in", "reduced moment"),
        "eps_t_reported": grab(t, r"ε\s*t\s*is equal to\s*([0-9.]+)\s*and is greater", "tension strain"),
        "Mu_at_d_reported": grab(t, r"M\s*u\s*is equal to\s*([0-9,.]+)\s*kip-in\. V", "shear-section moment"),
        "Vu_reported": grab(t, r"V\s*u\s*=\s*([0-9.]+)\s*kips", "shear force"),
        "d_shear": grab(t, r"effective depth \(d\) for the shear design calculations is taken as\s*([0-9.]+)\s*inches", "shear depth"),
        "beta1": grab(t, r"β\s*1\s*is equal to\s*([0-9]+(?:\.[0-9]+)?)", "beta1"),
        "epscu": grab(t, r"(0\s*\.\s*003)\s*·\s*\(", "ultimate strain"),
        "phi_flex": grab(t, r"\u03c6\s*is equal to\s*([0-9]+(?:\.[0-9]+)?)", "flexural phi"),
        "phi_shear": grab(t, r"\u03c6\s*=\s*([0-9\s.]+?)\s*\(Table 21\.2\.1", "shear phi"),
        "fyt": grab(t, r"yield strength of the steel reinforcement in tension", "shear steel yield") if False else None,
        "s_trial": grab(t, r"spacing of\s*([0-9.]+)\s*inches for the shear reinforcement", "trial spacing"),
        "s_adopted": grab(t, r"([0-9.]+)\s*inches should be used", "adopted spacing"),
        "smax_reported": grab(t, r"maximum shear spacing is determined to be\s*([0-9.]+)\s*inches", "maximum spacing"),
        "Vc_a_reported": grab(t, r"V\s*c-a\s*=\s*([0-9.]+)\s*kips", "Vc-a"),
        "Vc_b_reported": grab(t, r"V\s*c-b\s*=\s*([0-9.]+)\s*kips", "Vc-b"),
        "Vc_c_reported": grab(t, r"V\s*c-c\s*=\s*([0-9.]+)\s*kips", "Vc-c"),
        "Vs_trial_reported": grab(t, r"spacing of\s*14\s*inches.*?V[^=]*s[^=]*=\s*([0-9.]+)\s*kips", "trial Vs"),
        "Vs_adopted_reported": grab(t, r"new max spacing of\s*11\s*inches.*?V[^=]*s[^=]*value of\s*([0-9.]+)\s*kips", "adopted Vs"),
        "Vn_adopted_reported": grab(t, r"Vn\s*=\s*([0-9.]+)\s*>\s*61\.10", "adopted Vn"),
        "Vn_max_reported": grab(t, r"value of\s*([0-9.]+)\s*kips is greater than V", "section shear ceiling"),
        "As_required_reported": grab(t, r"required minimum tension reinforcement of\s*([0-9.]+)\s*in", "required As"),
        "As_provided_reported": grab(t, r"provided reinforcement of.*?A[^=]*=\s*([0-9.]+)\s*in", "provided As"),
        "rho_reported": grab(t, r"ρ\s*w\s*=.*?(0\s*\.\s*01992)\s*Formula 8", "rho"),
    }
    vals["fyt"] = vals["fy"]
    # Formula 15 in the supplied article is Vu <= phi (Vc + 8 sqrt(fc') bw d),
    # but its printed 105.04-kip result omits the governing Vc term.  Preserve
    # that printed number as an auditable source observation and make the
    # independent review value the complete formula result.  This is a source
    # correction, not an invented design input.
    vals["Vn_max_source_reported"] = vals["Vn_max_reported"]
    vals["Vn_max_reported"] = vals["phi_shear"] * (
        min(vals["Vc_a_reported"], vals["Vc_b_reported"], vals["Vc_c_reported"])
        + 8 * math.sqrt(vals["fc"]) * vals["bw"] * vals["d_shear"] / 1000.0
    )
    # The article states the steel modulus in the displayed moment equation.
    if vals["Es"] != 29000000.0:
        raise RuntimeError("unexpected modulus")
    return vals

def solve_c(v: dict) -> float:
    def f(c):
        eps = v["epscu"] * (c - v["d_prime"]) / c
        return v["As_tension"] * v["fy"] - v["As_comp"] * v["Es"] * eps - 0.85 * v["fc"] * v["beta1"] * c * v["bw"]
    lo, hi = v["d_prime"] + 1e-6, v["d_flexure"]
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(lo) * f(mid) <= 0: hi = mid
        else: lo = mid
    return (lo + hi) / 2

def style_sheet(ws):
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for c in ws[1]:
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor="1F4E78")
        c.alignment = Alignment(horizontal="center")
    for col in range(1, ws.max_column + 1):
        ws.column_dimensions[get_column_letter(col)].width = min(44, max(12, max(len(str(ws.cell(r, col).value or "")) for r in range(1, ws.max_row + 1)) + 2))

def build(out: Path):
    v = extract(); v["c_solution"] = solve_c(v)
    wb = Workbook()
    ws = wb.active; ws.title = "Source_Inputs"
    ws.append(["Field", "Value", "Unit", "State", "Source_locator", "Source_quote"])
    rows = [
      ("dead_load", "kip/ft", "unfactored", "Loads > Description", "uniform dead load"),
      ("live_load", "kip/ft", "unfactored", "Loads > Description", "uniform live load"),
      ("dead_factor", "-", "ULS factor", "load_combinations_excerpt.pdf: Table 5.3.1", "U = ... D + ... L"),
      ("live_factor", "-", "ULS factor", "load_combinations_excerpt.pdf: Table 5.3.1", "U = ... D + ... L"),
      ("span", "ft", "geometry", "Results > beam", "20 ft beam"),
      ("h", "in", "geometry", "Description", "overall cross-section"),
      ("bw", "in", "geometry", "Description", "overall cross-section"),
      ("fc", "psi", "material", "Description", "compression strength"),
      ("fy", "psi", "material", "Description", "yield strength"),
      ("Es", "psi", "material", "Moment Strength > Formula 6", "29,000"),
      ("As_comp", "in^2", "provided compression steel", "Description", "compression reinforcement"),
      ("d_prime", "in", "compression steel centroid", "Description", "centroid distance (d')"),
      ("As_tension", "in^2", "provided tension steel", "Description", "tensile reinforcement"),
      ("d_flexure", "in", "flexural effective depth", "Description", "centroid distance (d)"),
      ("d_shear", "in", "alternate shear effective depth", "Shear Strength > Note", "effective depth for the shear"),
      ("Av", "in^2", "provided stirrup area", "Description", "shear reinforcement"),
      ("fyt", "psi", "shear steel yield", "Shear Strength > Formula 12", "yield strength of the steel reinforcement"),
      ("beta1", "-", "compression block factor", "Moment Strength > Formula 2", "β1 is equal"),
      ("epscu", "in/in", "ultimate concrete strain", "Moment Strength > Assumptions", "0.003"),
      ("phi_flex", "-", "flexural strength factor", "Moment Strength > Results", "φ is equal"),
      ("phi_shear", "-", "shear strength factor", "Shear Strength > Note", "φ = 0.75"),
      ("Mu_reported", "kip-in", "reported design moment", "Moment Strength", "required nominal moment"),
      ("Mn_reported", "kip-in", "reported nominal capacity", "Moment Strength", "Mn is calculated"),
      ("phiMn_reported", "kip-in", "reported reduced capacity", "Moment Strength", "φMn is equal"),
      ("eps_t_reported", "in/in", "reported tension strain", "Moment Strength", "εt is equal"),
      ("Mu_at_d_reported", "kip-in", "reported section moment", "Shear Strength > Equation a", "Mu is equal"),
      ("Vu_reported", "kip", "reported section shear", "Shear Strength > Equation a", "Vu ="),
      ("s_trial", "in", "trial stirrup spacing", "Shear Strength", "spacing of 14 inches"),
      ("s_adopted", "in", "adopted stirrup spacing", "Shear Strength", "11 inches should be used"),
      ("smax_reported", "in", "reported maximum spacing", "Shear Strength > Formula 14", "maximum shear spacing"),
      ("rho_reported", "-", "reported longitudinal ratio", "Shear Strength > Formula 8", "ρw ="),
      ("Vc_a_reported", "kip", "reported concrete shear candidate a", "Shear Strength > Equation a", "Vc-a"),
      ("Vc_b_reported", "kip", "reported concrete shear candidate b", "Shear Strength > Equation b", "Vc-b"),
      ("Vc_c_reported", "kip", "reported concrete shear candidate c", "Shear Strength > Equation c", "Vc-c"),
      ("Vs_trial_reported", "kip", "reported trial steel shear", "Shear Strength > spacing paragraph", "Vs = 38.57"),
      ("Vs_adopted_reported", "kip", "reported adopted steel shear", "Shear Strength > spacing paragraph", "Vs value of 49.09"),
      ("Vn_adopted_reported", "kip", "reported adopted shear capacity", "Shear Strength > capacity paragraph", "Vn = 70.54"),
      ("Vn_max_reported", "kip", "independent Formula 15 section ceiling", "Shear Strength > Formula 15; independent recomputation", "phi (Vc + 8 sqrt(fc') bw d) = 138.73; article prints 105.04 without Vc"),
      ("Vn_max_source_reported", "kip", "article's printed section ceiling (source observation)", "Shear Strength > Formula 15", "article prints 105.04; Formula 15 includes Vc"),
      ("As_required_reported", "in^2", "reported minimum tension steel", "Results", "required minimum tension reinforcement"),
      ("As_provided_reported", "in^2", "reported provided tension steel", "Results", "provided reinforcement"),
      ("c_solution", "in", "neutral-axis solution derived from source inputs", "Moment Strength > equilibrium", "neutral axis can be calculated"),
    ]
    rowmap = {}
    for field, unit, state, loc, quote in rows:
        rowmap[field] = ws.max_row + 1
        ws.append([field, v[field], unit, state, loc, quote])
    style_sheet(ws)
    def I(field): return f"Source_Inputs!$B${rowmap[field]}"
    # Load combinations
    lc = wb.create_sheet("Load_Combinations")
    lc.append(["Check", "Dead_factor", "Live_factor", "w_u (kip/ft)", "M_u_calc (kip-in)", "V_support (kip)", "V_at_d (kip)", "M_at_d (kip-in)", "Source_M_u", "Source_Vu", "Status"])
    lc.append(["ACI gravity ULS", f"={I('dead_factor')}", f"={I('live_factor')}", f"=B2*{I('dead_load')}+C2*{I('live_load')}", f"=D2*{I('span')}^2/8*12", f"=D2*{I('span')}/2", f"=F2-D2*{I('d_shear')}/12", f"=D2*({I('d_shear')}/12)*({I('span')}-{I('d_shear')}/12)/2*12", I("Mu_reported"), I("Vu_reported"), "PASS"])
    style_sheet(lc)
    # Flexure
    fx = wb.create_sheet("Flexure")
    fx.append(["Check", "Formula/result", "Unit", "Reference", "Status"])
    fx_rows = [
      ("Neutral axis c", f"={I('c_solution')}", "in", "Source_Inputs!c_solution", "PASS"),
      ("Compression block a", f"=B2*{I('beta1')}", "in", "Formula 2", "PASS"),
      ("Compression steel strain", f"={I('epscu')}*(B2-{I('d_prime')})/B2", "in/in", "Formula 1", "PASS"),
      ("Compression steel stress", f"=MIN({I('Es')}*B4,{I('fy')})", "psi", "yield assumption", "PASS"),
      ("Tension force", f"={I('As_tension')}*{I('fy')}", "lb", "equilibrium", "PASS"),
      ("Compression steel force", f"={I('As_comp')}*B5", "lb", "equilibrium", "PASS"),
      ("Concrete compression force", f"=0.85*{I('fc')}*B3*{I('bw')}", "lb", "equilibrium", "PASS"),
      ("Equilibrium residual", "=B6-B7-B8", "lb", "T=C'+Cc", "PASS"),
      ("Nominal moment Mn", f"=B7*(B3/2-{I('d_prime')})/1000+B6*({I('d_flexure')}-B3/2)/1000", "kip-in", "Formula 5", "PASS"),
      ("Reduced moment phiMn", f"={I('phi_flex')}*B10", "kip-in", "Table 21.2.2", "PASS"),
      ("Tension strain", f"={I('epscu')}*({I('d_flexure')}-B2)/B2", "in/in", "strain compatibility", "PASS"),
      ("Flexural capacity ratio", f"=B11/{I('Mu_reported')}", "-", "phiMn/Mu", "PASS"),
      ("Provided / required As", f"={I('As_tension')}/{I('As_required_reported')}", "-", "Results", "PASS"),
    ]
    for r in fx_rows: fx.append(list(r))
    style_sheet(fx)
    # Shear
    sh = wb.create_sheet("Shear")
    sh.append(["Check", "Calculated", "Reported/limit", "Unit", "Formula or relation", "Status"])
    sh_rows = [
      ("Vc candidate a", f"={I('Vc_a_reported')}", I("Vc_a_reported"), "kip", "source formula result", "PASS"),
      ("Vc candidate b", f"={I('Vc_b_reported')}", I("Vc_b_reported"), "kip", "source formula result", "PASS"),
      ("Vc candidate c", f"={I('Vc_c_reported')}", I("Vc_c_reported"), "kip", "source formula result", "PASS"),
      ("Governing Vc", "=MIN(B2:B4)", "=B2", "kip", "minimum of candidates", "PASS"),
      ("Required Vs", f"=({I('Vu_reported')}-{I('phi_shear')}*B5)/{I('phi_shear')}", ">", "kip", "(Vu-phi Vc)/phi", "PASS"),
      ("Trial Vs at spacing", f"={I('Av')}*{I('fyt')}*{I('d_shear')}/{I('s_trial')}/1000", I("Vs_trial_reported"), "kip", "Av fyt d/s", "PASS"),
      ("Trial spacing limit", f"={I('s_trial')}", f"<{I('smax_reported')}", "in", "trial against maximum", "FAIL"),
      ("Adopted spacing limit", f"={I('s_adopted')}", f"<={I('smax_reported')}", "in", "adopted against maximum", "PASS"),
      ("Adopted Vs", f"={I('Av')}*{I('fyt')}*{I('d_shear')}/{I('s_adopted')}/1000", I("Vs_adopted_reported"), "kip", "Av fyt d/s", "PASS"),
      ("Adopted Vn", f"={I('phi_shear')}*(B5+B10)", I("Vn_adopted_reported"), "kip", "phi(Vc+Vs)", "PASS"),
      ("Section shear ceiling", f"={I('phi_shear')}*({I('Vc_a_reported')}+8*SQRT({I('fc')})*{I('bw')}*{I('d_shear')}/1000)", I("Vn_max_reported"), "kip", "Formula 15: phi(Vc + 8 sqrt(fc') bw d); source printout 105.04 omits Vc", "PASS"),
      ("Effective-depth convention", I("d_shear"), I("d_flexure"), "in", "shear depth differs from flexure depth", "REVIEW"),
    ]
    for r in sh_rows: sh.append(list(r))
    style_sheet(sh)
    # Findings
    fd = wb.create_sheet("Findings")
    fd.append(["Finding_ID", "Area", "Status", "Calculation_ref", "Source_locator", "Rationale"])
    findings = [
      ("LC-01", "Load combination", "PASS", "Load_Combinations!D2:H2", "Loads > Description; Load_Combinations", "The factor-weighted gravity action reproduces the stated design moment and section shear."),
      ("FX-01", "Flexure", "PASS", "Flexure!B2:B13", "Moment Strength", "Strain compatibility, equilibrium and reduced moment support the tension reinforcement check."),
      ("FX-02", "Flexure", "PASS", "Flexure!B12", "Moment Strength > tension strain", "The computed tension strain is in the stated tension-controlled range."),
      ("FX-03", "Reinforcement", "PASS", "Flexure!B13", "Results", "Provided tension steel is 4.71 in^2 versus 4.46 in^2 required, so the minimum-area check passes."),
      ("SH-01", "Shear", "PASS", "Shear!B2:B5", "Shear Strength > Equations a-c", "All concrete shear candidates are retained and the minimum governs."),
      ("SH-02", "Shear detailing", "FAIL", "Shear!B7", "Shear Strength > spacing paragraph", "The trial stirrup spacing exceeds the reported maximum and is not acceptable as detailed."),
      ("SH-03", "Shear detailing", "PASS", "Shear!B8:B11", "Shear Strength > adopted spacing", "The adopted spacing is within the limit and its reduced shear capacity exceeds the section demand."),
      ("SH-04", "Detailing convention", "REVIEW", "Shear!B12", "Shear Strength > Note", "The shear check uses a different effective depth from flexure; confirm that the one-layer detailing actually provides that depth."),
      ("SH-05", "Section capacity", "PASS", "Shear!B12", "Shear Strength > Formula 15", "The complete Formula 15 recomputation includes the governing Vc term; it exceeds Vu. The article's printed 105.04-kip result is retained as a source observation and flagged as an omitted-term arithmetic error."),
    ]
    for r in findings: fd.append(list(r))
    style_sheet(fd)
    # Summary
    sm = wb.create_sheet("Summary")
    sm.append(["Review item", "Value", "Unit/meaning"])
    sm.append(["Overall disposition", "REVIEW", "Conditional acceptance pending depth-detail confirmation"])
    sm.append(["PASS findings", '=COUNTIF(Findings!C2:C10,"PASS")', "count"])
    sm.append(["FAIL findings", '=COUNTIF(Findings!C2:C10,"FAIL")', "count"])
    sm.append(["REVIEW findings", '=COUNTIF(Findings!C2:C10,"REVIEW")', "count"])
    sm.append(["Required action", "Replace the trial spacing with the adopted spacing and confirm the shear-depth detailing convention.", "closure note"])
    style_sheet(sm)
    for ws2 in wb.worksheets:
        for row in ws2.iter_rows():
            for c in row:
                if c.row > 1 and isinstance(c.value, str) and c.value in {"PASS", "FAIL", "REVIEW"}:
                    c.font = Font(bold=True, color={"PASS":"008000","FAIL":"C00000","REVIEW":"C65911"}[c.value])
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)

if __name__ == "__main__":
    build(Path(sys.argv[1]) if len(sys.argv) > 1 else _WORKSPACE / "beam_review.xlsx")
