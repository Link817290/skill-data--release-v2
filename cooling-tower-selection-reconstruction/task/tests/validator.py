"""JSON adapter for offline artifact replay."""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
from original_validator import main


if __name__=='__main__':
 root=Path(sys.argv[1])
 artifact=root if root.is_file()else root/'cooling_tower.xlsx'if root.name=='golden'else root/'output/cooling_tower.xlsx'
 with tempfile.TemporaryDirectory(prefix='tower-verifier-')as tmp:
  sys.argv=[sys.argv[0],'--artifact',str(artifact),'--logs',tmp]
  with contextlib.redirect_stdout(io.StringIO()):main()
  print((Path(tmp)/'reward_detail.json').read_text())
