import argparse
from pathlib import Path
from report_logic import create_report, load_facts

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    args = parser.parse_args()
    materials = args.workspace/"materials"
    if not materials.is_dir():
        materials = Path(__file__).resolve().parents[1]/"environment/workspace/materials"
    create_report(materials,args.workspace/"output/service-quality-report.xlsx")
