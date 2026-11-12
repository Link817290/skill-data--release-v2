# Complete the manufacturing time-study workbook

Restore the missing calculations in `/workspace/materials/workspace.xlsx` and save `/workspace/output/standard_time.xlsx`. Preserve the original worksheets, Chinese business fields, input values and layout. Deliver a self-contained Excel tool whose formulas recalculate correctly after input edits, without external data links or macros.

## Output Cells

- `工时测量记录表`: `V5:Z24`, `AF5:AF24`, `AH5:AI24`.
- `标准版`: `L6:L10`, `O6:O10`, `Q6:S10`, `V6:V10`, `X6:X10`.

## Case Conventions

- Population deviation; one inclusive three-sigma screening pass; nonnegative lower bound. Recorded zeros are valid observations.
- `工时测量记录表!AE` is a supplied combined rating input. Retain each worksheet's own allowance convention.
- `标准版!L` refers to the station's `上下工装` normal-time record. `S` is the complete station-cycle ratio `(L + N) / (K + M)`: `L + N` is its numerator and the original `K + M` activity fields are its denominator.
- A blank source component in `标准版!K6:K10` represents zero activity for that component. `L6:L10` are missing output formulas to restore, not blank source inputs.
- The original theoretical-personnel calculation has a fixed planning multiplier of **2**. Report theoretical quantities without integer rounding.
