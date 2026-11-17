# Prepare the trade recall pack

Install the packages in requirements.txt, then run:

```sh
python build_registers.py --input /workspace/input --out /workspace/output
```

The script extracts the ruled product tables from the four supplier PDFs, reconciles pack additions, and writes the three CSV registers and trade notice. It checks notice identifiers before accepting a table. Highlighted prose is not treated as a product table. Dates and narrative conditions are taken from the supplied historical notices; a new recall requires review of its own conditions.

The outputs identify products and distribution relationships. They do not supply missing stock counts, production genealogy or completed disposition records.
