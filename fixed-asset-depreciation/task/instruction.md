# Complete the Fixed-Asset Depreciation Model

`materials/workspace.xlsx` provides business parameters, an asset register,
monthly workload inputs and existing report layouts. Complete the calculations
and links in this workbook. Preserve the supplied business inputs, worksheet
structure, formatting and charts; do not invent replacement asset data.

Build annual and monthly schedules for the four depreciation methods and link
them to reporting-period depreciation, accumulated depreciation, carrying
amounts, opening balances, departmental transfers, expense allocation, the
dashboard and model controls. Follow the workbook's business conventions:
depreciation starts in the month after acquisition; residual-rate precedence is
asset override, category default, then global default; workload-method openings
are associated with an asset and year. Transfers take effect in their recorded
month. Attribute expenses to the department in the month they arise and balances
to the department at the reporting cutoff. Support routine maintenance within
the configured capacity and clearly identify incomplete or invalid business inputs.

Use ordinary spreadsheet formulas that recalculate when inputs change. The
completed workbook must open and calculate offline without macros, external
links or a separate runtime script. Save it as `output/fixed_asset_model.xlsx`.
No separate explanatory report is required.
