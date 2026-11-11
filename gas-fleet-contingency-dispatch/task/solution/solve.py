#!/usr/bin/env python3
from pathlib import Path
import os
import shutil
import subprocess
import sys


default_root = (
    Path("/workspace")
    if Path("/workspace/materials").is_dir()
    else Path(__file__).resolve().parents[1] / "environment" / "workspace"
)
root = Path(os.environ.get("TASK_WORKSPACE", default_root))
template = Path(__file__).with_name("dispatch_model_template.py")
output = root / "output"
output.mkdir(parents=True, exist_ok=True)
target = output / "dispatch_model.py"
shutil.copyfile(template, target)
target.chmod(0o755)
subprocess.run([sys.executable, str(target), "--workspace", str(root)], cwd=root, check=True)
