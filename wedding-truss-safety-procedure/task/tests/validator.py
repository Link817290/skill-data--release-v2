import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent/'program_judge'))
from task_judge import main
if __name__=='__main__': main()
