# Festival Event Execution Rubric

This rubric describes the program checks and source-grounded factual integrity review.

## Settlement

Let `B` be the sum of independently completed assertion weights and `D` the sum
of deduplicated business-harm deductions. Strict score is
`max(0, B**3 - D)`. Assertions are aggregated once before the common readiness
utility is applied. The cubic utility reflects joint reliability across the
three operational responsibilities represented by the rubric: preparation and
admission, live operation/recovery, and closeout. It is a coarse risk model,
not a hard score cap or a claim that one exponent is uniquely scientific. It
preserves partial credit while preventing a long document containing many
isolated actions from being reported as deployment-ready when several operating
links remain open.

D01-D04 each deduct 0.30 per distinct safety harm; D05 deducts 0.40 for protected
source tampering; D06-D07 deduct 0.25 for source slot/venue contradictions; D08
deducts 0.20 for an infeasible adopted timetable; D09 deducts 0.10 once for other
material factual-integrity errors. Repeated manifestations of one causal harm
are charged once, and D09 excludes D01-D08. Omission earns no positive credit
without an additional omission penalty. Weights sum to one. The machine source
is `task/tests/scoring_params.json`.

Lenient is an independent 0/1 minimum-delivery lens. It requires a readable editable
DOCX, the supplied programs/slots/zones, effective capacity control, child-operation
supervision, controlled stage access, and no adopted D01-D09 harm. It is not a
threshold over strict and is not multiplied into strict.

## Positive Scope

| Owner | Unit | Weight | Complete result | Professional basis | Source-bound evidence |
|---|---|---:|---|---|---|
| P01 | preparation | 0.13 | Setup test, inventory check and transition rehearsal are adopted | Dependencies precede public opening | Proposal equipment/props; checklist preparation duties |
| P02 | staffing | 0.03 | Stage, order and whole-event control have actionable owners | Named action and scope prevent unowned work | Checklist owners and execution duty rows |
| P03 | admission | 0.09 | Slot validation, 40-person stop and truthful overflow action are adopted | Fixed sessions require enforceable admission | Proposal three 40-person sessions |
| P04 | turnaround | 0.08 | Demonstration, participant help and cleanup/tool recovery before the next session are adopted | Ten-minute gaps require real reset | Proposal slot gaps and checklist cleanup |
| P05 | flow | 0.02 | Audience movement and simultaneous-zone staffing are resolved | Plaza and hall operate concurrently | Proposal dual activity; checklist order duty |
| P06 | participant safety | 0.04 | Child tool supervision and pre-opening first-aid readiness are adopted | Hands-on tools create direct participant risk | Proposal public craft; checklist scissors |
| P07 | continuity | 0.02 | Meals and relief preserve live-post coverage | Breaks cannot abandon operating posts | Checklist meal duty and two-zone staffing |
| P08 | weather | 0.06 | A responsible role decides and communicates conditional weather action | Outdoor performance needs a decision chain | Proposal plaza performance |
| P09 | disruption | 0.05 | Performer and instructor absence have executable responses | Named dependencies need recovery paths | Proposal performers and craft instructors |
| P10 | stage safety | 0.03 | Surface, props/cables and public access are controlled | Stage hazards and work-zone access are independent controls | Proposal stage/props; checklist audio equipment |
| P11 | closeout | 0.14 | Stock loss, power/prop return and issue debrief are closed daily | Two-day operation needs asset and issue closure | Checklist material/photo records |
| P12 | media | 0.11 | Selected photos and video/edit review have an adopted handoff | Media output needs selection and release control | Checklist photography/video editing |
| P13 | source bindings | 0.04 | Both dated programs, all fixed craft slots and the two activity zones are preserved | Execution may extend but not rewrite supplied facts | Proposal dates/slots/zones |
| P14 | admission lifecycle | 0.06 | Exact-slot entitlement is redeemed, counted and handed to the teaching team | A copied limit does not prevent reuse or handoff loss | Proposal slots/capacity; reference session flow |
| P15 | accountable closeout | 0.10 | Assets, unresolved issues and selected media each reach an accountable next owner | Collection without reconciliation or recipient leaves the next day exposed | Checklist custody/media duties; reference closeout |

All fifteen areas and thirty-six assertions remain covered. Assertion
weights are explicit, unequal and identical for every model and condition.
P13 is low-value source preservation, not independent professional analysis.

