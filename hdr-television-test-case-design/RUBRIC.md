# Evaluation rubric

The scorer evaluates the English editable test-case workbook against the supplied product, project-acceptance and equipment materials. Equivalent professional wording, reordered rows and defensible case splitting or consolidation are accepted.

## Strict score

Strict score is the additive completion of six independent responsibilities less unique source-bound damage. There are no coverage multipliers, exponents, retention floors or score caps.

| Responsibility | Weight | Professional basis |
| --- | ---: | --- |
| Required HDR objective coverage | 20% | The workbook must cover all nine Dolby Vision, HLG and HDR10 Pro objectives named by the issued project requirements. |
| Project acceptance relationships | 20% | P3 D65, skin-tone Delta E, SDR fallback, HLG brightness and switching criteria are release decisions, so their quantities and conditions must remain bound. |
| Evidence and equipment roles | 15% | Product claims, project criteria and generic guidance have different authority; a signal source and calibrated measurement chain must remain separated. |
| Executable procedure | 35% | Preconditions, ordered stimulus/actions, measurement and comparison steps make the design runnable without overwhelming the acceptance decisions. |
| Expected result and decision closure | 8% | Each case must state an observable result that follows from its procedure. |
| English editable workbook contract | 2% | The requested carrier and six fields are required for downstream execution and review. |

The five acceptance relationships receive equal shares within their 20% responsibility because each controls a distinct release decision. The nine objectives use the source-derived shares encoded in `task/tests/validator.py`; broader multi-relation objectives receive 2.5 points and the others 2 points, totalling 20.

Wrong acceptance quantities, unsupported native-format claims, invented durations, peripheral scope and unsupported equipment roles create additive deductions. Repeated wording of one error is charged once per affected row/category; independent errors continue to reduce the score. Missing positive work only loses its own positive credit.

## Lenient score

Lenient is an independent binary usability lens. It is 1 only when:

- the deliverable is an XLSX with all six required fields;
- all nine required objectives are represented;
- all five acceptance relationships use the correct quantity, boundary and condition;
- the HDMI HDR source and calibrated measurement instruments have defensible separated roles, with no unsupported native-format claim;
- the objective-weighted executable-step and expected-result completion are each at least 75%; and
- at least 75% of submitted rows contain operational steps and a checkable expected result.

These are delivery necessities, not a threshold on the strict score. A technically wrong threshold or an all-in-one unsupported instrument fails lenient even if the workbook is well formatted.

## Semantic judge

The HDR10 Pro comparison case uses the source-bound `gpt-5.6-sol` judge for equivalent action and result wording. The package contains one request-bound exact-Golden replay. A changed candidate requires fresh scoring through the six `LLM_JUDGE_*` settings; service or schema failure leaves the trial unmeasured rather than publishing zero.
