We need a dependable offline check for our archived instrument measurements, so the team can rerun the review when records or control settings change. Build a small Python command-line tool that identifies exceptions and keeps the limits of the available evidence clear.

Use the files in `/workspace/input/instrument-history/`, `/workspace/input/calibration-record.docx` and `/workspace/input/measurement-interface.json`. Save the following deliverables at these exact absolute paths:

- `/workspace/output/measurement-check/measurement_check.py`: the runnable Python command-line tool.
- `/workspace/output/measurement-check/README.md`: the English usage guide, dependencies and exact commands for reproducing the supplied-input review.
- `/workspace/output/review-results.json`: the review results produced by running the tool on the supplied inputs.
- `/workspace/output/exceptions.csv`: the exceptions register produced by that run, including its header when no exceptions are found.

If a dependency list is needed, name it `/workspace/output/measurement-check/requirements.txt`. Additional supporting files may be included in `/workspace/output/measurement-check/`.

The CLI is `python /workspace/output/measurement-check/measurement_check.py --mass MASS.csv --optical OPTICAL.csv --config SETTINGS.json --output DIRECTORY`; replace the uppercase arguments with the applicable input paths and use `/workspace/output/` as `DIRECTORY` for the required delivered results.

Create `/workspace/output/` if needed. Deliver actual, readable, nonempty files there; a file list or links in the final response are not substitutes. Use these filenames and do not save the deliverables under `/workspace/workspace/output/`.