### Public severity policy

Weights are relative operational-risk shares. Full-flow rehearsal, admission
lifecycle, explicit disruption communication and accountable closeout receive
more weight because they connect otherwise isolated actions across people or
stages. Simple source preservation and single local checks retain smaller credit.
Within a conjunctive owner such as P14 or P15, missing one required leg means that
owner is incomplete; the underlying local actions still keep their separate
credit elsewhere. Missing work only loses its positive credit. An affirmatively
wrong or unsafe instruction may also trigger one D-item. Repeated manifestations
of one causal root are charged once; independent harms remain additive.

| Area | Assertion | Weight |
|---|---|---:|
| P01 | setup test | 0.01 |
| P01 | inventory preparation | 0.01 |
| P01 | rehearsal transition | 0.11 |
| P02 | stage control | 0.01 |
| P02 | security | 0.01 |
| P02 | overall control | 0.01 |
| P03 | slot validation | 0.01 |
| P03 | capacity enforcement | 0.01 |
| P03 | overflow alternative | 0.07 |
| P04 | hands on demonstration | 0.04 |
| P04 | assistance | 0.03 |
| P04 | per session reset | 0.01 |
| P05 | audience flow | 0.01 |
| P05 | conditional shared staff | 0.01 |
| P06 | child supervision | 0.03 |
| P06 | first aid provision | 0.01 |
| P07 | meal coordination | 0.01 |
| P07 | continuous coverage | 0.01 |
| P08 | weather authority | 0.01 |
| P08 | weather communication | 0.05 |
| P09 | performer disruption | 0.02 |
| P09 | instructor delay | 0.03 |
| P10 | stage surface | 0.01 |
| P10 | props cables | 0.01 |
| P10 | controlled access | 0.01 |
| P11 | stock loss | 0.01 |
| P11 | power return | 0.12 |
| P11 | debrief | 0.01 |
| P12 | photo handoff | 0.02 |
| P12 | video review | 0.09 |
| P13 | day 19 program | 0.01 |
| P13 | day 20 program | 0.01 |
| P13 | fixed craft slots | 0.01 |
| P13 | two source zones | 0.01 |
| P14 | complete admission lifecycle | 0.06 |
| P15 | accountable closeout handoffs | 0.10 |

## Business Harm

| Item | Adopted error | Points per distinct harm |
|---|---|---:|
| D01 | Explicit unlimited entry or adopted session capacity above 40 | 0.30 |
| D02 | Affirmatively invert a supplied date-to-activity binding | 0.30 |
| D03 | Affirmatively remove adult supervision of children using tools/crafts | 0.30 |
| D04 | Unrestricted free stage access outside organized controlled interaction | 0.30 |
| D05 | Delete, replace, symlink or modify a protected input file | 0.40 |
| D06 | Adopt a craft-class interval contradicting the supplied fixed slots | 0.25 |
| D07 | Adopt a replacement venue or floor contradicting the source zones | 0.25 |
| D08 | Concrete execution timetable contradicts its own required durations | 0.20 |
| D09 | Other material established project facts are fabricated or contradict public sources | 0.10 once for this class |

The deduction bands are likewise coarse: `0.30` for direct participant/access
safety harms, `0.40` for protected-source tampering, `0.25` for fixed slot/venue
rewrites, `0.20` for an infeasible adopted timetable and `0.10` for another
material unsupported fact. They are not universal loss estimates. Omission alone
does not trigger a deduction. Repeated manifestations of one root are deduplicated;
D09 excludes D01-D08 and source-scope review prevents a proposed or pending choice
from being treated as an established wrong fact.

D09 reviews the complete candidate text against the public instruction, event
proposal and materials checklist. It records the asserted fact, why it is material,
candidate locations and relevant source locations. Operational proposals, estimates,
explicit assumptions and pending confirmations are accepted. D01-D08 error classes
are excluded from this review to avoid duplicate deductions. A review failure is
an unavailable measurement, never an inferred business zero. `LLM_JUDGE_MODE=replay`
requires the Golden-only exact-request records under `tests/golden_replay/` and
makes no network calls. A new or changed artifact must miss that binding and use
a fresh live review with `LLM_JUDGE_BASE_URL` and `LLM_JUDGE_API_KEY` from the
verifier environment.

