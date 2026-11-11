We would like to decide how to improve delivery service at Jiangwan. Please review the records and proposals in `/workspace/input/` and recommend an upgrade plan we can confidently put into practice.

Deliver a decision report (Word or PDF), a completed copy of `/workspace/input/配送方案交付模板.xlsx`, and reproducible calculation files. Follow the template's field and unit conventions; additional analysis sheets are welcome. Explain the evidence, trade-offs, and limits of your recommendation. Write the report and workbook in Chinese using SimSun.

Save the following deliverables at these exact absolute paths:

- `/workspace/output/analysis.xlsx`: the completed workbook.
- Exactly one of `/workspace/output/decision_report.pdf` or `/workspace/output/decision_report.docx`: the decision report.
- `/workspace/output/calculations/solve.py`: the runnable entry point for reproducing the calculations. Additional supporting files may be included in this directory.
- `/workspace/output/calculations/README.md`: the dependencies and exact commands for reproducing the results from the supplied inputs.

Create `/workspace/output/` if needed. Deliver actual, readable, nonempty files there; a file list or links in the final response are not substitutes. Use these filenames and do not save the deliverables under `/workspace/workspace/output/`.

In the `订单状态` worksheet, `消息编号` means only the message IDs from the
highest business revision that supplies the current row. Historical message IDs
may be retained in the adjacent optional `历史消息编号` column for audit
traceability; they must not replace or be mixed into the current-version field.
For quarantined revision conflicts, leave business attributes that cannot be
resolved from the conflicting branch blank and keep the conflict reason visible.
