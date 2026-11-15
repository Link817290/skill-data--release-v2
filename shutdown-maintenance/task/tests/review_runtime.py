"""Compatibility API for the source-bound review-chain profile."""
from mix_judge.runtime.settlement import settle


def merge(schedule_witness, independent_controls):
    return settle(schedule_witness, independent_controls)