Interpret factual scope in context. Calling the supplied program and its stated
limits or interactions the approved execution baseline does not alone assert a
separate external approval act. A specific completed approval, permit number,
funding receipt or established additional resource still requires support. The
ordinary meanings of plaza and hall support proportionate weather precautions and
indoor operations; they do not establish a particular roof structure, extra room
or certification. Joint planners may be described generically as organizers.
Allocating supplied staff, badges or equipment is an operating choice, subject to
the document's local confirmations. Author-created preparation dates and version
labels do not need to appear in the source files. A statement about information
available to this plan is not automatically a statement about all external data.

Every nonempty initial factual review undergoes a second, uniform adjudication.
That review checks whether each cited candidate unit actually entails the claim,
whether the claim is material, and whether the full local context asserts an
externally established fact rather than an operating choice or open confirmation.
Only confirmed findings trigger D09. Both requests, raw responses and the complete
decision record are retained and bound into offline replay. Empty initial reviews
need no adjudication. Judge failures are unavailable measurements, never zeroes.
An unnamed traditional-craft instructor role, including a generic heritage-teacher
label with the person's identity pending, does not itself claim a named or
formally recognized professional credential. Actual certification, grade,
verified qualification or completed appointment claims still require support.
Original provider findings remain observable when the local source-scope guard
excludes an explicitly generic role finding.
Every remaining proposed finding receives a uniform final source-scope audit
against the complete candidate, public sources and actual XLSX merged ranges.
It separately requires literal entailment, factual scope, materiality and source
support. Source-attributed quantities and derived fixed event totals are factual
assertions even without an outside transaction. Original review responses and
all scope-audit responses remain observable and bound to their exact requests.

General entailment guards protect ordinary food-risk planning, a generic proposed
cleanup acceptance role, qualified allocation of supplied gift types, and adoption
of the supplied ten-minute arrival/ticket workflow. These do not by themselves
establish a confirmed recipe, signed service commitment, extra stock, extra room
or newly approved refusal rule. Explicit procurement/recipe confirmations,
completed agreements, actual fixed-total contradictions, guaranteed over-allocation,
cross-type substitution and added late-arrival refusal do not receive these
exemptions. A merged source category can support a reasonable group assignment;
a blank subordinate owner cell does not alone prove a fabricated commitment.
Any exclusion records its actual finding and reason separately from provider
findings; original provider records are retained.

Proposed extensions needing approval, rejected statements and negated errors do
not incur D01-D07. A concrete complete execution timetable must remain internally
feasible even if marked as proposed: D08 charges consecutive same-team performances
scheduled closer together than the output's own stated program duration, or a
claimed craft turnaround longer than the ten-minute gap while preserving all
supplied fixed craft slots. It does not infer a missing duration or charge an
unselected alternative, an unresolved timing/duration field or an omission.
Repeated mentions and repeated conflicts arising from the same timetable are
one harm. June 20's unstated total performance duration must not be inferred from
June 19, nor does the reference's proposed duration establish a source-fixed fact.
D02 binds an activity within its own date segment rather
than across the following date. D03 binds cancellation to supervision itself:
preserving supervised interaction and prohibiting cancellation are not violations.
Output-only verification explicitly skips D05; workspace verification checks the
private trusted hashes.
D06 does not treat admission, check-in, reset, meals or a concurrent performance
interval as a craft-class interval. D07 exempts conditional weather alternatives
requiring venue approval. Neither charge is an omission penalty.

## Equivalence and Boundaries

Accept tables, narrative, reordered sections, supported synonyms and equivalent
operating plans. Dates, copied headings, capacities or owner labels alone earn no
professional credit. Session capacity must be connected to admission control.
Real counted admissions, a full-session stop on entry, or forty session-specific
tickets that stop when exhausted are equivalent capacity controls. A copied
forty-person limit with execution left for later discussion is insufficient.
Assigned flow staff stopping audience entry and protecting an evacuation or
passage lane perform real crowd management. Assigned live seating assistance
for participants is distinct from a static seating chart or furniture setup.
Questions about whether to clean and recover tools do not adopt a reset duty;
requiring both to be complete before the next session is an equivalent control.
Skill process compliance is reviewed separately from the artifact score.

