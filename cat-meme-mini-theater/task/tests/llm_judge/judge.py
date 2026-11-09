"""Portable public entry point. Requires Python 3, Node 22, FFmpeg and ffprobe."""
import pathlib
import subprocess
import sys

if __name__ == "__main__":
    sys.exit(subprocess.call(["node", str(pathlib.Path(__file__).parent / "runtime" / "judge.mjs"), *sys.argv[1:]]))
