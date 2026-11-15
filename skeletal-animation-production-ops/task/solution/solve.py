from pathlib import Path
import shutil,sys
task=Path(__file__).resolve().parents[1]
package=task.parent
out=Path(sys.argv[1]) if len(sys.argv)>1 else task/'environment/workspace/output'
shutil.copytree(package/'golden',out,dirs_exist_ok=True)
print(out.resolve())