Overall control accepts an adopted whole-event coordination or operating-decision
duty by its actual owner, including an onsite decision maker, execution lead,
overall duty owner or activity coordinator. Reversed action/scope wording and
explicit opening-conflict checks across both operating points are equivalent.
A row's role may own its duty cells, and an explicit continuation may retain that
owner; another teacher's action or a role mentioned only as the recipient of a
report may not borrow it. A pending person name does not cancel a declared duty.
Local weather work, labels or watchkeeping alone, withdrawn responsibilities
and unadopted quoted duties do not establish whole-event operational control.
The machine predicate is `festival_control.overall_control`.

Named source staff, volunteers or an assigned order-management role may fulfil
the security duty when they perform the required crowd or safety action; a literal
job title meaning security guard is not required. Registering the full group for a
later-session waitlist is an overflow alternative, subject to the stated capacity.
A finished video or edit draft is a video carrier even when the same sentence does
not repeat the word video. Approval of photographs alone remains insufficient.
Performer/team leads and an assigned sound or overall-control role may own a
concrete full-flow rehearsal. Crowd-management duties include organizing order.
Giving a full group accurate information about still-open performance, blessing or
other activities is an alternative; no unavailable place may be promised. Stage
floor checks may use the stage-entry or explicit two-zone context. Controlled
access accepts an explicit performer-only rule, prohibition on public entry or
crossing, and a no-audience constraint inside the performance boundary. A final
video may require confirmation by the designated approver, or execution of its
approval chain before external publication, while the chain's identity is pending.
Asking whether approval is required and a blank approval-status field do not qualify.
An explicit duty to complete publication approval in the same handoff row as a
video deliverable also qualifies; a row containing only an approval-status marker
does not establish that duty.

Stage inspections must bind the inspection action to the surface, props or cables;
a status cell saying "already confirmed" is not an inspection. Restrictions must
bind the restricted audience to entry into a protected working area. A restriction
on touching props is not an entry restriction. Craft assistance needs an adopted
material/tool distribution, seating or guidance action: unissued tools and stopped
distribution are not completed distribution. Photo selection includes equivalent
selection verbs, but pending selection alone earns no credit. Clearing tables and
recovering tools as the prerequisite for the next session is per-session reset;
end-of-event cleaning alone is not.
Prop and cable controls may be stated in separate rows of the same safety table
or the same explicitly named safety/stage section. Each side must independently
adopt inspection or a concrete protective action such as securing props or
fixing/covering cables; merely listing both objects does not qualify. Neither a
cable-only control nor a prop-only control earns this conjunctive assertion.
Closeout power-off and prop storage may similarly compose across subsections of
the same explicitly named daily-closeout chapter. Equipment return alone is not
prop return. Staff/volunteer craft-material distribution or seating assistance
is equivalent to an assistant's action; unrelated ticket distribution is not.
An explicit full-session overflow section may bind its stated full-capacity
condition to an adopted alternative in that section. Preparation and stage
sections may supply their declared context, never a missing business action.
Teaching credit must describe a teaching action or explicit teacher demonstration;
a performance introduction in a different table column does not qualify. A teacher
demonstrating a craft technique or demonstrating alongside roving guidance qualifies;
a label naming a demonstration station does not. Named assigned staff may fulfil
meal coordination or instructor-delay response, and an authorized decision maker
may fulfil weather authority; a literal role label is not required. Video review
must bind the review to video or an edit. An explicit prepublication video-review
obligation qualifies even when the approver identity or publication channel is
pending. Approval of photographs alone, merely confirming the approver identity,
and pending publication-permission fields without a review duty do not qualify. Access
restrictions accept both person-before-ban and ban-before-person syntax.
A table's video/edit product cell may scope an explicit prepublication review
duty in another cell of the same row. A pending approver-name field does not
withdraw that adopted duty; a review-status field alone does not establish it.

Exact unprovided quantities, staffing levels and afternoon timings are not hidden
positive targets. Reasonable proposed choices remain acceptable. Specific existing
rooms, obtained approvals, external commitments and project identity are factual
claims when presented as established and fall within D09. The reference keeps its
original document structure while unsupported arrangements are qualified as pending
confirmation and the activity title follows the public proposal.

## Scorer Limits

