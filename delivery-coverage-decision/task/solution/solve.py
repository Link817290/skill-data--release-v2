"""Reference calculation entrypoint; algorithm lives once in Golden."""
import runpy
import sys
from pathlib import Path
folder=Path(__file__).resolve().parents[2]/'golden/calculations'
sys.path.insert(0,str(folder))
runpy.run_path(str(folder/'solve.py'),run_name='__main__')
