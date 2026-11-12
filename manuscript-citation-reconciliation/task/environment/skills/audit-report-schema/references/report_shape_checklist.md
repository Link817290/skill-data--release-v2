# Delivery checklist

- The report is valid UTF-8 JSON.
- Every supplied DOCX appears once.
- Both discrepancy arrays appear for every manuscript, including when empty.
- Entry text is copied verbatim from the extracted source.
- Summary counts are recomputed from the arrays.
- Every body bracket expression is represented in either `citation_occurrences` or `ignored_bracket_expressions`, with exact source paragraph text and index.
- `boundary` contains both bibliography boundary indexes, and every unmatched reference review contains normalized identity evidence.
- No outside source, guessed metadata, or unrequested artifact is included.