All thirty operating assertions P01-P12 use a uniform two-stage source-bound
language review and independent adjudication. Keywords, role names, copied
headings, filenames and candidate declarations cannot directly earn positive
credit. The four P13 date/slot/zone bindings remain closed-set program checks.
The public business contract is `tests/positive_contract.json`. Real provider requests, responses and evidence
IDs bind the exact offline cache. A documented general source-equivalence guard
also accepts an adopted video-approval obligation in its actual handoff row.
The factual model review supplies D09 findings. Neither layer certifies every possible
equivalent expression or external fact. P13 binds programs to dates, checks all
three craft intervals for both days and connects each source zone to its activity.
It rejects the tested negated, rejected and cross-object statements. Independent
review evidence is retained. Neither Gold replay nor artifact scores alone prove
delivery acceptance. Missing assertions earn zero without an additional penalty.
Venue-first parallel descriptions bind each activity to its own venue. A date
mentioned only to compare another day's structure is not an activity assignment.
An interval labelled as having no craft class cannot trigger a wrong-class charge.

Teacher near-distance assistance with children using tools is equivalent to
supervision. Explicit parent, guardian or accompanying-adult supervision or
assistance during children's tool use or craft operation also qualifies.
Adult presence, admission accompaniment or stage escort alone does not qualify.
An explicit mandatory supervision duty during children's craft/tool use may
precede the named adult, teacher or accompanying guardian. The adult's name or
admission-count status need not be settled for that stated duty to qualify.
Mere presence, a pending question whether supervision is required, or mention
of a guardian without an operation-linked supervision duty does not qualify.
First-aid readiness accepts either provision of suitable supplies or an assigned
pre-opening duty to confirm the location, access, equipment or contact path for
existing qualified venue response resources. The resource, responsible role,
pre-opening deadline and concrete readiness action must be connected in the same
statement or operating-table row. Merely asking whether a kit or responder exists,
an unassigned pending field, confirmation after the event, and calling emergency
services only after injury do not fulfil this preparation assertion. This does
not require invented medical appointments, existing resources or clinical advice.
Explicit separate-post coverage or interruptible secondary
duties across simultaneous zones is equivalent to conditional shared staffing;
a bare list of staffing concepts is not an operational plan.

Performer-disruption alternatives inherit the same stated incident condition.
Withdrawing first-aid supplies does not cancel a separately adopted script
adjustment, replacement, pause or escalation. A withdrawn response does not earn
credit merely because its action words remain in the document.

Explicit section headings may supply the weather, rest-period or daily-closeout
context of a duty. They cannot supply a missing action or responsible party.
Power-off and prop-storage actions may occur in separate rows or paragraphs of
the same named closeout section; the verifier records both source locations.
Negated or merely pending inspection, power-off and storage actions cannot
qualify through linked evidence. A cable inspection cannot borrow a prop action
from an unrelated section, or conversely. Entry restrictions include stopping
unrelated people from entering a work area, and prohibiting audience entry onto
the performance surface. An explicitly audience/child interaction section may
supply the subject of an entry restriction, never the prohibition or its area.
Prohibiting simultaneous control of two operating points qualifies as separated
staff coverage. Rest-period handoffs, replacement before leaving and prohibiting
simultaneous departure qualify as uninterrupted post coverage.
Preparation a stated number of days before the event is a pre-event dependency.
Named assigned staff and the sound operator may own closeout duties. Prop return
includes storage in boxes. Stock accounting includes statistics of remaining
materials and losses, and daily debrief includes a short incident-and-handover
summary. A responsibility-assigned daily written summary of problems, incidents
or unresolved actions qualifies without requiring one literal meeting label.
Attendance statistics alone, blank issue fields and a post-event aggregate not
bound to daily closeout do not qualify. Explicitly withholding public access to a protected working area is
equivalent to prohibiting entry, while a restriction on touching props alone is
not. Broadcasting and announcing a weather change to operating posts qualifies
as weather communication.

## Additional Predicate Boundaries

Stage-surface credit requires an inspection, not post-event cleaning. Overflow alternatives require an adopted alternative action; a prohibition on promising an unresolved waitlist is insufficient. A list of activities followed by an unbound list of venues is not an affirmative zone inversion. Performance turnaround is not a craft reset merely because a later clause mentions avoiding craft check-in. Tool accountability by inventory, collection, or return before the next session is accepted as equivalent reset evidence. All 34 assertions and eight concrete additive harm classes are active.

Capacity adoption accepts ordinary copulas such as “上限为80人”; these do not
evade the same D01 participation-limit deduction. Source participation limits
and adopted-capacity boundaries remain authoritative.
