# Putting a table inside a template

Adding a table inside a cell of an existing table is mechanically different from adding a table to a document. Getting this wrong is the most common way a correct plan produces a wrong file: the content is right, the structure is not, and the report no longer matches the shape everyone else's copies have.

This page describes one family of toolchains, the ones with a document object model where a cell is itself a container. Read the last section first if your template is not one of those, because in some formats nesting is not possible at all and the right answer is different.

## The core distinction

A document library's top level table collection belongs to the document body. Appending there puts a new table after the existing content, as a sibling of the template's own table rather than inside it. What you want instead is to add the table to the cell object, so it lives within that cell's content.

In the Python library for Word documents, python-docx, a cell object exposes its own `add_table` and calling it on the cell is what places the new table inside that cell. Reaching the target cell means indexing into the outer table's rows and then its cells. Other toolchains name things differently, but the distinction is the same: a container's own add method versus the document's.

Two consequences follow, and both matter:

* Adding to the document body leaves the template intact but puts your table in the wrong place, usually after everything else.
* Rebuilding the outer table to make room, or splitting a cell to hold the new content, changes the template's shape. That is worse, because the shape is what colleagues, past editions, and any downstream consumer rely on.

## Merged cells and how they read back

Template cells that span several columns report back once per underlying grid position. When you walk an outer row's cells you may therefore encounter the same merged cell, and the same nested table inside it, as many times as that cell spans grid positions. De duplicate by object identity before counting, or one nested table will look like several.

The same effect appears inside your own schedule table when a span covers several period columns. Whether you build the span by merging cells or by repeating the text across them, reading the row back gives you the text once per covered column. This is useful: counting the populated cells in a row gives you the visual span length, which is what you want to check against the commitment.

It is also a trap when counting values rather than structure. If you scan the document's text for figures, a single stated number inside a merged cell appears many times over. De duplicate before drawing any conclusion from how many times something occurs.

## Verifying what you built

A cell's text property is not a reliable window onto nested structure, and libraries differ in which direction it misleads. Some return the text of any nested table concatenated with the cell's own paragraphs, so a report with the tables and one without read identically. Others return only the cell's own paragraphs, so text you did put in a nested table is simply absent, and anything downstream that searches the text will report your figures missing even though the table is there. Do not assume either behaviour; check which one your library does before relying on it.

Verify by structure instead:

1. Open the file you actually wrote, not the object you built in memory.
2. Confirm the outer table's row and column counts are unchanged from the template.
3. For each cell that should carry a nested table, ask the cell for its tables and confirm you get one, de duplicated by identity.
4. Confirm each nested table's own row and column counts match what you intended to build.
5. Confirm the document body still has the same number of top level tables the template had. More than that usually means a nested table was appended to the document rather than to the cell. Compare against the template rather than against a fixed number, since templates differ in how many tables they carry.

Run this check as a script against the saved file. Opening the document in a viewer will show you that something is there but will not tell you whether it is nested where it needs to be.

## Formatting inside the nested table

Keep it simple and let the outer document's styles apply. A nested table does not need its own theme, and heavy styling inside one often breaks when the outer document is opened elsewhere. A header row and plain cell text are enough. Where the toolchain supports it, apply a plain grid style so the borders render, since a borderless nested table can read as loose text once printed.

## When the format cannot nest

Not every template is a document object model with containers inside containers.

* **A spreadsheet workbook.** There is no table inside a cell. The equivalent task is inserting rows or a block into the sheet, and the risk is different: named ranges, merged headers, and the workbook's own formulas can all break when rows shift. Insert where the sheet is designed to grow, and check the workbook's formulas still resolve afterwards.
* **A fillable form or a fixed field layout.** Nesting is impossible. Put the table in an appendix or attachment and cross reference it from the field, for example a short line naming the attachment. Do not try to render a grid as spaced text inside a single field, which reads as damage rather than structure.
* **A plain text or lightweight markup template.** A text table is legitimate here if the template's other content is text, but check how the recipient renders it before relying on alignment.

In all three cases the underlying judgment from the entry page still applies: parallel items still want a tabular shape, and a claim still wants its figures attached. Only the mechanics change. What does not change is that you may not restructure the template to make nesting possible.
