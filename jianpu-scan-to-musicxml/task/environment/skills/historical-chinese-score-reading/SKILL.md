---
name: historical-chinese-score-reading
description: Read vertically arranged Chinese song manuscripts with adjacent suzipu notation, preserving text order, primary pitch classes, secondary signs, cancellations, and facsimile regions. Use when a scan must become a diplomatic event record before encoding.
---

# Historical Chinese Score Reading

## Scope and Delivery Boundary

Use this procedure when a historical Chinese page interleaves large lyric or
prose characters with smaller suzipu signs. The goal is a source-bound event
ledger, not a modernized performance edition. This procedure is a separately
mounted runtime aid; it is not evidence about any task's particular pages.

Do not infer modern staff pitch, meter, duration, tempo, or ornament execution
unless the source itself supplies enough evidence. Suzipu primary signs are
relative named pitch classes. Secondary signs are independent graphic marks and
must not be silently converted into durations.

The reusable glyph exemplars are in `references/`. Open those images when a
source glyph is uncertain. They are a controlled visual vocabulary, not a
transcription of the supplied task image.

## Reference Vocabulary

Primary-sign exemplar files and labels:

| Label | Exemplar | Traditional name |
| --- | --- | --- |
| `HE` | `references/he.png` | 合 |
| `SI` | `references/si.png` | 四 |
| `YI` | `references/yi.png` | 一 |
| `SHANG` | `references/shang.png` | 上 |
| `GOU` | `references/gou.png` | 勾 |
| `CHE` | `references/che.png` | 尺 |
| `GONG` | `references/gong.png` | 工 |
| `FAN` | `references/fan.png` | 凡 |
| `LIU` | `references/liu.png` | 六 |
| `WU` | `references/wu.png` | 五 |
| `GAO_WU` | `references/gao_wu.png` | 高五 |

Secondary-sign exemplar files and labels:

| Label | Exemplar | Traditional name |
| --- | --- | --- |
| `DA_DUN` | `references/add_dadun.png` | 大顿 |
| `XIAO_ZHU` | `references/add_xiaozhu.png` | 小住 |
| `DING_ZHU` | `references/add_dingzhu.png` | 丁住 |
| `DA_ZHU` | `references/add_dazhu.png` | 大住 |
| `ZHE` | `references/add_zhe.png` | 折 |
| `YE` | `references/add_ye.png` | 拽 |

A source may omit either layer. Record absence as null; do not force a nearest
class merely to complete a row.

## Business Step 1: Establish the Page and Column Graph

Before recognizing individual characters, determine how the physical pages join.
For each page, locate the outer frame, printed page number if any, title blocks,
and full-height columns. Traditional pages normally read top-to-bottom within a
column and proceed from the rightmost column toward the left, but confirm that
pattern from continuation and punctuation rather than assuming it blindly.

Create a page-column register:

```text
page | column | horizontal span | vertical span | role | successor
```

The successor field is the important part. It prevents a later OCR or crop pass
from sorting all boxes by x-coordinate across different pages. Page order is
resolved first; column order is resolved inside each page; vertical order is
resolved inside each column.

If one text line continues across a page boundary, close the last column on the
first page and open the first reading column on the second. A page transition is
not automatically a musical pause.

## Business Step 2: Separate Document Roles

Classify each full column or block before extracting its contents:

- title or work heading;
- attribution or author information;
- mode heading;
- prose preface;
- music text paired with notation;
- marginal print, folio heading, or unrelated running matter.

Use typography, position, and adjacency together. Large calligraphy does not by
itself imply sung text. A mode label near the title establishes context but is
not a music event. Preface characters form their own diplomatic sequence and
must not be paired with suzipu glyphs just because a nearby music column begins
at the same height.

Persist one role per region and retain its page and bounding box. If a role is
uncertain, mark it uncertain in the working ledger before transcribing; do not
let it silently enter the music stream.

## Business Step 3: Pair Text and Notation Positions

