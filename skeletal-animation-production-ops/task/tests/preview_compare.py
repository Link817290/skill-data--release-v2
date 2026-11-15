"""Compare rendered content independently of image container metadata."""
import csv
from PIL import Image


def equivalent_preview(expected, supplied):
    if not expected.is_file() or not supplied.is_file():return False
    try:
        if expected.suffix.lower()=='.csv':
            with expected.open(encoding='utf-8-sig',newline='') as left, supplied.open(encoding='utf-8-sig',newline='') as right:
                return list(csv.reader(left))==list(csv.reader(right))
        with Image.open(expected) as left,Image.open(supplied) as right:
            frames=getattr(left,'n_frames',1)
            if left.size!=right.size or frames!=getattr(right,'n_frames',1):return False
            if expected.suffix.lower()=='.gif' and left.info.get('loop',1)!=right.info.get('loop',1):return False
            for index in range(frames):
                left.seek(index);right.seek(index)
                if left.convert('RGBA').tobytes()!=right.convert('RGBA').tobytes():return False
                if frames>1 and left.info.get('duration',0)!=right.info.get('duration',0):return False
            return True
    except (OSError,ValueError,EOFError):return False
