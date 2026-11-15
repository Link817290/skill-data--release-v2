"""Expose the measured native strict result through the delivery reward field."""
import json
import math
import os
from pathlib import Path
import stat
import sys
import tempfile


def main():
    path = Path(sys.argv[1])
    original = path.read_bytes()
    value = json.loads(original)
    strict = value.get('rewards', {}).get('strict')
    if (value.get('status') != 'measured' or isinstance(strict, bool)
            or not isinstance(strict, (int, float)) or not math.isfinite(strict)
            or not 0 <= strict <= 1):
        raise ValueError('A measured finite native strict reward is required')
    if 'reward' in value:
        if value['reward'] != strict:
            raise ValueError('Top-level reward conflicts with the native strict result')
        return
    native = path.with_name('reward.native.json')
    with native.open('xb') as stream:
        stream.write(original)
    value['reward'] = strict
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent,
                                         prefix='.reward-', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write('\n')
        os.chmod(temporary, stat.S_IMODE(path.stat().st_mode))
        os.replace(temporary, path)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


if __name__ == '__main__':
    main()
