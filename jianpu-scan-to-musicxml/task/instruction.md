# Transcribe a historical Chinese score into diplomatic MEI

A music archive needs the two consecutive pages in `materials/source_page_01.png`
and `materials/source_page_02.png` converted into one editable
`/workspace/output/揚州慢.mei` file. Read the pages in their printed vertical order
and preserve the complete title, attribution, mode heading, prose preface, sung
text, and every adjacent suzipu notation position.

Encode each music position with its lyric character, primary suzipu pitch class,
any secondary sign, inclusion or cancellation status, page and column boundary,
and a facsimile link to the corresponding text and notation regions. Retain the
two source pages as MEI facsimile surfaces so a cataloguer can trace structured
content back to the scans. The result must be well-formed, parseable MEI; XML IDs,
indentation, and element ordering are implementation choices.

This source does not determine modern meter, absolute pitch, or note duration.
Do not invent those values, do not modify the supplied scans, do not use the
network, and do not import musical content from an edition outside `/workspace`.

Before editing, inspect the procedures available in the working environment and
apply any whose scope matches this historical-notation conversion.
