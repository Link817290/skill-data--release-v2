"""Top-level settlement shared by the compatibility contract."""


def settle(schedule_witness, independent_controls):
    if not 0 <= schedule_witness <= 1 or not 0 <= independent_controls <= 1:
        raise ValueError("Completion values must lie in [0, 1]")
    return 0.80 * schedule_witness + 0.20 * independent_controls