Music is read as paired lanes. The larger lyric characters occupy one vertical
lane and the smaller notation signs occupy an adjacent lane. Build one event row
for each printed music position:

```text
sequence | page | column | lyric | primary | secondary | status |
text_box | notation_box | column_end
```

Pair by vertical overlap and local sequence, not by globally nearest center. A
tall lyric box can overlap more than one small mark; compare its predecessor and
successor before assigning the sign. Keep the two bounding boxes separate.

Do not close gaps by shifting later symbols. A notation position may have a
blank or illegible primary sign, and an excluded or cancelled position still
occupies its place in reading order. The persistent sequence number is the
binding key for all later checks.

Close each column immediately: the lyric count, notation-position count, and
event-row count should reconcile before moving left. A discrepancy triggers a
review of that column, not a global renumbering at the end.

## Business Step 4: Classify the Primary Sign by Shape

For each notation box, compare the complete stroke configuration with the
primary exemplars. Use both positive features and exclusions:

1. Normalize only viewing scale and contrast; do not reshape strokes.
2. Compare the main vertical or hooked skeleton.
3. Check terminal strokes and internal crossings.
4. Distinguish a primary stroke from a detached secondary mark.
5. Reinspect the original page at wider context before committing an ambiguous
   class.

The exemplar filenames are stable labels for structured output. Traditional
names help human review but are not a license to classify by OCR of a vaguely
similar modern character. `WU` and `GAO_WU` are distinct primary classes, not
typographic variants to merge. `None` is preferable to an unsupported guess.

Write the class to the event row as soon as it is resolved and bind it to the
notation box. A later source inspection that changes the box or pairing requires
revisiting the class because its visual evidence has changed.

## Business Step 5: Classify Secondary Signs Independently

After the primary is fixed, inspect the notation box and its immediate surround
for an auxiliary mark. Compare the auxiliary component with the six secondary
exemplars; do not classify the composite silhouette as a new primary glyph.

Record exactly one secondary class when a sign is present and null when absent.
Do not infer a secondary sign from lyric punctuation or paper noise. When a small
mark lies between two primary glyphs, use attachment distance, alignment, and
stroke continuity to decide which event owns it.

Run a second visual pass looking only for secondary signs. They are smaller and
more likely to disappear during a primary-sign pass. Reconcile the number of
non-null rows with the number of visible auxiliaries in each column.

## Business Step 6: Preserve Editorial and Physical Boundaries

Record column endings on the final event of the printed column, not on the first
event of the next column. Record page number on every event rather than trying to
derive it later from sequence ranges.

Cancellation, deletion, or exclusion is a status on the occupied source
position. Preserve the lyric, sign evidence, boxes, and order of that position;
do not delete it from the event stream. Distinguish an editorial cancellation
from damage, ink loss, or an intentionally blank sign.

Capture integer pixel boxes in source-image coordinates:

```text
[left, top, right, bottom]
```

Boxes should enclose the visible text or notation without swallowing a neighbor.
Approximate but honest boxes are preferable to copied full-column rectangles.

## Business Step 7: Reconcile the Diplomatic Ledger

Perform four closure passes before handoff:

1. **Order closure:** read the event text aloud by page and column; verify every
   transition against the scan.
2. **Pair closure:** every event retains one sequence key, a text region, and its
   own notation region when visible.
3. **Class closure:** every visible main sign and auxiliary mark has exactly one
   supported class or an explicit unresolved state.
4. **Boundary closure:** page, column-end, and cancellation flags agree with the
   physical and editorial evidence.

Return to an earlier row whenever a later column reveals that the reading order
or pairing assumption was wrong. The ledger is complete only when counts close
per column and for the whole source, not merely when the last page has been read.

## Handoff Contract

The downstream encoder should receive source-ordered metadata regions and music
events with separate text and notation boxes. It should not need to reinterpret
the scans to discover page order, symbol ownership, primary class, secondary
class, or editorial status. Unresolved evidence remains explicitly unresolved;
it must not be replaced by invented rhythm or modern pitch.
