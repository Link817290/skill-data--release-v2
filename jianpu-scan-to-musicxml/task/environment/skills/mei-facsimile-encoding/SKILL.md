---
name: mei-facsimile-encoding
description: Encode a diplomatic transcription as source-linked MEI, including facsimile surfaces and zones, metadata regions, ordered notation events, editorial status, and structural validation. Use after a scan has been resolved into a source-bound ledger.
---

# MEI Facsimile Encoding

## Scope and Delivery Boundary

Use this procedure after visual reading has produced an ordered ledger with
source regions. It covers portable MEI representation and closure, not glyph
recognition. This procedure and its validator are separately mounted runtime
aids, not source evidence and not workspace materials.

The accompanying `scripts/validate_mei_facsimile.py` checks a file supplied by
the operator. It reports generic XML, facsimile-link, coordinate, and event
structure issues; it contains no source transcription and does not determine
which pitch class or text is correct.

## Business Step 1: Declare a Diplomatic MEI Document

Create one well-formed MEI document in the MEI namespace. Use an `meiHead` with a
minimal `fileDesc`, `titleStmt`, and `pubStmt`, then put the encoded source under
`music/body/mdiv/score`. Keep Unicode text as printed. Modernized titles or silent
character substitutions should not replace the diplomatic values.

Represent source-specific mode information without pretending that it is modern
key or meter data. Project-specific `data-*` attributes or typed annotations are
appropriate when MEI has no exact native field. Use stable controlled values and
document their meaning in element types or labels.

Do not create `meterSig`, timed notes, absolute pitch, or playback data merely to
make the file resemble a modern score. An intentionally atemporal diplomatic MEI
is more faithful than a precise-looking invented performance.

## Business Step 2: Build Facsimile Surfaces and Zones

Create one `surface` for each physical image in page order. Give each surface a
unique XML ID, page number, dimensions, and a `graphic` target resolving to the
corresponding image. The path may be relative to the MEI file; confirm that it
resolves from the delivered location.

Create separate zones for text and notation evidence. Each zone needs a unique
XML ID and ordered coordinates:

```xml
<zone xml:id="..." ulx="..." uly="..." lrx="..." lry="..."/>
```

Coordinates are expressed in the surface coordinate system. Require
`ulx < lrx` and `uly < lry`, and keep the box within the image bounds when bounds
are known. Zone names are local identifiers, not semantic answers.

Bind every content element using `facs="#zone-id"`. A facsimile link is closed
only when the target ID exists on the correct surface.

## Business Step 3: Encode Metadata Regions Separately

Keep title, attribution, mode, and prose preface distinguishable from music
events. Bibliographic title and attribution belong in `meiHead`; visible source
regions may also appear as typed `annot` elements under a metadata `div` so their
order and facsimile links are retained.

A practical form is:

```xml
<div type="source-metadata">
  <annot type="preface" n="..." facs="#...">...</annot>
</div>
```

Use one element per source unit when character-level order or geometry matters.
Preserve the ledger sequence with `n` or document order. Record a printed column
ending as an explicit boolean attribute rather than inferring it from XML line
breaks.

Do not mix metadata annotations with secondary-sign annotations during later
parsing. Their `type` values and parent contexts must remain unambiguous.

## Business Step 4: Encode Each Music Position as One Unit

Represent each occupied music position as one source-ordered container. For
MEI's mensural-neutral neume vocabulary, `syllable` with `verse/syl` and
`neume/nc` keeps the sung text and notation together without inventing duration:

```xml
<syllable xml:id="..." n="..." type="included" facs="#text-zone">
  <verse><syl>printed text</syl></verse>
  <neume><nc type="suzipu-pitch" label="..." facs="#notation-zone"/></neume>
</syllable>
```

Store the primary class as a controlled label. Store a secondary class as a
typed child annotation of the `nc`, not by concatenating it into the primary
label. If primary evidence is absent, retain an empty or explicitly unresolved
label instead of dropping the whole position.

An alternate MEI grouping is acceptable if it preserves the same one-position
identity, source order, text, primary class, secondary class, and facsimile
links. XML element names alone are not the semantics; the relations must remain
machine-readable.

## Business Step 5: Carry Page, Column, and Editorial State

Write the page assignment on each event or make it unambiguous through its zone's
surface. Insert `pb` at actual source-page transitions. Use `cb` or an explicit
column-break attribute for printed column endings. A line wrap introduced by an
XML formatter is not a source column break.

Represent an excluded or cancelled source position as a status, for example
`type="excluded"` or a controlled `data-excluded` value. Do not remove its text,
sign, geometry, or sequence number. Consumers must be able to distinguish "this
position was present but excluded" from "the transcriber omitted a position."

Keep event numbers stable while revising classification. If a later correction
changes reading order, renumber once and then revalidate every link and boundary.

## Business Step 6: Validate Referential and Structural Closure

Run the generic validator on the authored file:

```bash
python3 /path/to/scripts/validate_mei_facsimile.py score.mei
```

Resolve all errors before handoff. Warnings identify missing recommended context
and should be inspected against the source. A successful XML parse is only the
first check; broken `facs` targets and duplicate IDs still make the document
unusable.

Also perform these ledger-to-MEI reconciliations:

- number of surfaces equals number of physical scans;
- number of metadata source units equals the metadata ledger;
- number and order of music containers equals the music ledger;
- every visible text and notation box has one used zone;
- every primary and secondary value round-trips from the MEI parser;
- page, column-ending, and exclusion states round-trip unchanged.

Record counts before and after encoding. If they differ, repair the missing or
duplicated unit rather than changing the ledger total to match the file.

## Business Step 7: Reopen and Inspect the Delivered Location

Validate the file at its final path, not only a temporary build path. Reparse it
after the last write and resolve each `graphic` target relative to the delivered
MEI. Inspect the first and last event on each page and every boundary event.

The closure pass should leave a small record such as:

```text
surfaces: expected / encoded / linked
metadata units: expected / encoded
music positions: expected / encoded
text zones: expected / referenced
notation zones: expected / referenced
column endings: expected / encoded
excluded positions: expected / encoded
```

This record is an intermediate quality-control artifact; it does not belong in
the MEI unless the delivery request asks for it.

## Completion Contract

The MEI is ready when a generic XML parser can read it, every ID and facsimile
reference closes, both text and notation evidence are traceable to the right
page, source order survives reparsing, editorial status survives, and no timing
or pitch semantics absent from the source have been invented.
