"""Locate the pinned Godot executable."""
from pathlib import Path
import os,shutil

def godot_binary(explicit=None):
    if explicit:return explicit
    if os.environ.get('GODOT_BIN'):return os.environ['GODOT_BIN']
    local=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'skill-data-runtime/skeletal-animation-production-ops/godot/Godot_v4.4.1-stable_win64_console.exe'
    if local.exists():return str(local)
    found=shutil.which('godot') or shutil.which('godot4')
    if not found:raise RuntimeError('Godot missing; run environment/skeletal-animation-production-ops/build-context/bootstrap.ps1 or set GODOT_BIN')
    return found
