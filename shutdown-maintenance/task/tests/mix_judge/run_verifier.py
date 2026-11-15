"""Declare the measured program, semantic and settlement composition."""
from pathlib import Path

from runtime.settlement import settle


def merge(schedule_witness, independent_controls):
    return settle(schedule_witness, independent_controls)


def run(validator, numeric, semantic):
    validator.check(Path(numeric))
    return merge(semantic["schedule_witness"], semantic["independent_controls"])
