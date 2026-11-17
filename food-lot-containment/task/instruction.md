We need a trade recall pack that our warehouse and retail contacts can act on. Bring the supplier notices in `/workspace/input/supplier-notices/` together as of December 2, 2024, prepare the product and distribution registers, and give us a clear notice explaining what recipients should do and what information they should return.

Use UTF-8 CSV and the upload fields in `/workspace/input/register-fields.csv`. Save the following deliverables at these exact absolute paths:

- `/workspace/output/product-scope.csv`: the product register.
- `/workspace/output/pack-changes.csv`: the pack-change register.
- `/workspace/output/distribution-list.csv`: the distribution register.
- Exactly one of `/workspace/output/trade-recall-notice.docx` or `/workspace/output/trade-recall-notice.pdf`: the English recipient notice.
- `/workspace/output/preparation/build_registers.py`: the runnable entry point for reproducing the registers. Additional supporting files may be included in this directory.
- `/workspace/output/preparation/README.md`: the dependencies and exact commands for reproducing the pack from the supplied inputs.

Create `/workspace/output/` if needed. Deliver actual, readable, nonempty files there; a file list or links in the final response are not substitutes. Use these filenames and do not save the deliverables under `/workspace/workspace/output/`.
