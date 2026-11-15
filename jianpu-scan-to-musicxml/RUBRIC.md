# Evaluation rubric

The task is a diplomatic MEI transcription of the two supplied historical Chinese score pages. Strict scoring is the additive completion of independent source responsibilities. An otherwise parseable submission that invents modern meter, absolute pitch or duration violates the diplomatic-transcription contract and receives zero; this prohibition is evaluated independently from ordinary missing work.

| Responsibility | Weight | Professional basis |
| --- | ---: | --- |
| Heading, attribution, mode and preface | 4% | Establishes the source identity and interpretive context. |
| Sung text fidelity | 8% | Preserves the complete 98-character reading sequence. |
| Primary notation classes | 24% | Measures the main notation at every source position. |
| Six genuine secondary classes | 24% | Measures the real auxiliary signs without letting one rare class dominate the document. |
| Genuine secondary absence | 8% | Prevents invented signs at the 70 unmarked positions. |
| Bare-position source binding | 6% | Measures lyric identity, status, page/boundary, source pairing and regions at unmarked positions. |
| Compound-position source binding | 8% | Measures lyric identity, status, page/boundary, source pairing, regions, primary class and secondary class at the 28 marked positions. |
| Printed page and column boundaries | 5% | Preserves the physical source segmentation. |
| Source-region quality | 4% | Keeps genuine immutable ink support for text and notation. |
| Source pairing | 3% | Binds the two regions to the same declared source position. |
| Physical reading order | 3% | Preserves source succession across both pages. |
| Diplomatic document contract | 3% | Requires genuine source images and closed unique references. The modern-semantics prohibition is enforced independently. |

The recognition and source-binding responsibilities are deliberately separate. A wrong pitch loses primary recognition but does not erase a correctly preserved lyric, page, pairing and crop; the same defect is not charged again through an all-fields gate. Valid MEI aliases, namespaced fields, typed annotations, harmless ID renaming and equivalent XML storage order are accepted.

## Lenient score

Lenient is an independent binary minimum for a usable diplomatic transcription. It requires:

- heading/prose and sung-text completion of at least 90%;
- primary-class completion of at least 80%;
- macro completion across the six real secondary classes of at least 65%;
- secondary absence, inclusion status, page/column boundaries, source pairing and physical order of at least 90% (status at least 95%);
- genuine source-region coverage of at least 80%; and
- a complete diplomatic document contract.

These thresholds operate on independent source responsibilities rather than on the weighted strict score. Missing or invalid MEI earns zero. Golden and valid equivalent encodings earn one.
