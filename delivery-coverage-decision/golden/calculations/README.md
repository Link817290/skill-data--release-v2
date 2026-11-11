# Reproduce the calculations

Use Python 3.11 or later and install `requirements.txt`. From this directory run:

```sh
python solve.py --input /workspace/input --output /workspace/output/calculations/recomputed
```

The solver reads the supplied business documents and CSV records and produces
order, route, assignment, resource and decision evidence in the specified directory.
Keep the original input records unchanged. Distinct tied assignments can have
the same objective values. The calculation outputs support the decision report;
they do not establish operational approval or actual service performance.
