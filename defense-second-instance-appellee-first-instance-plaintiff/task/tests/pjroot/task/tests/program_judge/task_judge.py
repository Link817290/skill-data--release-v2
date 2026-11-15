#!/usr/bin/env python3
"""Program Judge adapter for the appellee's appellate defence statement task.

Three explicit layers:
  extract_raw()  carrier text only (Markdown lines, or DOCX body paragraphs and table rows)
  normalize()    registered rules N01-N09 turn lines into canonical observations
                 (header/party block, answer body with heading chains, closing block,
                 quoted zones, asserted clauses, gap markers)
  evaluate()     one positive() call per P and one deduction() call per D, using the
                 registered derivation rules R01-R13 for adoption, spans, conflicts and shape.

No model judgement is embedded. Every fact, alias and threshold comes from
rubric-contract.json, relation-matrix.md and the frozen Golden.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from pathlib import Path

from program_judge_runtime import Locator, ProgramJudge, load_contract, sha256
from adversarial_guards import NEG_ZH, blank_withdrawn


PACKAGE_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_CONTRACT = PACKAGE_ROOT / "rubric-contract.json"

# Frozen task constants (relation-matrix.md section 4 lists where each is visible).
CAISSON_RANGE = (Decimal("4400000"), Decimal("4440000"))      # 沉井 about 442万 (appeal petition 一(一))
CEMENT_RANGE = (Decimal("1340000"), Decimal("1360000"))       # 水泥调差 1,350,765 / about 135万 (judgment)
ACCEPTED_PENALTY_STARTS = ("2021-10-14", "2021-10-15")
ACCEPTED_PENALTY_DAYS = {"2021-08-19", "2021-08-20", "2021-10-14", "2021-10-15"}

# R11: procedural acts no material records. Polarity is read on the act, so 上诉人从未发出索赔
# is an affirmative assertion about the appellant's conduct and triggers just as 上诉人已发出索赔
# would. Every surface below has a token count of 0 over the whitespace-stripped materials corpus
# (民事判决书.docx + 被告上诉状（B公司）_去标识版.docx + 民事判决书.docx.ocr.md, 11,251 characters).
UNSUPPORTED_ACTS = (
    ("appraisal_procedure",
     re.compile(r"重新鉴定|鉴定人[^,;。]{0,8}(出庭|质询)|质询[^,;。]{0,6}鉴定人|"
                r"(双方|各方|两造|当事人)[^,;。]{0,10}参与[^,;。]{0,10}(鉴定|勘验|查勘)|"
                r"鉴定(过程|程序|活动)[^,;。]{0,10}(双方|各方|当事人)[^,;。]{0,8}参与|"
                r"参与[^,;。]{0,6}(鉴定(过程|程序|活动)|现场(勘验|查勘))|"
                # the contract's frozen act set includes "the
                # site-signature/construction-record/supervision-file basis of the appraisal".
                # An on-site inspection asserted as a basis of the appraisal is the same act key
                # (勘验/查勘 count 0 over the materials corpus, and the contract already names the
                # surface behind 参与); reading it only in the participation frame measured the
                # frame rather than the act.
                r"现场(勘验|查勘|踏勘)|实地(勘验|查勘|踏勘)|勘验笔录|"
                r"现场签证|施工记录|监理资料|监理记录")),
    ("delay_claim",
     re.compile(r"(发出|发过|提出|提过|提起|递交|提交|主张|作出|送达)[^,;。]{0,10}"
                r"((工期|逾期竣工|逾期)?违约(通知|函|告知书)|(工期|逾期竣工|逾期)?索赔)")),
    # Out-of-evidence certainty. The judgment holds 工程逾期的原因较为复杂，A公司是否需
    # 承担相应的违约金并不明确; neither material attributes the delay to the appellant. A sentence that
    # attributes the delay to the appellant as settled fact (工期延误完全系B公司…所致) invents the
    # factual basis of the delay-responsibility rebuttal. Negated forms (并非/不是 系…) and burden
    # statements (未举证证明工期延误系答辩人原因造成) do not match or are excluded by the guards.
    ("delay_cause_certainty",
     re.compile(r"(工期延误|工程延误|工期拖延|工期延长|逾期竣工|工程逾期|工期逾期|延误工期)[^,;。]{0,12}?"
                r"(完全|全部|均|皆|纯属|纯粹|实际上?)?(?<![不非未无])(系|是|由|因为?|归因于|应?归责于)"
                r"[^,;。]{0,4}?(B公司|上诉人|被答辩人|发包人)[^;。]{0,24}?(所致|造成|导致|引起|原因)")),
    # Fabricated document. Neither material records any letter, confirmation or undertaking
    # issued by the appellant (函件 0, 确认函 0, 确认书 0, 承诺函 0, 书面确认 0, 回函 0, 复函 0 over the
    # corpus); the cement adjustment turns on the appellant's endorsement of the 工程联系单 and its
    # attachment, which this key does not match (联系单 is not in the document list).
    ("written_confirmation",
     re.compile(r"(B公司|上诉人|被答辩人|发包人)[^;。]{0,16}?(出具|发出|签署|签发|发送|致函|作出|递交|提交)"
                r"[^,;。]{0,8}?(书面(函件|确认|承诺|意见|函)|确认函|确认书|承诺函|回函|复函|函件)")),
)
# A conditional or concessive lead (即使工期延误系上诉人原因所致…) hypothesises the fact
# rather than asserting it; applied to these two keys only, so the other act keys keep their behaviour.
ATTRIBUTION_KEYS = ("delay_cause_certainty", "written_confirmation")
HYPOTHETICAL_LEAD = re.compile(r"即使|即便|纵使|纵然|如果|假如|假设|倘若|若|如|是否|除非|能否|可否")
# A negator or evidential hedge inside the match (并非/不当然/未必/难以认定…) denies or
# withholds the attribution instead of asserting it.
ATTRIBUTION_NEGATED = re.compile(r"并非|不是|不当然|并不|未必|不能|无法|难以|没有|未|无")
# R11 modality guard: a deontic or future modal before the act in the same clause makes the
# sentence a statement about what a party may or should do, not an assertion that it happened.
ACT_MODAL = re.compile(r"应当?|可以?|将|会|需|须|宜|建议|有权|得以")
# R11 reporting guard: 未主张其曾申请重新鉴定 asserts what the opposing brief does not claim, which
# is a statement about that filing (checkable against it), not an adopted fact about the world.
# The contract already excludes "reporting it as the appellant's own claim"; this is its negated
# form, and it is one of the lawful rewrites (burden of proof / attribution).
ACT_REPORTED = re.compile(r"(未|没有|并未|从未|亦未|均未)[^,;。]{0,8}?(主张|称|声称|说明|提及|指出|表示|举证|证明|指明)")
# R11 generic-party guard: the contract charges an act asserted "as the appellee's own affirmative
# case". 当事人申请重新鉴定,须具备…等情形 states what the law requires of a party in general and
# asserts no act of anybody, so it is a legal standard rather than a fact about this record.
ACT_GENERIC = re.compile(r"^[^一-鿿]*(当事人|一方当事人|各方当事人|任何一方|申请人)[^。;,]{0,4}$")
# R11 filing-record guard, the negated twin of ACT_REPORTED. 上诉状未援引任何一审未出现的证据材料,
# 亦未申请重新鉴定 and 上诉人…在本案上诉中亦未申请重新鉴定或补充鉴定 say what the opposing filing does
# not contain - the same excluded class as 未主张其曾申请重新鉴定, only with the act verb (申请/提出/
# 递交) in place of the speech verb, which the literal verb list of ACT_REPORTED misses. The guard needs
# both halves: a negator in the act's own clause and a token naming the filing or the record in whose
# scope the non-occurrence is stated. A bare 上诉人从未发出索赔 names no filing and still triggers, which
# is the reading R11 declares (polarity is read on the act).
ACT_NEG = re.compile(r"(不曾|从未|并未|亦未|均未|没有|未|无)[^,;。]{0,6}$")
ACT_FILING = re.compile(r"上诉状|上诉理由|上诉意见|上诉请求|本案上诉|上诉中|上诉期间|二审中|一审中|原审中")
# R11 appellant-objection guard: the materials record that the appellant objected to the appraisal
# and that C公司 then reduced the price (上诉状: 后经上诉人提出异议，C公司减少造价金额约31万元). A
# sentence whose subject is the appellant and that ties its part in the appraisal to that objection
# and reduction, in the same or the next sentence, restates a recorded fact rather than inventing a
# procedural act. The appellee claiming its own participation still triggers.
OBJ_SUBJECT = re.compile(r"(上诉人|B公司|被答辩人)[^,;。]{0,8}$")
OBJ_RECORD = re.compile(r"(提出|提)[^,;。]{0,6}异议")
OBJ_REDUCED = re.compile(r"核减|减少")

# D15: totals the answer derives from figures in the judgment. Each is the sum or difference of
# amounts the judgment states (claimed 21,400,735 + 2,691,720.36 + 225,922; awarded 19,789,007.89 +
# 2,641,873.11 + 225,922; their difference; 88,062,437 - 65,631,556; the appellant's claimed
# reductions of about 722万 off 88,062,437 and the balance after payment; 3,565,379.30 delay damages
# as computed by the appellant). A figure of seven or more integer digits that differs from one of
# them in exactly one digit position is a miscalculated total, not a different quantity (a figure two
# positions away can be another legitimate derivation, e.g. 22,430,881 - 7,310,000 = 15,120,881).
DERIVED_TOTALS = (Decimal("24318377.36"), Decimal("22656803"), Decimal("1661574.36"), Decimal("22430881"),
                  Decimal("88062437"), Decimal("3565379.30"), Decimal("15210881"), Decimal("80842437"))
FIGURE = re.compile(r"(?<![\d.])\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\d.,])\d{7,}(?:\.\d+)?")

# D17: parts every appellate answer to this appeal carries - the title, the appellee's party line,
# an answer on the caisson ground, the bored-pile ground, the delay-price clause 16.2.2, the payment
# clause 14.2, the delay damages, the appraisal, the cement adjustment and a prayer to dismiss the
# appeal. An answer missing one of them has lost a part of the pleading, not only a nuance; each
# missing part is its own damage instance.
REQUIRED_PARTS = (
    ("title", lambda first, text: bool(re.search(r"答辩|答辩意见|二审意见", first))),
    ("party", lambda first, text: bool(re.search(r"(^|\n)(?:答辩人|被上诉人|被答辩人)?[^\n]{0,12}A公司", text))),
    ("dismissal_prayer", lambda first, text: bool(re.search(r"驳回[^\n。]{0,12}上诉", text))),
)

# Golden endorses the first-instance judgment only as qualified - 原审法院对案涉工程
# 价款、逾期付款违约金、工程质保金及逾期支付利息的判决除未考虑水泥价格调差费用约¥1350000…外并无不当 -
# and asks for that part to be corrected (应当在二审中予以改判纠正). An unqualified 维持原判 or
# 一审判决认定事实清楚、适用法律正确 endorses the omission of the cement adjustment as well. An
# endorsement that names its scope (维持原判第一项、第三项; 维持一审判决关于受理费、鉴定费负担的决定) is
# the narrow endorsement the posture calls for and is not charged.
D14_ENDORSE = re.compile(r"维持(原判|一审判决|原审判决|原判决)|"
                         r"(一审|原审)判决[^。;]{0,16}?(认定事实清楚|适用法律[^。;,]{0,10}?正确)|"
                         r"(认定事实清楚|事实认定清楚)[^。;]{0,12}?适用法律[^。;,]{0,10}?正确")
D14_SCOPED = re.compile(r"^[^。;,]{0,12}?(第[一二三四五六七八九十]+项|关于[^。;,]{0,16}?费)")
D14_SCOPED_BEFORE = re.compile(r"(第[一二三四五六七八九十]+项|受理费|鉴定费|费用)[^。;]{0,10}?(的)?(分担|负担)?$")
D14_CARVE = re.compile(r"(水泥|材料)[^。;]{0,14}?(调差|价差|价格调整|价格调差)|¥1350000|135万")

# R12: the appellant identity is frozen by the materials (被告上诉状: 上诉人(一审被告) B公司,
# 被上诉人(一审原告) A公司; the judgment records no appeal by A公司, materials 提起上诉 count 0).
APPEAL_PARTY = re.compile(r"答辩人|被上诉人|被答辩人|A公司|一审原告|原审原告|上诉人|B公司|一审被告|原审被告")
APPELLEE_SIDE = ("答辩人", "被上诉人", "A公司", "一审原告", "原审原告")
CO_ARGUMENT = re.compile(r"(与|和|同|跟|对|向|针对|就|为|替|代)$")
FILE_APPEAL = re.compile(r"(提起|提出|递交|提交|提请)了?(上诉状|上诉)")
APPEAL_NEG = re.compile(r"不|未|没有|没|无|并非|非|放弃")

GAP_MARKERS = [
    "[待补充]", "【待补充】", "[待填写]", "【待填写】", "[待核实]", "【待核实】",
    "[placeholder]", "材料未提供", "未提供", "待补充", "待填写", "待核实", "unspecified", "TBD",
]
GAP_TOKEN = "⟦GAP⟧"
Q = "⟦Q⟧"

TITLE_RE = re.compile(r"^((民事)?(二审|上诉)?(民事)?答辩(状|书|意见书?)|上诉答辩状)(\([^)]{0,8}\))?$")
PARTY_LABEL = re.compile(r"^(被上诉人|被答辩人|上诉人|答辩人|原审原告|原审被告|一审原告|一审被告)(\([^)]{0,30}\))?[：:](.*)$")
PARTY_CONT = re.compile(r"^(法定代表人|负责人|住所地?|地址|住址|委托(诉讼)?代理人|统一社会信用代码|联系(电话|方式)|电话|职务|案号)")

NEG = "不|未|没有|并非|非|无|否认|无需|无须"
PROPER = re.compile(r"并无不当|并不不当|并无不妥|无不妥|无不当|并无错误|正确|合理|适当|恰当|有(事实和法律|事实|法律|合同)?依据|于法有据|"
                    r"应予(以)?(维持|采纳|支持|确认)|应当(予以)?(维持|采纳|支持|确认)|符合(合同|双方(当事人)?)?的?(约定|法律规定|规定)|依据充分|理由充分|"
                    r"(计算|核算|认定|分段节点)?无误|不应(再)?(被)?(推翻|撤销|改判)|与[^。;]{0,24}?(约定|规定|条款)[^。;]{0,6}?一致")
PROPER_SELF = ("并无不当", "并不不当", "并无不妥", "无不妥", "无不当", "并无错误")
PROPER_NEG = re.compile(r"(不|未|没|缺乏|无|非|难以|欠)$")
ADOPT_SELF = re.compile(r"(答辩人|被上诉人|A公司|本方)[^。;]{0,16}?(予以|均|亦|也|并)?(支持|认可|赞同|援引并支持)")
FIRST_INSTANCE = re.compile(r"一审|原审|判决|认定")
# R14 ground-failure families. Three legal moves close an opposing ground in a responsive pleading and
# all three are the appellee adopting its own position: the ground fails on the merits, the ground is
# outside what this instance may decide (the "defer" stance), and the ground cannot stand together with
# the instrument or premise it rests on. Each family is a relation, not a synonym of the others.
GROUND_OBJECT = r"(该|上述|其|本|此|“…”)[^。;,]{0,6}?的?(理由|主张|请求|上诉理由|命题|抗辩|解释|说法|异议)"
GROUND_FAIL_TOKENS = (r"(不能成立|不成立|不能提出|不予采纳|不应采纳|不能采纳|不应(予以)?支持|"
                      r"(没有|无|缺乏)(合同|事实|法律|事实和法律)?依据|所排除|不具备[^。;]{0,8}?条件|无从发生|"
                      r"不属于[^。;]{0,10}?(审理|受理|处理)?范围|不在[^。;]{0,10}?范围(之内|内)?|"
                      r"不能并存|不能同时成立|归于无用|无适用余地|不能作此解释)")
GROUND_FAILS = re.compile(GROUND_OBJECT + r"[^。;]{0,24}?" + GROUND_FAIL_TOKENS)
REJECT_AFTER = re.compile(r"错误|不准确|有误|应(当)?予(以)?纠正|不能成立|不成立|(缺乏|没有|无)[^。;,]{0,8}?依据|"
                          r"不合理|(?<![无并])不当|不妥当|站不住脚|于法无据|应予驳回|予以驳回|依法驳回|不予支持|不应(予以)?支持|不予采纳")
# R02 opponent surfaces. The appellant speaks in an appellate answer through its own filing as well
# as through its name: 上诉状/上诉理由/上诉请求 name the brief, and what the brief says is attributed
# to the appellant exactly as 上诉人称 is. Without them 上诉理由二关于付款条件未成就的主张 and
# 上诉状虽在请求中提出"改判或发回重审" read as the appellee's own assertions.
OPPONENT_SUBJ = r"(?:上诉人|B公司|被答辩人|对方(?:当事人)?|一审被告|原审被告|上诉状|上诉理由|上诉请求|上诉意见)"
ATTRIB = re.compile(OPPONENT_SUBJ +
                    r"(?:(?P<gap2>[^,;。:]{0,24}?)的(上诉)?(理由|主张|观点|说法|抗辩|命题|表述|陈述|计算|论述|看法|定性|请求|异议|意见|结论|断言|判断)"
                    r"|(?P<gap>[^,;。:]{0,14}?)"
                    r"(坚持认为|认为|上诉称|辩称|声称|称|主张|抗辩|所称|所述|质疑|援引|指出|请求|要求|自述|断言|"
                    r"(?:概括|定性|归纳|归)为|"
                    r"提出的?[^,;。]{0,8}(理由|主张|意见|观点|抗辩|命题|说法|表述|陈述|计算|论述|看法|定性)))")
# R02 continuation: 上诉人以X为由,主张Y chains the subject through an adjunct into the clause that
# carries the speech verb. Without it the second clause has no subject of its own and Y reads as
# adopted (04a adoption_status excludes an attributed clause however the attribution is written).
CONTINUE_ATTR = re.compile(r"^(?:并|又|且|亦|还|再|同时|从而|进而|因而|据此|由此|遂|则|故)*"
                           r"(?:据此|由此|进而|因而|从而)?"
                           r"(?:主张|认为|称|上诉称|辩称|声称|请求|要求|提出|断言|质疑|援引)")
OPPONENT_TOKEN = re.compile(OPPONENT_SUBJ)
REBUT = re.compile(r"不能成立|不成立|不予采纳|不予支持|缺乏(事实和法律|事实|法律)?依据|没有(事实和法律|事实|法律)?依据|无(事实和法律|事实|法律)?依据|"
                   r"于法无据|并不能|不能当然|不能|错误|不合理|混为一谈|站不住脚|不应(予以)?(采纳|支持)|不足以|并无(合理)?依据")
CONTRAST = re.compile(r"^(但|但是|然而|可是|却|事实上|实际上|对此|而事实)")
# R02 scope: an attributed clause ends where a new subject takes over. 被答辩人主张…的事实基础,
# 一审未予扣减并无不当 reports the appellant in its first clause and endorses the decision below in
# its second; running the attribution to the end of the sentence deleted the appellee's own
# endorsement and with it the adoption marker R19 looks for.
NEW_SUBJECT = re.compile(r"^(一审|原审|本院|该院|人民法院|二审|法院|答辩人|本方|A公司|被上诉人|一审原告|原审原告|"
                         r"本案|该(主张|理由|请求|异议|意见|条款|认定|判项|处理)|上述(主张|理由|请求))")
BACKREF = re.compile(r"^(该|此|上述|前述)")
# R02 scope, the petition clause: a clause in which the author petitions the court is the author's own
# speech act whoever was named in the clause before it. Running the attribution on through it would let
# 上诉人提出的上诉请求具有事实与法律依据,望合议庭依法撤销原判、发回重审 - an appellee asking for its own
# client's judgment to be revoked - pass with no charge at all, by reading the request clause as
# part of what the appellant says.
REQUEST_FRAME = re.compile(r"^(据此|为此|综上|因此|故)?[,;]?(望|恳请|敬请|谨请|祈请|请求|请|特请)"
                           r"(贵院|贵庭|法院|人民法院|二审法院|合议庭|审判庭)")
CONCESSIVE = re.compile(r"^(尽管|虽然|虽|即使|即便|哪怕|纵使|退一步(讲|说|来说)?|假设|假如|如果|若|倘若|如(?!前|上|下|此))")
CANDIDATE = re.compile(r"(?<![不无])可能|或许|也许|大概|待定|候选|备选|二选一|抑或|要么|倾向于")
QUOTE_HEAD = re.compile(r"^(关于)?(上诉人|B公司|被答辩人|对方)的?(上诉)?(请求|理由|主张|观点)(及|和|与)?(上诉)?(请求|理由|主张)?(概述|摘要|要点|简述|梳理)?:?$")

QUOTE_RE = re.compile(r"“([^”]{13,})”|\"([^\"]{13,})\"|「([^」]{13,})」")
DATE_CN = re.compile(r"(\d{4})年(\d{1,2})月(\d{1,2})日")
MONTH_CN = re.compile(r"(\d{4})年(\d{1,2})月(?!\d)")
DATE_NUM = re.compile(r"(?<![\d.@¥])((?:19|20)\d{2})[-/.](\d{1,2})[-/.](\d{1,2})日?(?![\d.])")
MONTH_NUM = re.compile(r"(?<![\d.@¥§])((?:19|20)\d{2})[-/.](\d{1,2})(?![\d.])")
MONEY = re.compile(r"(?:人民币|RMB)?(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(万元|元)|¥(\d{1,3}(?:,\d{3})+|\d+)(\.\d+)?(?:元)?")
ARTICLE = re.compile(r"第([零〇一二两三四五六七八九十百千0-9]+)条")
TITLE_FOLD = re.compile(r"《[^》]{0,80}》")
CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}

L1_RE = re.compile(r"^[一二三四五六七八九十]+[、.]")
L2_RE = re.compile(r"^\([一二三四五六七八九十]+\)")
L3_RE = re.compile(r"^\d{1,2}[.、](?!\d)")
L4_RE = re.compile(r"^\(\d{1,2}\)")
NUMBERING = re.compile(r"^([一二三四五六七八九十]+[、.]|\([一二三四五六七八九十]+\)|\d{1,2}[.、](?!\d)|\(\d{1,2}\))")
PRICE_KW = re.compile(r"造价|价款|鉴定|沉井|灌注桩|旋喷桩|水泥土|水泥|信息价|组价|计价")
PEN_KW = re.compile(r"违约金|利息|逾期付款|逾期支付|付款条件|工期")


# R18: the frozen Materials corpus, whitespace-stripped. A body line that reproduces a contiguous
# stretch of an input document is a copy of an input, not an assertion the candidate makes, so it
# carries no evidence span (04a section 1: 直接抄材料 must earn positive_earned 0). The threshold is
# the shortest stretch that cannot be an ordinary shared phrase; quoting is unaffected, because a
# quotation of 13 characters or more is already folded by N07 and a quoted paragraph is a quoted
# zone, and a candidate that rewrites the input in its own words keeps every span it earns.
MATERIALS_MIN_COPY = 60
_MATERIALS_CACHE: list[str] = []


def materials_corpus() -> str:
    if not _MATERIALS_CACHE:
        parts = []
        root = PACKAGE_ROOT / "materials"
        for path in sorted(root.glob("*")) if root.is_dir() else []:
            try:
                if path.suffix.lower() == ".docx":
                    import docx
                    from docx.table import Table
                    from docx.text.paragraph import Paragraph

                    document = docx.Document(str(path))
                    parts.extend(par.text for par in document.paragraphs)
                    for table in document.tables:
                        for row in table.rows:
                            parts.extend(cell.text for cell in row.cells)
                else:
                    parts.append(path.read_bytes().decode("utf-8", "ignore"))
            except Exception:
                continue
        _MATERIALS_CACHE.append(re.sub(r"\s+", "", unicodedata.normalize("NFKC", "\n".join(parts))))
    return _MATERIALS_CACHE[0]


def reproduces_materials(clean: str) -> bool:
    """R18: True when the line is a contiguous reproduction of the frozen Materials. Quoted spans are
    removed first (N07): quoting the record with quotation marks is what the deliverable is supposed
    to do, and the reproduction test is about pasting an input as if it were the author's own text."""
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", n07_quotes(clean).replace("“…”", "")))
    if len(text) < MATERIALS_MIN_COPY:
        return False
    corpus = materials_corpus()
    return any(text[i:i + MATERIALS_MIN_COPY] in corpus
               for i in range(0, len(text) - MATERIALS_MIN_COPY + 1, MATERIALS_MIN_COPY))


# ---------------------------------------------------------------------------
# Layer 1: raw carrier extraction
# ---------------------------------------------------------------------------
def extract_raw(artifact: Path) -> dict:
    """Return raw carrier lines with structural locators; never interprets business meaning."""
    raw = {"artifact": artifact, "carrier": None, "records": [], "parse_error": None}
    if not artifact.is_file():
        raw["parse_error"] = "artifact file is missing"
        return raw
    if artifact.suffix.lower() == ".docx":
        raw["carrier"] = "docx"
        try:
            import docx
            from docx.table import Table
            from docx.text.paragraph import Paragraph

            document = docx.Document(str(artifact))
            p_index = t_index = 0
            for child in document.element.body.iterchildren():
                tag = child.tag.rsplit("}", 1)[-1]
                if tag == "p":
                    raw["records"].append({"locator": f"docx:body/p[{p_index}]", "text": blank_withdrawn(Paragraph(child, document).text)})
                    p_index += 1
                elif tag == "tbl":
                    for r, row in enumerate(Table(child, document).rows):
                        cells = [blank_withdrawn(cell.text) for cell in row.cells]
                        raw["records"].append({"locator": f"docx:body/tbl[{t_index}]/tr[{r}]", "text": "|" + "|".join(cells) + "|"})
                    t_index += 1
        except Exception as exc:
            raw["parse_error"] = f"docx parse failure: {type(exc).__name__}"
            raw["records"] = []
        return raw
    raw["carrier"] = "markdown"
    try:
        text = artifact.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        raw["parse_error"] = "artifact is not valid UTF-8"
        return raw
    in_fence = False
    for number, line in enumerate(text.lstrip("﻿").splitlines(), start=1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if not in_fence:
            # A withdrawn / disowned / quote-and-rejected span earns nothing (adversarial_guards)
            raw["records"].append({"locator": f"md:line[{number}]", "text": blank_withdrawn(line)})
    return raw


# ---------------------------------------------------------------------------
# Layer 2: registered normalization rules
# ---------------------------------------------------------------------------
def cn_number(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    total, current = 0, 0
    for char in token:
        if char in CN_DIGITS:
            current = CN_DIGITS[char]
        elif char in CN_UNITS:
            total += (current or 1) * CN_UNITS[char]
            current = 0
        else:
            return None
    return total + current


def money_token(integer: str, fraction: str | None, unit: str | None) -> str:
    try:
        value = Decimal(integer.replace(",", "") + (fraction or ""))
    except InvalidOperation:
        return integer
    if unit == "万元":
        value *= 10000
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "¥" + text


def n01_clean(text: str) -> tuple[str, int, bool]:
    """N01: NFKC fold, drop Markdown decoration and table pipes, remove whitespace.

    Returns the cleaned text, the Markdown heading depth (0 when none) and whether the
    whole line was wrapped in bold markup."""
    text = unicodedata.normalize("NFKC", text)
    for invisible in ("​", "‌", "‍", "﻿", "­"):
        text = text.replace(invisible, "")
    stripped = text.strip()
    depth = 0
    if stripped.startswith("|"):
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", cell or "--") for cell in cells):
            return "", 0, False
        text = ":".join(cell.rstrip(":") for cell in cells if cell)
    m = re.match(r"^\s*(#{1,6})\s*", text)
    if m:
        depth = len(m.group(1))
        text = text[m.end():]
    text = re.sub(r"^\s*>\s*", "", text)
    text = re.sub(r"^\s*[-*+]\s+", "", text)
    bold = bool(re.fullmatch(r"\s*(\*\*|__)[^*_]+(\*\*|__)[:：]?\s*", text))
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return re.sub(r"\s+", "", text), depth, bold


def n06_gap(text: str) -> str:
    """N06: fold every declared gap marker into one gap token."""
    for marker in sorted(GAP_MARKERS, key=len, reverse=True):
        text = text.replace(unicodedata.normalize("NFKC", marker), GAP_TOKEN)
    return re.sub(r"_{3,}|×{2,}|X{3,}", GAP_TOKEN, text)


def n02_n03_n05(text: str) -> str:
    """N03 dates (day and month precision), N02 money, N05 statute articles into canonical tokens."""
    text = DATE_CN.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = MONTH_CN.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}", text)
    text = DATE_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}", text)
    text = MONTH_NUM.sub(lambda m: f"@{int(m.group(1)):04d}-{int(m.group(2)):02d}", text)

    def money(m: re.Match) -> str:
        if m.group(1) is not None:
            return money_token(m.group(1), m.group(2), m.group(3))
        return money_token(m.group(4), m.group(5), None)

    text = MONEY.sub(money, text)

    def article(m: re.Match) -> str:
        number = cn_number(m.group(1))
        return f"§{number}" if number is not None else m.group(0)

    return ARTICLE.sub(article, text)


def n07_quotes(text: str) -> str:
    """N07: quoted propositions (13+ characters) are not the author's own assertion."""
    return QUOTE_RE.sub("“…”", text)


def neg_in(text: str | None) -> bool:
    return bool(text) and re.search(NEG, text) is not None


def r02_asserted(sentence: str) -> str:
    """R02: replace non-adopted clauses (opponent attribution, concessive or conditional
    clauses, candidate sentences) by a quote token; keep rebuttals that follow attribution."""
    if CANDIDATE.search(sentence):
        return Q
    out, attributed, carried = [], False, False
    for clause in re.split(r"(?<=[,:])", sentence):
        body = clause
        if attributed and (CONTRAST.match(body) or NEW_SUBJECT.match(body)
                           or REQUEST_FRAME.match(body)
                           or (BACKREF.match(body) and REBUT.search(body))):
            attributed = False
        if attributed:
            out.append(Q)
            continue
        if CONCESSIVE.match(body):
            carried = bool(OPPONENT_TOKEN.search(body))
            out.append(Q)
            continue
        # R02 continuation: the opponent named in the previous clause governs a speech verb that
        # opens this one (上诉人以结算存在争议为由,主张付款条件始终未成就).
        if carried and not CONTRAST.match(body):
            c = CONTINUE_ATTR.match(body)
            if c:
                rebuttals = list(REBUT.finditer(body, c.end()))
                if rebuttals:
                    out.append(Q + body[rebuttals[-1].start():])
                else:
                    out.append(Q)
                    attributed = True
                carried = False
                continue
        m = ATTRIB.search(body)
        # the negation guard belongs to the verb branch (上诉人未主张X does not attribute X to the
        # appellant); a negation inside the possessive noun phrase is part of the attributed content
        # (上诉人关于沉井系措施项目而非实体工程的论述)
        if m and not (m.group("gap") is not None and neg_in(m.group("gap"))) \
                and not body[:m.start()].endswith("答辩"):
            rebuttals = list(REBUT.finditer(body, m.end()))
            r = rebuttals[-1] if rebuttals else None
            if r:
                body = body[:m.start()] + Q + body[r.start():]
            else:
                body = body[:m.start()] + Q
                attributed = True
            carried = False
        else:
            carried = bool(OPPONENT_TOKEN.search(body)) and not REBUT.search(body)
        out.append(body)
    return "".join(out)


def split_sentences(text: str) -> list[str]:
    return [part for part in re.split(r"[。;!?]", text) if part]


def raw_token_soup(raw_text: str) -> bool:
    """R01: a raw line made of eight or more whitespace- or comma-separated short tokens is keyword soup.

    Whitespace next to digits or ASCII punctuation is collapsed first so spaced numbers
    such as `2021 年 8 月` stay one legitimate phrase."""
    text = unicodedata.normalize("NFKC", raw_text).replace("**", "").strip()
    text = re.sub(r"^\s*(#{1,6}|[-*+>]|\d+[.)])\s+", "", text)
    text = re.sub(r"\s*([\d.,:;()%/])\s*", r"\1", text)
    fragments = [frag for frag in re.split(r"[\s、,，]+", text) if frag]
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 8 and len(short) >= 0.7 * len(fragments)


def is_list_spray(text: str) -> bool:
    """R01: six or more short enumerated fragments are a keyword list, not a proposition."""
    fragments = re.split(r"[、,]", text)
    short = [frag for frag in fragments if len(frag) <= 8]
    return len(fragments) >= 6 and len(short) >= 0.7 * len(fragments)


def too_dense(text: str) -> bool:
    """R01: one sentence asserting more than four amounts or four dates is candidate spraying."""
    return len(set(re.findall(r"¥[\d.]+", text))) > 4 or len(set(re.findall(r"@\d{4}-\d{2}(?:-\d{2})?", text))) > 4


def heading_level(clean: str, depth: int, bold: bool) -> int:
    """N04: numbered or Markdown heading lines resolve to a level; body sentences do not."""
    if TITLE_RE.fullmatch(clean):
        return 0
    numbered = 1 if L1_RE.match(clean) else 2 if L2_RE.match(clean) else 3 if L3_RE.match(clean) else 4 if L4_RE.match(clean) else 0
    if depth:
        return numbered or min(depth, 4)
    if bold and len(clean) <= 80:
        return numbered or 3
    if numbered and (not clean.endswith(("。", ";")) or len(clean) <= 40):
        return numbered
    return 0


class Doc:
    """Normalized answer brief: header/party lines, body lines with heading chains, closing lines."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.artifact = str(raw["artifact"])
        self.lines: list[dict] = []
        for record in raw["records"]:
            clean, depth, bold = n01_clean(record["text"])
            if not clean:
                continue
            canon = n02_n03_n05(n06_gap(clean))
            self.lines.append({"locator": record["locator"], "raw": record["text"], "clean": clean,
                               "canon": canon, "quoted": n07_quotes(canon), "soup": raw_token_soup(record["text"]),
                               "copied": reproduces_materials(clean),
                               "level": heading_level(clean, depth, bold)})
        zone = "header"
        chain: dict[int, dict] = {}
        for line in self.lines:
            clean = line["clean"]
            if zone != "closing" and clean.startswith("此致"):
                zone = "closing"
            if zone == "header":
                if TITLE_RE.fullmatch(clean) or PARTY_LABEL.match(clean) or PARTY_CONT.match(clean):
                    line["zone"] = "header"
                    continue
                zone = "body"
            line["zone"] = zone
            if zone != "body":
                continue
            level = line["level"]
            if level:
                chain = {k: v for k, v in chain.items() if k < level}
                chain[level] = line
            line["chain"] = [chain[k] for k in sorted(chain) if chain[k] is not line]
            heads = line["chain"] + ([line] if level else [])
            line["quoted_zone"] = any(QUOTE_HEAD.match(NUMBERING.sub("", h["clean"])) for h in heads)
            line["l1"] = chain.get(1)
            sentences = []
            for sentence in split_sentences(line["quoted"]):
                spray = line["soup"] or is_list_spray(sentence) or too_dense(sentence)
                full = r02_asserted(sentence)
                folded = r02_asserted(TITLE_FOLD.sub("《》", sentence))
                sentences.append({"canon": sentence, "a_full": Q if spray else full, "a": Q if spray else folded,
                                  "c": TITLE_FOLD.sub("《》", sentence),
                                  "lctx": (line["chain"][-1]["canon"] if line["chain"] else "") + line["canon"],
                                  "line_canon": line["canon"],
                                  # R14 scope: the adoption marker of a local span may sit in the
                                  # line's own lead-in or in the heading the line sits under
                                  # (答辩人支持一审关于…的以下具体认定：…), not only inside the
                                  # sentence that carries the object. Read through R02 so an
                                  # attributed lead-in still cannot adopt anything.
                                  "la": Q if spray else r02_asserted(
                                      TITLE_FOLD.sub("《》",
                                          (line["chain"][-1]["canon"] if line["chain"] else "") + line["canon"]))})
            line["sentences"] = sentences
        self.body = [l for l in self.lines if l.get("zone") == "body"]
        self.header = [l for l in self.lines if l.get("zone") == "header"]
        self.closing = [l for l in self.lines if l.get("zone") == "closing"]
        self.body_state = "identified" if self.body else "confirmed_missing"
        self.spans = self._spans()

    def _section_has_body(self, index: int) -> bool:
        """R13: the section a heading opens, down to the next heading of the same or a higher
        level, contains at least one non-heading body line."""
        level = self.body[index]["level"]
        for line in self.body[index + 1:]:
            if line["level"]:
                if line["level"] <= level:
                    return False
                continue
            return True
        return False

    def _spans(self) -> list[dict]:
        """R03: local evidence spans = one body line with its heading chain, or one lowest-level
        heading block (heading plus following paragraphs until the next heading) of at most 1600 chars.
        R13: a heading line is evidence only read together with the body of its own section, so an
        isolated heading, or one whose section holds only further headings, yields no span."""
        spans = []
        for index, line in enumerate(self.body):
            if line["level"] and not self._section_has_body(index):
                continue
            if line["copied"]:
                continue
            if not line["quoted_zone"] and len(line["quoted"]) <= 900:
                spans.append({"lines": [line], "chain": line["chain"]})
        current = None
        for line in self.body:
            if line["level"]:
                if current and len(current["lines"]) > 1:
                    spans.append(current)
                current = None if line["quoted_zone"] else {"lines": [line], "chain": line["chain"]}
            elif current is not None and not line["quoted_zone"] and not line["copied"]:
                current["lines"].append(line)
        if current and len(current["lines"]) > 1:
            spans.append(current)
        result = []
        for span in spans:
            if len(span["lines"]) > 1 and sum(len(l["quoted"]) for l in span["lines"]) > 1600:
                continue
            span["sentences"] = [s for l in span["lines"] for s in l["sentences"]]
            span["ctx"] = "".join(h["canon"] for h in span["chain"]) + "".join(l["canon"] for l in span["lines"])
            result.append(span)
        return result

    def loc(self, line: dict, object_key: str, field: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:{line['locator']}", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path=line["locator"],
                       object_key=object_key, field=field, observed=line["raw"][:400])

    def canon_loc(self, source: Locator, line: dict, rule: str) -> Locator:
        return Locator(locator_id=source.locator_id + ":canon", artifact_path=self.artifact,
                       container_type=source.container_type, container_path=source.container_path,
                       object_key=source.object_key, field=source.field + ".canonical",
                       observed=line["quoted"][:400], evidence_origin="lossless_canonicalized",
                       source_locator_ids=(source.locator_id,), normalization_rule_id=rule)

    def section_loc(self, object_key: str, prefix: str) -> Locator:
        return Locator(locator_id=f"{prefix}:section:body", artifact_path=self.artifact,
                       container_type=self.raw["carrier"] or "unknown", container_path="section:body",
                       object_key=object_key, field="section_state", observed=self.body_state)


def observe_lines(judge: ProgramJudge, doc: Doc, obs_id: str, lines: list[dict], object_key: str,
                  field: str, rule: str) -> str:
    evidence: list[Locator] = []
    seen: set[str] = set()
    for line in lines:
        if line["locator"] in seen:
            continue
        seen.add(line["locator"])
        source = doc.loc(line, object_key, field, obs_id)
        evidence.extend([source, doc.canon_loc(source, line, rule)])
    return judge.observe(obs_id, "identified", evidence)


def normalize(raw_registry: dict, judge: ProgramJudge) -> dict:
    """Register carrier-independent observations; the runtime owns their states."""
    if raw_registry.get("parse_error"):
        locator = Locator("parse:artifact", str(raw_registry["artifact"]), raw_registry.get("carrier") or "unknown",
                          "artifact", "defence_statement", "carrier", raw_registry["parse_error"])
        judge.observe("obs.parse_failure", "parse_failure", [locator])
        return {"parse_failure": True}
    doc = Doc(raw_registry)
    for name, lines in (("header", doc.header), ("body", doc.body), ("closing", doc.closing)):
        if lines:
            observe_lines(judge, doc, f"obs.scan.{name}", lines, f"section.{name}", "section_text", "N01")
        else:
            judge.observe(f"obs.scan.{name}", "confirmed_missing", [Locator(
                f"obs.scan.{name}:section", doc.artifact, doc.raw["carrier"] or "unknown", f"section:{name}",
                f"section.{name}", "section_state", "confirmed_missing")])
    return {"parse_failure": False, "doc": doc}


# ---------------------------------------------------------------------------
# Layer 3: P/D decisions
# ---------------------------------------------------------------------------
def iter_matches(pattern: re.Pattern, text: str):
    """R04: overlapping candidate matches, restarting one character after each match start,
    so a rejected early candidate never hides a later adopted one."""
    pos = 0
    while pos <= len(text):
        m = pattern.search(text, pos)
        if not m:
            return
        yield m
        pos = m.start() + 1


def gap_clean(m: re.Match) -> bool:
    gd = m.groupdict()
    return not neg_in(gd.get("g")) and not neg_in(gd.get("h"))


def span_adopts(span) -> bool:
    """R19: the appellee's adopted stance on a finding of the decision below is established by an R05 or
    R14 marker anywhere in the local span. A span with no rejection in it is not read as adoption:
    that would let a keyword-sprayed or negated answer earn P12 or P11. R05 includes the short form of
    an endorsement (无误 beside 并无错误) and the appellate form 该认定不应再被推翻."""
    return any(has_proper(s["a"]) or has_proper(s["la"]) for s in span["sentences"])


def has_proper(text: str) -> bool:
    """R05 + R14: the appellee adopts the position. R05 is an endorsement token that is not negated
    just before it. R14 adds the two adoption forms an appellate answer uses without any evaluative
    adjective: an adoption verb bound to the appellee and pointing at the decision below
    (答辩人支持一审关于…的认定), and the operative conclusion that the named opposing ground fails
    (该项主张…不能提出). Both are the appellee's own adopted stance, which is what the contract's
    adoption_status asks for; requiring 并无不当 measures agreement with the Golden's wording."""
    for m in PROPER.finditer(text):
        if m.group(0) in PROPER_SELF:
            return True
        if not PROPER_NEG.search(text[max(0, m.start() - 2):m.start()]):
            return True
    if FIRST_INSTANCE.search(text):
        for m in ADOPT_SELF.finditer(text):
            if not PROPER_NEG.search(text[max(0, m.start() - 2):m.start()]):
                return True
    return bool(GROUND_FAILS.search(text))


def rejected_after(text: str, position: int) -> bool:
    """R04: a rejection token in the rest of the matched clause or the next clause (at most 30 characters)."""
    window = ",".join(text[position:].split(",")[:2])[:30]
    for m in REJECT_AFTER.finditer(window):
        m_start = m.start()
        if not re.search(r"(并无|没有|无|不存在|并非|不是)$", window[max(0, m_start - 3):m_start]):
            return True
    return False


def credit(judge, doc, item_id, fraction, comparison, reason, lines, object_key, rule="N01"):
    obs = f"obs.{item_id}"
    if comparison == "missing":
        judge.observe(obs, "confirmed_missing", [doc.section_loc(object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "missing")
        return
    if comparison == "ambiguous":
        evidence = [doc.loc(line, object_key, "candidate_span", obs) for line in {l["locator"]: l for l in lines}.values()]
        judge.observe(obs, "ambiguous", evidence or [doc.section_loc(object_key, obs)])
        judge.positive(item_id, 0.0, obs, reason, "different")
        return
    observe_lines(judge, doc, obs, lines, object_key, "proposition_span", rule)
    judge.positive(item_id, fraction, obs, reason, comparison)


def decide_positive(judge, doc, item_id, object_key, scorer, full_reason, partial_reason, conflict=None, rule="N01"):
    """R06: score every local span; the best full or partial span wins; a span that also adopts
    the contrary proposition cannot earn credit, and only such spans make the item ambiguous."""
    if doc.body_state != "identified":
        return credit(judge, doc, item_id, 0, "missing", "answer body not found", [], object_key)
    best, best_span, conflicts = 0.0, None, []
    for span in doc.spans:
        fraction = scorer(span)
        if fraction and conflict and conflict(span):
            conflicts.append(span)
            continue
        if fraction > best:
            best, best_span = fraction, span
    if conflicts and best == 0:
        lines = [l for s in conflicts for l in s["lines"]]
        return credit(judge, doc, item_id, 0, "ambiguous", "proposition asserted together with its contrary in one span", lines, object_key)
    if best == 1.0:
        comparison = "exact" if judge.positives[item_id]["comparison_mode"] == "exact" else "equivalent"
        return credit(judge, doc, item_id, 1.0, comparison, full_reason, best_span["lines"], object_key, rule)
    if best > 0:
        return credit(judge, doc, item_id, best, "partial", partial_reason, best_span["lines"], object_key, rule)
    return credit(judge, doc, item_id, 0, "missing", "proposition not asserted in any local span", [], object_key)


# ---- D01 concessions on the price grounds (also used as P conflict tests) -----------------
D01_PATTERNS = {
    "caisson": [re.compile(r"沉井(?P<g>[^。;]{0,20}?)(属于|系|是|为|构成|仅为|只是)(?P<h>[^。;]{0,24}?)措施(项目|费|工程)"),
                re.compile(r"沉井[^。;]{0,20}?(不应|不能|不得|无需|不予)[^。;]{0,6}?(重新组价|重新计价|调整单价|调价)"),
                re.compile(r"沉井[^。;]{0,20}?(不属于|并非|不构成)[^。;]{0,6}?(工程|设计)?变更")],
    "bored_pile": [re.compile(r"(灌注桩|旋挖|成孔|施工机械|钻机)(?P<g>[^。;]{0,30}?)(属于|系)(?P<h>[^。;]{0,10}?)(承包人|A公司|答辩人|被上诉人)的?(自身)?的?原因"),
                   re.compile(r"(灌注桩|旋挖)[^。;]{0,30}?(不属于|并非|不构成)[^。;]{0,6}?(工程|设计)?变更")],
    "cement_soil": [re.compile(r"(水泥土|旋喷桩|搅拌桩)(?P<g>[^。;]{0,30}?)(应|应当)(?P<h>[^。;]{0,6}?)按[^。;]{0,8}?(原)?投标的?(综合)?单价(结算|计价|计算)"),
                    re.compile(r"(水泥土|旋喷桩|搅拌桩)[^。;]{0,20}?(不应|不能|不得|无需)[^。;]{0,6}?(重新组价|重新计价)")],
    "cement_adjustment": [re.compile(r"水泥[^。;]{0,20}?(不应|不能|不予|无权|不得)[^。;]{0,6}?(调差|调价|调整|计入|增加)")],
    "appraisal": [re.compile(r"鉴定意见[^。;]{0,15}?(明显)?(缺乏依据|不能作为|不应(予以)?采纳|不予采纳)")],
}


NEGATED_FRAME = re.compile(r"(不能|不应|不得|并非|不是|无法|不可)(因为|以|据此|仅凭|仅因)?[^。;]{0,40}?(认定|认为|得出|推定|主张)[^。;,]{0,6}$")


def concession_hits(sentence_a: str, objects) -> list[str]:
    hits = []
    for obj in objects:
        for pattern in D01_PATTERNS[obj]:
            matched = False
            for m in iter_matches(pattern, sentence_a):
                if not gap_clean(m) or rejected_after(sentence_a, m.end()):
                    continue
                if reported_ground(sentence_a, m.start(), m.end()):
                    continue
                if NEGATED_FRAME.search(sentence_a[:m.start()]):
                    continue
                matched = True
                break
            if matched:
                hits.append(obj)
                break
    return hits


def span_concedes(objects):
    return lambda span: any(concession_hits(s["a"], objects) for s in span["sentences"])


D02_PATTERN = re.compile(r"付款条件[^。;]{0,6}?(尚未|未|没有|并未)成就|(B公司|上诉人|发包人|被答辩人)[^。;]{0,10}?(不构成|不存在)[^。;]{0,4}?逾期(付款|支付)|"
                         r"(B公司|上诉人|发包人|被答辩人)[^。;]{0,10}?(无需|无须|不应|不需要|不必)[^。;]{0,6}?(支付|承担)[^。;]{0,10}?违约金|违约金[^。;]{0,10}?(不应|不能)[^。;]{0,4}?(予以)?支持")
# the deontic head carries the polarity: 工期延误违约金不应在本案中抵扣 says the opposite of
# 工期延误违约金应予抵扣, so 应/应当 is read only when it is not itself negated.
D03_PATTERN = re.compile(r"(A公司|答辩人|被上诉人|承包人)[^。;]{0,15}?(?<![不未无非])(应当?|需|须)[^。;]{0,8}?(承担|支付)[^。;]{0,15}?(工期(延误)?|逾期竣工)的?违约金|"
                         r"(工期(延误)?违约金|逾期竣工违约金)[^。;]{0,20}?(?<![不未无非])应当?[^。;]{0,6}?(从|自)?[^。;]{0,10}?(抵扣|扣减|抵销|抵减)")


# R17: 以…为由 / 以…为前提 / 以…为基础 all state a ground or premise somebody else offers, which
# adoption_status excludes exactly as it excludes an attributed clause.
REASON_ADJUNCT = re.compile(r"(以|凭|据)[^。;]{0,40}?为(由|据|依据|理由|依托|前提|基础|条件)")
# R17: 是否/能否/可否/有无 turn the clause into the question the answer is about to answer, not a
# proposition it adopts (案涉沉井是否属于基坑支护措施项目——而这正是上诉人尚未证明的前提);
# 究竟A还是B is the same disjunctive question written without 是否.
INTERROGATIVE = re.compile(r"是否|能否|可否|有无|抑或|是不是|究竟|还是")
# R17: 上诉人主张X、依Y条 introduces the appellant's ground with an enumerating comma; the whole
# enumeration is the ground, not the appellee's own proposition.
OPPONENT_GROUND = re.compile(OPPONENT_SUBJ + r"[^,;。:]{0,10}?(主张|称|认为|上诉称|辩称|所称|援引|提出|请求|要求|自述|断言|(?:概括|定性|归纳|归)为)")
# R17 reported-claim noun phrase: the proposition is the *content* of a claim the other side makes,
# named either before it (上诉理由一的整体主张是"鉴定意见明显缺乏依据") or after it
# (其关于工期延误违约金应予抵扣的请求). Both report a claim; neither adopts it.
REPORTED_BEFORE = re.compile(r"(主张|称|认为|请求|要求|断言|概括|归纳|指称|所称|表述|陈述|异议|观点|意见)(是|为|即|:)?[\"'“”「『]?$")
REPORTED_AFTER = re.compile(r"^[\"'“”」』]?的?[^。;,]{0,6}?(主张|请求|理由|异议|意见|观点|说法|命题|断言|结论|陈述|表述|抗辩|诉请)")
# R17 burden-of-proof frame: a proposition the other side must prove, or failed to prove, is not a
# proposition the answer adopts (该主张要成立,须先证明案涉沉井…属于措施项目).
PROOF_FRAME = re.compile(r"(须|应当?|需|要|未|没有|并未|亦未|均未|从未|不能|无法|足以|不足以|用以|以|欲|拟)"
                         r"[^。;,]{0,6}?(证明|举证|论证|说明|表明|证实|印证)[^。;,]{0,8}$")
# R17 negated head: 既未确认X / 而非认定X / "双方存在争议"不构成X assert the contrary of X.
NEG_HEAD = re.compile(r"(不|未|没有|并未|从未|亦未|均未|无|非|而非|难以|不能|不应|不得|无法|不构成|不等于|"
                      r"不意味着|不足以|不属于|不在)[^。;,]{0,10}?"
                      r"(认定|认为|确认|得出|推定|主张|构成|意味着|等于|表明|证明|说明|支持|采纳|成立)[^。;,]{0,8}$")


def reported_ground(text: str, start: int, end: int) -> bool:
    """R17: a deduction's error proposition must be complete inside one clause and must not sit in a
    reported-ground adjunct. Crossing a clause separator makes the match an accidental adjacency of
    two different clauses (…推翻鉴定意见的证据，仅以"明显缺乏依据"…); an 以…为由 adjunct states the
    ground somebody else offers (…仅以鉴定意见不应采纳为由要求改变负担主体), which 04a's
    adoption_status excludes just as it excludes an attributed clause."""
    # 、 enumerates list items, so a match that spans one is the same accidental adjacency a comma is
    # (鉴定人不具备相应资格、鉴定程序严重违法、鉴定意见明显依据不足 is one statutory enumeration).
    if re.search(r"[,;:、]", text[start:end]):
        return True
    if any(m.start() <= start and end <= m.end() for m in REASON_ADJUNCT.finditer(text)):
        return True
    # the attribution has to be in the match's own clause: an opponent verb three clauses earlier does
    # not make the rest of the sentence the opponent's.
    clause_start = max([text.rfind(ch, 0, start) for ch in ",;:"] + [-1]) + 1
    clause_end = min([p for p in (text.find(ch, end) for ch in ",;:") if p >= 0] + [len(text)])
    if INTERROGATIVE.search(text[clause_start:clause_end]):
        return True
    head = text[clause_start:start]
    if REPORTED_BEFORE.search(head) or PROOF_FRAME.search(head) or NEG_HEAD.search(head):
        return True
    # a bracketed enumeration is a gloss listing somebody else's items (the statutory grounds for a
    # re-appraisal, say), not a predicate the sentence asserts.
    for m in re.finditer(r"\(([^()]{0,200})\)", text):
        if m.start() < start and end <= m.end() and "、" in m.group(1):
            return True
    if REPORTED_AFTER.match(text[end:clause_end]):
        return True
    return any(m.end() <= start for m in OPPONENT_GROUND.finditer(text[clause_start:start + 1]))


def pattern_adopted(pattern: re.Pattern, a: str) -> bool:
    return any(not rejected_after(a, m.end()) and not reported_ground(a, m.start(), m.end())
               and not NEGATED_FRAME.search(a[:m.start()])
               for m in pattern.finditer(a))


def span_concedes_penalty(span) -> bool:
    return any(pattern_adopted(D02_PATTERN, s["a"]) for s in span["sentences"])


def span_concedes_delay(span) -> bool:
    return any(pattern_adopted(D03_PATTERN, s["a"]) for s in span["sentences"])


# ---- P02 沉井 is a variation, re-pricing (about 442万) proper ------------------------------
P02_CHANGE = re.compile(r"沉井(?P<g>[^。;]{0,40}?)(属于|系|构成|是|为|认定为)(?P<h>[^。;]{0,10}?)(工程变更|设计变更|变更工程|新增工程|新增项目|合同外(新增)?的?(工程|项目))")
REPRICE = re.compile(r"重新组价|重新计价|重新确定(综合)?单价|据实(结算|计价|计算)|按实(结算|计价|计算)|增加(工程)?造价|调整(综合)?单价|¥44[0-4]\d{4}(?!\d)")


def eval_p02(judge, doc):
    def score(span):
        change = proper = False
        for s in span["sentences"]:
            a = s["a"]
            if any(gap_clean(m) for m in iter_matches(P02_CHANGE, a)):
                change = True
            if "沉井" in a and REPRICE.search(a) and (has_proper(a) or has_proper(s["la"])):
                proper = True
        return 1.0 if change and proper else 0.5 if change else 0.0
    decide_positive(judge, doc, "P02", "price.caisson_variation", score,
                    "沉井 is a variation and its re-pricing by the appraisal is proper",
                    "沉井 qualified as a variation without endorsing the re-pricing",
                    span_concedes(("caisson",)))


# ---- P07 information-price period 2017-11 to 2020-10 proper -------------------------------
def eval_p07(judge, doc):
    def score(span):
        best = 0.0
        for s in span["sentences"]:
            a = s["a"]
            if "信息价" not in a or not (has_proper(a) or has_proper(s["la"])):
                continue
            if "@2017-11" in a and "@2020-10" in a:
                best = 1.0
            elif re.search(r"实际施工期间|施工期间|开工至竣工|开竣工(期间|时间)", a):
                best = max(best, 0.5)
        return best
    decide_positive(judge, doc, "P07", "price.information_price_period", score,
                    "information prices over 2017-11 to 2020-10 are properly used",
                    "actual construction period endorsed without the months")


# ---- R16 shared normalized fragments -----------------------------------------------------
# The discriminating power of each item stays in its object and scope guards; these fragments only
# say "the record carries no evidence of it" and "no counterclaim was filed" in the ways Chinese
# pleadings actually write them, instead of listing the verbs Golden and the first rollout happened
# to use (04a section 2: wording-open items must not lose credit to a lawful synonym).
NO_EVIDENCE_SRC = (r"(未|没有|并未|从未|均未|亦未)[^。;]{0,12}?(提供|提交|举示|出示|举出|拿出|列出|给出|指明)[^。;]{0,12}?证据|"
                   r"(未|没有|并未|从未|均未|亦未)[^。;]{0,8}?(能)?举证(证明)?|(未|没有)[^。;]{0,8}?尽到?[^。;]{0,6}?举证责任")
NO_COUNTERCLAIM_SRC = (r"(未|没有|并未|从未|均未|亦未)[^。;]{0,12}?(提起|提出)[^。;]{0,12}?反诉|"
                       r"(未|没有|并未|从未|均未|亦未)[^。;]{0,12}?(以|通过|采取)?反诉(的?(形式|方式|请求))?[^。;]{0,10}?(提出|提起|主张)")

# ---- P08 delay-based bar on price adjustment unsupported ----------------------------------
P08_PRED = re.compile(NO_EVIDENCE_SRC + r"|" + NO_COUNTERCLAIM_SRC + r"|"
                      r"(不能|无法|不足以|未能|未(能)?举证|没有举证|并未举证|未提供证据)证明[^。;]{0,25}?(承包人|A公司|答辩人|被上诉人)[^。;]{0,10}?(原因|责任|承担)|"
                      r"(延误|逾期)[^。;]{0,15}?(并非|不是|非)[^。;]{0,8}?(承包人|A公司|答辩人|被上诉人)的?(自身)?的?原因")


# R16 (U17, cannot-prove limb): the contract's accepted set includes 不能证明系承包人原因, and an
# appellate answer states it about the clause's own premise - 16.2.2(5) 的适用前提是工期延误责任由
# 承包人承担,该前提未经查明/并未成立/不具备适用条件. Object, relation and polarity are Golden's; only
# the noun the negation attaches to differs, so requiring the appellant to be the grammatical subject
# of the failed proof measured wording rather than the proposition.
P08_PREMISE = re.compile(r"(前提|条件|要件)[^,;。]{0,14}?(并未|尚未|未|不|没有|即不|亦不)[^,;。]{0,8}?(成就|成立|具备|满足|查明|确定|认定|存在)|"
                         r"(不|未|尚未|并未|没有)[^,;。]{0,6}?(具备|符合|满足)[^,;。]{0,10}?(适用)?(前提|条件|要件)|"
                         r"(未|尚未|并未|没有|未能|无法|不能)[^,;。]{0,26}?(适用)?(前提|条件|要件)|"
                         r"(后果|效果)[^,;。]{0,6}?(不发生|不产生|无从发生|不成立)|"
                         r"(前提|条件|要件|责任|归属|原因)[^,;。]{0,12}?(未经|尚未|并未|未)[^,;。]{0,6}?(查明|认定|确定|审理|证明|举证)|"
                         r"(责任|归属|原因|前提|条件)[^,;。]{0,12}?(并不明确|不明确|不明|未定)")
# the damages ground (P12) is what this exclusion is for: 工期违约金的抵扣, not the word 违约金 or
# 扣减 wherever it appears (鉴定意见未据此扣减材料价差 is the price object, not the damages object).
P08_OTHER_GROUND = re.compile(r"工期(延误)?违约金|逾期竣工违约金|抵扣|抵销")
# the premise limb needs an object of its own: without one, the delay term would be read on the
# line and the price term on the heading chain, so any "前提/条件未成就" sentence under a price
# heading (a payment-condition sentence, for example) would earn U17. The unproven premise
# must itself be the delay/responsibility premise or the clause that states it.
P08_PREMISE_OBJ = re.compile(r"工期|延误|16\.2\.2|该条|本条|该条款|该项|适用前提|责任|归属|原因")


def eval_p08(judge, doc):
    def score(span):
        for s in span["sentences"]:
            c = s["canon"]
            # delay object inside the sentence's own line; price-adjustment object in the sentence,
            # or in the nearest heading of that line (R03 heading chain), never a damages sentence
            if re.search(r"工期|延误|16\.2\.2", s["line_canon"]) and re.search(r"信息价|价差|调差|价格|材料", s["lctx"]) \
                    and not P08_OTHER_GROUND.search(c) \
                    and (P08_PRED.search(s["a"])
                         or (P08_PREMISE.search(s["a"]) and P08_PREMISE_OBJ.search(s["a"]))):
                return 1.0
        return 0.0
    passing = next((span for span in doc.spans if score(span) == 1.0), None)
    if passing:
        obs = observe_lines(judge, doc, "obs.G08", passing["lines"],
                            "price.delay_bar_unsupported", "proposition_span", "N01")
    else:
        obs = judge.observe("obs.G08", "confirmed_missing",
                            [doc.section_loc("price.delay_bar_unsupported", "obs.G08")])
    judge.gate("G08", bool(passing), obs,
               "delay-based price bar rebutted" if passing else "delay-based price bar not rebutted")


# ---- P14: clause 12.1 does not bar caisson re-pricing --------------------------------------
P14_NONAPP = re.compile(
    r"无适用(?:余地|对象)|不能(?:直接)?适用|不属于[^。;]{0,60}?12\.1[^。;]{0,20}?(?:约定|范围)|"
    r"不能因为[^。;]{0,60}?12\.1|无可供调整的对象|并不冲突|"
    r"不能(?:据此|由此|反过来)[^。;]{0,16}?(?:否定|推出|推翻|证明|认定)|"
    r"援引不能成立|混淆[^。;]{0,20}?(?:单价调整|组价)")


def eval_p14(judge, doc):
    sentences = list(body_sentences(doc))
    qualifying = set()
    for i, (line, sentence) in enumerate(sentences):
        a = sentence["a"]
        if a == Q or not P14_NONAPP.search(a):
            continue
        if not ("12.1" in sentence["canon"] or (re.search(r"该条|本条|此条|其援引", a)
                    and any("12.1" in prior["canon"] for _, prior in sentences[max(0, i - 2):i]))):
            continue
        if not any("沉井" in nearby["canon"] for _, nearby in sentences[max(0, i - 6):i + 3]):
            continue
        if INTERROGATIVE.search(a) or OPPONENT_GROUND.search(a[:P14_NONAPP.search(a).start()]):
            continue
        if reported_ground(a, P14_NONAPP.search(a).start(), P14_NONAPP.search(a).end()):
            continue
        qualifying.add(line["locator"])
    def score(span):
        return 1.0 if any(line["locator"] in qualifying for line in span["lines"]) else 0.0
    decide_positive(judge, doc, "P14", "price.clause_12_1_caisson_repricing", score,
                    "clause 12.1 does not preclude caisson re-pricing", "none",
                    conflict=span_concedes(("caisson",)))


# ---- P10 overdue-review penalty is not a precondition of the overdue-payment penalty ------
P10_A = re.compile(r"(并非|不是|不构成|不属于|不能作为|不应作为|并不是)[^。;]{0,25}?(前置条件|前提条件|前置程序|前提)")
P10_B = re.compile(r"(提交|送交|送|委托|交由|报送)[^。;]{0,15}?(审计|审价|第三方)[^。;]{0,30}?(不能|并不能|不得|无法|不足以|不当然|不应)[^。;]{0,6}?(当然)?(免除|豁免|免去|减轻|阻却)[^。;]{0,20}?(违约责任|违约金|付款义务|责任)")
P10_C = re.compile(r"逾期审核[^。;]{0,20}?(与|和|同)[^。;]{0,20}?逾期(付款|支付)[^。;]{0,20}?(不同|相互独立|各自独立|独立|互不影响|并行)")
P10_D = re.compile(r"(两|二|数|各)项?[^。;]{0,10}?(彼此|各自|相互)?(独立|不同)的?(违约责任|违约金|责任|义务)")
# R16: A is not a precondition of B is also written as "whether A holds does not affect whether B holds"
P10_E = re.compile(r"(不影响|并不影响|互不影响|不以[^。;]{0,12}?为前提|与[^。;]{0,12}?无关|(所)?规范的?对象[^。;]{0,12}?(不同|不是|并非)|错置|张冠李戴|并非同一[^。;]{0,6}?(问题|责任|款项|条款)|而非[^。;]{0,8}?逾期审核|并非(依|据|就|以|针对|基于)[^。;]{0,12}?(该款|第\\(1\\)款|逾期审核|审核))")
# R16 (U20, audit-does-not-excuse limb). The contract's accepted set is 提交审计不能免除违约责任; an
# answer writes it as 交由第三方审价不改变义务主体 / 不等于已完成审核 / 该抗辩不能免除付款义务.
# Same object, relation and polarity - only the discharging verb differs.
P10_F = re.compile(r"(送交|交由|委托|报送|提交|送)[^。;]{0,15}?(审计|审价|第三方)[^。;]{0,30}?"
                   r"((不|并不|不能|不足以|无法)[^。;]{0,10}?(免除|豁免|免去|减轻|阻却|改变|转移|消灭)"
                   r"|(不等于|并不等于|不能等于|不同于|不构成)[^。;]{0,12}?(免除|履行|完成|审核|签发|履约))|"
                   r"(抗辩|主张|理由|事由|情形)[^。;]{0,10}?(不能|并不能|不足以|无法|并未)[^。;]{0,8}?(免除|豁免|免去|阻却|消灭)"
                   r"[^。;]{0,14}?(付款义务|违约责任|违约金|逾期付款责任|逾期付款|付款责任)")


def eval_p10(judge, doc):
    def score(span):
        for s in span["sentences"]:
            a = s["a"]
            if s["a"] == Q:
                continue
            if P10_A.search(a) and re.search(r"审核|审价|审计|14\.2\(1\)|第\(1\)款|第一款", s["canon"]):
                return 1.0
            if P10_B.search(s["c"]) or P10_C.search(a):
                return 1.0
            if P10_D.search(a) and re.search(r"审核|审价|审计", s["canon"]) \
                    and re.search(r"逾期(付款|支付)|竣工付款", s["canon"]):
                return 1.0
            if P10_E.search(a) and re.search(r"(逾期)?审核|审价|审计", s["lctx"]) \
                    and re.search(r"逾期(付款|支付)|竣工付款", s["lctx"]):
                return 1.0
            if P10_F.search(a) and re.search(r"(逾期)?审核|审价|审计", s["lctx"]) \
                    and re.search(r"逾期(付款|支付)|竣工付款|付款义务|付款责任", s["lctx"]):
                return 1.0
        return 0.0
    decide_positive(judge, doc, "P10", "penalty.review_not_precondition", score,
                    "the overdue-review penalty is not a precondition and third-party audit does not excuse late payment", "none",
                    span_concedes_penalty)


# ---- P11 penalty runs from the filing date (2021-08-19) because no settlement certificate -
# R16: the negation may stand before the issuing verb or after the topicalised certificate
# (拒绝出具竣工结算证书 / 结算证书始终未签发); both orders are one proposition.
NEG_ISSUE = r"(?:不|未|没有|并未|从未|均未|亦未|始终未|一直未|迟迟未|尚未|至今未|长期不|迟迟不|拒不|拒绝|拖延|未能|未曾)"
P11_DATE = re.compile(r"起诉(之日|日|时|当日)|提起诉讼(之日|时)?|诉前调解立案(之日)?|立案之日|主张权利(之日)?|诉讼主张(权利)?之日|@2021-08")
P11_START = re.compile(r"起算|起计|作为[^。;]{0,10}?(起算|应付款|付款)|视为[^。;]{0,8}?(应付|付款)|起(按|至|计|支付)|之日起|\)起")
P11_REASON = re.compile(NEG_ISSUE + r"[^。;]{0,12}?(签发|出具)[^。;]{0,8}?(竣工)?结算证书|"
                        r"(竣工)?结算证书[^。;]{0,12}?" + NEG_ISSUE + r"[^。;]{0,6}?(签发|出具)|"
                        r"(起算(时间|时点|日|点|日期)|付款(时间|期限|日期|时点)|应付款(时间|日))[^。;]{0,10}?(不明确|不明|难以确定|无法确定|约定不明)")


def eval_p11(judge, doc):
    def score(span):
        if not re.search(r"违约金|利息|逾期付款|逾期支付", span["ctx"]):
            return 0.0
        # R14 scope: the object limbs (the date and the start) must sit in one sentence, the adoption
        # marker anywhere in the same local span - the same treatment P12 already uses, and the reason
        # R03 defines a span rather than a sentence as the unit of local evidence.
        stated = any(P11_DATE.search(s["a"]) and P11_START.search(s["a"])
                     and not re.search(r"质保金|质量保证金|保证金|保险费", s["canon"]) for s in span["sentences"])
        adopt = stated and span_adopts(span)
        reason = any(P11_REASON.search(s["a"]) for s in span["sentences"])
        return 1.0 if adopt and reason else 0.5 if adopt else 0.0
    decide_positive(judge, doc, "P11", "penalty.start_filing_date", score,
                    "the penalty properly runs from the filing date because no settlement certificate fixed the due date",
                    "filing-date start endorsed without the reason", span_concedes_penalty)


# ---- P12 delay liquidated damages: no counterclaim, first instance properly declined -----
P12_PRED = re.compile(NO_COUNTERCLAIM_SRC + r"|(未|没有|并未)[^。;]{0,15}?(举证|质证|辩论)")
# Polarity: a span whose adopted text affirms that a counterclaim WAS filed
# ("B公司已提出…反诉", "反诉请求业已提出") contradicts the record (判决书 p78: 未提出反诉), so the
# not-litigated limb in the same span cannot carry P12 to full credit. The clause that leads
# into the match is read: a negator anywhere in it (未就该项…提出反诉, 从未提出) or a question /
# condition marker (是否提出反诉, 如其提起反诉) means the sentence does not affirm a filing, so
# correct text is never vetoed.
P12_CC_AFFIRM = re.compile(r"(提出|提起)[^。;，,]{0,12}?反诉|反诉(请求)?[^。;，,]{0,6}?(已|业已|已经)(提出|提起)")
P12_CC_GUARD = re.compile(NEG_ZH + r"|是否|能否|如|若|倘|假设|即使|可以?(另行)?")


def affirms_counterclaim(text: str) -> bool:
    for m in P12_CC_AFFIRM.finditer(text):
        lead = re.split(r"[，,；;。：:]", text[:m.start()])[-1]
        if not P12_CC_GUARD.search(lead + text[m.start():m.end()]):
            return True
    return False


def eval_p12(judge, doc):
    def score(span):
        local = (span["chain"][-1]["canon"] if span["chain"] else "") + "".join(l["canon"] for l in span["lines"])
        if not re.search(r"工期[^。;]{0,8}违约金|逾期竣工违约金|工期[^。;]{0,20}(抵扣|抵销|扣减)", local):
            return 0.0
        pred = any(P12_PRED.search(s["a"]) and not re.search(r"信息价|价差|调差", s["canon"]) for s in span["sentences"])
        if any(affirms_counterclaim(s["a"]) for s in span["sentences"]):
            return 0.0
        other = any(re.search(r"另行(主张|起诉|诉讼|解决)", s["a"]) for s in span["sentences"])
        proper = span_adopts(span)
        if pred and proper:
            return 1.0
        return 0.5 if other and proper else 0.0
    decide_positive(judge, doc, "P12", "delay.no_counterclaim", score,
                    "no counterclaim for delay damages was filed, so the first instance properly declined to offset them",
                    "separate-claim route endorsed without the missing counterclaim", span_concedes_delay)


# ---- P13 construction judicial interpretation (I) article 27 -------------------------------
P13_RE = re.compile(r"(建设工程施工合同纠纷案件适用法律问题的解释\((一|1)\)|(建工|建设工程)(施工合同)?(司法)?解释\((一|1)\)|法释〔2020〕25号|法释\[2020\]25号)[^。;]{0,40}?§27(?!\d)")


def eval_p13(judge, doc):
    def score(span):
        for s in span["sentences"]:
            m = P13_RE.search(s["a_full"])
            if not m or not re.search(r"起诉|起算|利息|违约金|应付款", s["canon"]):
                continue
            if re.search(r"(不适用|不能适用|不应适用|不应参照|不能参照|不宜参照|并非|不属于|无关|错误)[^。;]{0,60}$", s["a_full"][:m.start()]):
                continue
            if re.search(r"^[^。;,]{0,20}(不适用|不能适用|不应适用|错误|不当)", s["a_full"][m.end():]):
                continue
            return 1.0
        return 0.0
    decide_positive(judge, doc, "P13", "penalty.interpretation_art27", score,
                    "relies on Construction Interpretation (I) article 27 for the due date", "none", rule="N05")


# ---- deductions ----------------------------------------------------------------------------
class Deductions:
    def __init__(self, judge: ProgramJudge, doc: Doc):
        self.judge, self.doc, self.counter = judge, doc, 0

    def decide(self, item_id, sections, manifestations, key_fn, root, reason, object_key):
        scans = [f"obs.scan.{s}" for s in sections]
        if not manifestations:
            self.judge.deduction(item_id, "not_triggered", scans, "error proposition not asserted")
            return
        occurrences, obs_ids, seen = [], [], set()
        for lines, detail in manifestations:
            manifestation = f"{item_id}:{lines[0]['locator']}:{detail}"
            if manifestation in seen:
                continue
            seen.add(manifestation)
            self.counter += 1
            obs = observe_lines(self.judge, self.doc, f"obs.{item_id}.m{self.counter}", lines, object_key, "error_span", "N01")
            obs_ids.append(obs)
            occurrences.append({"damage_instance_key": key_fn(detail), "causal_root_id": root, "manifestation_id": manifestation,
                                "observation_id": obs, "reason": detail})
        self.judge.deduction(item_id, "triggered", scans + obs_ids, reason, occurrences)


def shape_count(lines: list[dict]) -> int:
    """N09: non-whitespace characters of body lines, excluding gap-marked clauses."""
    total = 0
    for line in lines:
        for clause in re.split(r"[,;。]", n06_gap(line["clean"])):
            if GAP_TOKEN not in clause:
                total += len(clause)
    return total


def shape_groups(doc: Doc):
    """R10: body lines grouped by their level-1 heading; the first keyword decides price vs penalty.
    A level-1 block whose heading names neither is outside the declared scope of S01 and S02 (the
    contract measures "level-1 blocks whose heading first names a price term" and "…a penalty or
    delay term" and says nothing about any other block), so it is simply not measured. It is not a
    reason to abandon the measurement: doing so made an answer that adds an off-scope section escape
    the shape charge that the same answer would have taken without it."""
    if not any(l["level"] == 1 for l in doc.body):
        return None
    groups = {"price": [], "penalty": []}
    for line in doc.body:
        # R10: the block is the one whose heading names the term. Reading only the level-1 heading
        # made the measurement carrier-bound: an answer that puts its whole argument under
        # 二、事实与理由 and names 鉴定/造价 one level down had neither unit measured at all, and
        # escaped both shape charges although its price and penalty answers are the usual length.
        # The chain is walked outermost first, so a level-1 heading that names a term still wins.
        head = None
        for candidate in line["chain"] + ([line] if line["level"] else []):
            if PRICE_KW.search(candidate["clean"]) or PEN_KW.search(candidate["clean"]):
                head = candidate
                break
        if head is None:
            continue
        p, q = PRICE_KW.search(head["clean"]), PEN_KW.search(head["clean"])
        if p and (not q or p.start() < q.start()):
            groups["price"].append(line)
        elif q:
            groups["penalty"].append(line)
    return groups


def body_sentences(doc: Doc):
    for line in doc.body:
        if line["quoted_zone"]:
            continue
        for s in line["sentences"]:
            yield line, s


OPPONENT_REQUESTER = re.compile(r"(上诉人|B公司|被答辩人|对方(当事人)?|一审被告|原审被告)((虽然?|虽|亦|也|还|又|再|仍|另|即|则|在上诉状中|在二审中|于上诉状中)?(一并|同时|进一步)?|的[^,;:]{0,8}?(上诉)?(请求|主张|诉请)[^,;:]{0,8}?)$")
# D05 sentence-level reporting: the prayer belongs to whoever the sentence says makes it. The subject
# may sit clauses earlier (被答辩人的上诉状共列四项理由,分别针对…,请求撤销一审判决第一项、第三项)
# or be the anaphor for the appellant (其请求整体撤销一审判决第三项,没有事实和合同依据).
REPORTED_PRAYER = re.compile(OPPONENT_SUBJ + r"[^。;]{0,60}?(请求|要求|提出|主张|申请)|"
                             r"(?<![答辩])其(?:亦|也|仍|又|还|均|虽然?|则)?(请求|要求|主张)")
# D05 negation: a prayer the answer says was not made, or was not supported, is not a prayer the
# answer makes (被答辩人也未说明为何…而必须发回重审; 未提出支持发回重审的独立程序性事由).
DENIED_PRAYER = re.compile(r"(未|没有|并未|从未|亦未|均未|不曾)[^。;]{0,10}?(说明|证明|提出|指出|阐明|列明|举证|表明|明确)")
# D05 statutory recital: 依民事诉讼法…原判决认定基本事实不清的,可以查清事实后改判,或者撤销原判决
# 发回重审 states the statute's own disposals, not a request.
STATUTE_RECITAL = re.compile(r"(依|根据|按照|依照)[^。;]{0,25}?(民事诉讼法|诉讼法|法律规定|司法解释|《[^》]{0,40}》|第[零〇一二三四五六七八九十百]+条|§\d+)|"
                             r"(原判决|一审判决|第一审判决)[^。;]{0,25}?的,")
# D05 rejection of the prayer: 驳回…发回重审的请求 / 请二审法院依法驳回…撤销一审判决…的请求 asks the
# court to refuse it. 维持 asks for the judgment to stand, which is the opposite of revoking it.
PRAYER_REFUSED = re.compile(r"驳回|维持原判|维持一审|维持原审|不予支持|不应(予以)?支持|不予采纳|无(适用)?余地")
# D05 request governance: a bare 发回重审 token is a request only when a request verb or an
# affirmative deontic governs it in the same clause (contract trigger: "the appellee's own sentence
# or closing request asks to ... remand"). A recital or a topic mention asks for nothing.
REQUEST_GOVERNOR = re.compile(r"(请求|恳请|要求|望|请|申请|提请|敬请)|(?<![不未无])(应当?予?以?|须|必须|依法应)")
REJECT_LEAD = re.compile(r"(不应|不能|无需|不予|没有必要|不必|并无|驳回|不存在|未|没有|并未|从未|亦未|均未|"
                         r"无|不具备|不符合|不属于|不足以|难以|排除|维持)")


def opponent_requester(text: str, position: int) -> bool:
    """D05 subject binding: a request verb whose own clause subject is the appellant reports the
    appellant's request (上诉人虽请求撤销…), not the appellee's adopted request. The subject may also
    have been named earlier in the same sentence, which is how a pleading normally reports a prayer."""
    clause = re.split(r"[,:]", text[:position])[-1]
    if OPPONENT_REQUESTER.search(clause):
        return True
    return any(m.start() <= position for m in REPORTED_PRAYER.finditer(text[:position + 6]))


def prayer_denied(text: str, position: int) -> bool:
    """D05 polarity, read over the whole sentence: the answer reports that the prayer was not made
    out, or refuses it, rather than making it."""
    return bool(DENIED_PRAYER.search(text[:position]) or STATUTE_RECITAL.search(text[:position]))


def appeal_clause(sentence: str, position: int) -> str:
    """R12: the clause that carries the appeal verb (text after the last comma, colon or semicolon)."""
    return re.split(r"[,:;]", sentence[:position])[-1]


def appeal_actor(sentence: str, position: int) -> str | None:
    """R12 subject binding: a party token inside the appeal verb's own clause governs the verb;
    when that clause names no party the sentence topic governs, and a party introduced by a
    co-argument marker (与/和/同/跟/对/向/针对/就) is a counterparty, never the subject."""
    tokens = list(APPEAL_PARTY.finditer(appeal_clause(sentence, position)))
    if tokens:
        return "appellee" if tokens[-1].group(0) in APPELLEE_SIDE else "appellant"
    for m in APPEAL_PARTY.finditer(sentence[:position]):
        if CO_ARGUMENT.search(sentence[:m.start()]):
            continue
        return "appellee" if m.group(0) in APPELLEE_SIDE else "appellant"
    return None


def appeal_denied(sentence: str, position: int) -> bool:
    """R12 polarity: read on the appeal verb's own clause; 不服 is an attitude to the judgment,
    not a negation of the appeal."""
    return APPEAL_NEG.search(re.sub(r"不服|不满", "", appeal_clause(sentence, position))) is not None


def asserted_sentences(doc: Doc):
    """R02-asserted sentences of the answer body and the closing lines."""
    for line, s in body_sentences(doc):
        yield line, s["a"]
    for line in doc.closing:
        for sentence in split_sentences(line["quoted"]):
            yield line, r02_asserted(sentence)


def eval_deductions(judge: ProgramJudge, doc: Doc) -> None:
    d = Deductions(judge, doc)

    found = [([line], f"price:{obj}") for line, s in body_sentences(doc)
             for obj in concession_hits(s["a"], tuple(D01_PATTERNS))]
    found += [([line], "penalty") for line, s in body_sentences(doc) if pattern_adopted(D02_PATTERN, s["a"])]
    found += [([line], "delay_damages") for line, s in body_sentences(doc) if pattern_adopted(D03_PATTERN, s["a"])]
    d.decide("D01", ["body"], found, lambda detail: "concede_" + detail, "R-role-concession",
             "adopts an appellant price, penalty or delay-damages ground", "answer.concession")

    found = []
    for line in doc.header:
        m = PARTY_LABEL.match(line["quoted"])
        if not m:
            continue
        label, value = m.group(1), re.split(r"[,(]", m.group(3), maxsplit=1)[0]
        ents = set(re.findall(r"([AB])公司", value))
        if re.search(r"^(不是|并非|非)", value):
            continue
        if label in ("答辩人", "被上诉人") and "B" in ents and "A" not in ents:
            found.append(([line], f"{label}-B"))
        if label in ("上诉人", "被答辩人") and "A" in ents and "B" not in ents:
            found.append(([line], f"{label}-A"))
    d.decide("D04", ["header"], found, lambda detail: "party_roles_inverted", "R-role-party",
             "party block inverts appellant and appellee", "party.roles")

    found = []
    for line, s in body_sentences(doc):
        a = s["a"]
        for m in re.finditer(r"发回重审", a):
            # a heading that names the topic is not a request (R13/04a: a heading is a proxy, not an
            # assertion); the request branch below reads request verbs, this one reads a bare token
            if line["level"]:
                continue
            clause_start = max([a.rfind(ch, 0, m.start()) for ch in ",;:"] + [-1]) + 1
            clause = a[clause_start:m.start()]
            # the contract's trigger is "the appellee's own sentence or closing request asks to ...
            # remand": a bare token in a statutory recital or a topic mention asks for nothing.
            if not REQUEST_GOVERNOR.search(clause):
                continue
            if REJECT_LEAD.search(clause) or PRAYER_REFUSED.search(clause):
                continue
            if rejected_after(a, m.end()):
                continue
            # R17: the appellee answering the appellant's remand request is not the appellee asking
            # for one. A remand named inside an opponent-attributed clause, or in a sentence that
            # says the request has no support, is an answer to it.
            if reported_ground(a, m.start(), m.end()):
                continue
            if opponent_requester(a, m.start()) or prayer_denied(a, m.start()):
                continue
            if re.search(r"(发回重审|该|其|此)[^。;]{0,12}?(请求|主张)[^。;]{0,16}?"
                         r"(没有|无|缺乏)[^。;]{0,8}?(理由|依据|支持)|"
                         r"(没有|无|不存在)[^。;]{0,12}?(违反法定程序|程序违法)", a):
                continue
            found.append(([line], "remand"))
        m = re.search(r"(支持|采纳)(?P<g>[^。;]{0,4}?)(上诉人|B公司)的?上诉(请求|主张|理由)", a)
        if m and not neg_in(m.group("g")) and not re.search(r"(不应|不能|不予|不)$", a[max(0, m.start() - 3):m.start()]):
            found.append(([line], "support_appeal"))
        for m in re.finditer(r"(请求|恳请|望|请|特此请求|敬请)[^。;]{0,20}?撤销[^。;]{0,20}?判决", a):
            # R17: 上诉请求 / 诉讼请求 / 反诉请求 is a noun naming somebody's claim, not the
            # appellee asking for something; 上诉人的上诉请求限于撤销…第一项 reports the scope of
            # the appeal, which is the opposite of adopting it.
            if re.search(r"(上诉|诉讼|反诉|变更)$", a[:m.start()]):
                continue
            if re.search(r"水泥|价差|调差|增加", a) or opponent_requester(a, m.start()):
                continue
            # 请二审法院依法驳回上诉人关于撤销一审判决…的请求 asks for the revocation to be refused.
            if PRAYER_REFUSED.search(m.group(0)):
                continue
            if rejected_after(a, m.end()) or prayer_denied(a, m.start()):
                continue
            found.append(([line], "revoke_judgment"))
            break
    for line in doc.closing:
        for sentence in split_sentences(line["quoted"]):
            a = r02_asserted(sentence)
            m = re.search(r"(请求|恳请|望|请)[^。;]{0,20}?(撤销[^。;]{0,20}?判决|发回重审|支持[^。;]{0,4}上诉)", a)
            if m and not re.search(r"(上诉|诉讼|反诉|变更)$", a[:m.start()]) \
                    and not re.search(r"水泥|价差|驳回", a) and not opponent_requester(a, m.start()):
                found.append(([line], "closing_adverse_request"))
    d.decide("D05", ["body", "closing"], found, lambda detail: "adverse_request", "R-role-request",
             "the appellee's own request supports revocation, remand or the appeal", "request.adverse")

    found = []
    for line, s in body_sentences(doc):
        a = s["a"]
        for label, pattern, bounds in (
                ("caisson", r"沉井[^。;]{0,25}?(造价|价款|费用|工程款)[^。;¥]{0,10}?¥([\d.]+)", CAISSON_RANGE),
                ("cement", r"水泥[^。;]{0,15}?(调差|价差|差价|调价)[^。;¥]{0,15}?¥([\d.]+)", CEMENT_RANGE)):
            for m in re.finditer(pattern, a):
                try:
                    value = Decimal(m.group(2))
                except InvalidOperation:
                    continue
                if not bounds[0] <= value <= bounds[1]:
                    found.append(([line], f"{label}-{m.group(2)}"))
    amount_found = [([line], "amount:" + detail) for (lines, detail) in found for line in lines]

    found = []
    for line, s in body_sentences(doc):
        a = s["a"]
        ctx = "".join(h["canon"] for h in line["chain"]) + s["canon"]
        if not re.search(r"违约金|逾期付款|逾期支付", a) or re.search(r"诉讼请求|诉请|原告(主张|请求)|A公司(主张|请求)|质保金|质量保证金|保证金", ctx):
            continue
        for m in re.finditer(r"(?:自|从|以)?@(\d{4}-\d{2}(?:-\d{2})?)[^。;@]{0,16}?(?:起|开始|起算|作为[^。;]{0,6}起算)", a):
            date = m.group(1)
            accepted = date in ACCEPTED_PENALTY_DAYS
            if not accepted:
                found.append(([line], f"start-{date}"))
    penalty_start_found = [([line], "penalty_start:" + detail) for (lines, detail) in found for line in lines]

    found = []
    for line in doc.lines:
        for segment in re.split(r"[,;。]", line["quoted"]):
            if GAP_TOKEN in segment:
                continue
            if re.search(r"民终第?\d+号", segment):
                found.append(([line], "case_number_digits"))
            if line.get("zone") != "header":
                continue
            if re.search(r"住所地?|地址|住址", segment) and re.search(r"\d+(号|路|栋|室|弄|幢|单元|楼)", segment):
                found.append(([line], "address_digits"))
            if re.search(r"(统一社会信用代码|信用代码):?[0-9A-Z]{18}", segment):
                found.append(([line], "credit_code"))
            if re.search(r"(?<!\d)1[3-9]\d{9}(?!\d)|(?<!\d)0\d{2,3}-\d{7,8}(?!\d)", segment):
                found.append(([line], "phone"))
            m = re.search(r"(法定代表人|负责人|法人代表):?([一-鿿]{1,4})", segment)
            if m and m.group(2) not in ("甲", "乙") and not re.search(r"某|职务|同上|不详", m.group(2)):
                found.append(([line], "representative_name"))
    d.decide("D08", ["header", "body", "closing"], found, lambda detail: "fabricated_identifiers", "R-fabrication",
             "invented case number or party identifiers not present in the materials instead of a gap marker", "party.identifiers")

    found = []
    for line, s in body_sentences(doc):
        if s["a_full"] == Q or re.search(r"已废止|废止|失效|原《", s["canon"]):
            continue
        c = s["a_full"]
        if re.search(r"关于审理建设工程施工合同纠纷案件适用法律问题的解释(\((二|2)\))?》", c) or re.search(r"法释(〔|\[)(2004|2018)(〕|\])(14|20)号", c):
            found.append(([line], "repealed_interpretation"))
    d.decide("D09", ["body"], found, lambda detail: "repealed_interpretation_basis", "R-law",
             "relies on a repealed construction judicial interpretation", "penalty.legal_basis")

    # D12 unsupported author-originated procedural assertion (R11)
    found = []
    for line, s in body_sentences(doc):
        for key, pattern in UNSUPPORTED_ACTS:
            for m in pattern.finditer(s["a"]):
                clause = re.split(r"[,:;]", s["a"][:m.start()])[-1]
                if ACT_MODAL.search(clause) or ACT_REPORTED.search(clause):
                    continue
                if ACT_GENERIC.match(clause):
                    continue
                if key in ATTRIBUTION_KEYS and (HYPOTHETICAL_LEAD.search(s["a"][:m.end()])
                                                or ATTRIBUTION_NEGATED.search(m.group(0)) or ACT_NEG.search(clause)
                                                or ACT_REPORTED.search(s["a"][:m.start()])):
                    continue
                if ACT_NEG.search(clause) and ACT_FILING.search(s["a"][:m.start()]):
                    continue
                if key == "appraisal_procedure" and OBJ_SUBJECT.search(clause):
                    here = line["sentences"].index(s)
                    near = "".join(x["canon"] for x in line["sentences"][here:here + 2])
                    if OBJ_RECORD.search(near) and OBJ_REDUCED.search(near):
                        continue
                found.append(([line], f"{key}:{m.group(0)[:16]}"))
    d.decide("D12", ["body"], found, lambda detail: "unsupported_addition:" + detail.split(":")[0],
             "R-unsupported-addition",
             "asserts a procedural act or omission that neither material records", "document.unsupported_additions")

    judge.deduction("D14", "not_triggered", ["obs.scan.body", "obs.scan.closing"],
                    "retired: conventional dismissal/uphold request is proper for a non-appealing appellee")

    # D13 intra-artifact contradiction on the frozen appellant identity (R12)
    affirmed, denied = [], []
    for line, a in asserted_sentences(doc):
        for m in FILE_APPEAL.finditer(a):
            if appeal_actor(a, m.start()) != "appellee":
                continue
            (denied if appeal_denied(a, m.start()) else affirmed).append(line)
    found = []
    if affirmed and denied:
        found = [([affirmed[0]], "appellee_filed_appeal"), ([denied[0]], "appellee_did_not_appeal")]
    d.decide("D13", ["body", "closing"], found, lambda detail: "internal_contradiction:appellant_identity",
             "R-internal-contradiction",
             "asserts both that the appellee did and that it did not file the appeal", "document.internal_contradiction")

    found = []
    for line in doc.body:
        for m in FIGURE.finditer(line["clean"]):
            try:
                value = Decimal(m.group(0).replace(",", ""))
            except InvalidOperation:
                continue
            digits = str(int(value))
            for total in DERIVED_TOTALS:
                ref = str(int(total))
                if value == total or len(digits) != len(ref) or len(ref) < 7:
                    continue
                if sum(a != b for a, b in zip(digits, ref)) == 1:
                    found.append(([line], f"{total}"))
    derived_found = [([line], "derived_total:" + detail) for (lines, detail) in found for line in lines]
    found = amount_found + penalty_start_found + derived_found
    def amount_key(detail):
        kind, value = detail.split(":", 1)
        if kind == "amount":
            return "wrong_amount:" + value.split("-")[0]
        if kind == "penalty_start":
            return "wrong_penalty_start"
        return "wrong_derived_total:" + value
    d.decide("D06", ["body"], found, amount_key, "R-wrong-amount-or-date",
             "states a wrong case amount, derived total or penalty start date", "amounts.case_figures")

    lines = doc.lines

    text = "\n".join(l["clean"] for l in lines)
    missing = [name for name, test in REQUIRED_PARTS if not test(lines[0]["clean"] if lines else "", text)]
    if lines and missing:
        obs = observe_lines(judge, doc, "obs.D17.parts", lines, "document.required_parts", "section_text", "N01")
        judge.deduction("D17", "triggered", ["obs.scan.body", obs], "required parts missing: " + ", ".join(missing),
                        [{"damage_instance_key": "missing_structure", "causal_root_id": "R-required-parts",
                          "manifestation_id": f"D17:{name}", "observation_id": obs, "reason": f"{name} absent"}
                         for name in missing])
    else:
        judge.deduction("D17", "not_triggered", ["obs.scan.body"], "all required parts present")

    shapes = {s["id"]: s for s in judge.contract.get("shape_units", [])}
    groups = shape_groups(doc) if doc.body_state == "identified" else None
    shape_occurrences = []
    shape_observations = ["obs.scan.body"]
    for shape_id, group in ():  # Reference character counts are diagnostic only, not a task requirement.
        scans = ["obs.scan.body"]
        if doc.body_state != "identified":
            continue
            continue
        if groups is None:
            continue
            continue
        members = groups[group]
        count = shape_count(members)
        # A block whose whole content is gap-marked is a declared gap, not a thin answer: the gap marker
        # contract invites it and it keeps the old reading. A block with no lines at all is measured as an
        # underrun at zero characters - deleting the section that carries a ground is the largest version
        # of "too thin to carry it", and leaving it unmeasured let a half-deleted answer take no damage.
        if members and count == 0:
            continue
            continue
        shape = shapes[shape_id]
        ratio = count / max(float(shape["golden_value"]), float(shape["declared_floor"]))
        # There is no overrun arm where the contract sets no overrun tolerance (null). The Golden is a
        # compressed reference the answering model never sees and the instruction states no length, so a
        # high ratio only means "wrote more than the reference", not a defect. The underrun arm applies:
        # an answer too thin to carry the ground is real damage, and it is what catches a deleted block.
        over_tolerance = shape.get("overrun_tolerance_ratio")
        over = None if over_tolerance is None else ratio - (1 + float(over_tolerance))
        under = (1 - float(shape["underrun_tolerance_ratio"])) - ratio
        if (over is None or over <= 0) and under <= 0:
            continue
            continue
        overrun = over is not None and over > 0
        detail = f"{'over' if overrun else 'under'}-{count}-of-{int(shape['golden_value'])}"
        obs = observe_lines(judge, doc, f"obs.D10.{shape_id}.shape", members or doc.body,
                            f"shape.{shape_id}", "shape_members", "N09")
        # Wholesale missing content is not one typo: every further 15 percent of the Golden body missing
        # beyond the underrun tolerance opens one more damage instance of the same cause with the same
        # coefficient (no new coefficient), capped at four, so deleting a whole measured block cannot sit
        # inside the lenient lens's "at most two damage instances".
        instances = 1 if overrun else 1 + min(int(under / 0.15), 3)
        penalties = []
        for k in range(instances):
            suffix = "" if k == 0 else f":deficit{k}"
            penalties.append({"damage_instance_key": f"shape_{shape_id}{suffix}",
                              "causal_root_id": f"R-shape-{shape_id}",
                              "manifestation_id": f"D10:{shape_id}:{detail}{suffix}",
                              "observation_id": obs, "reason": detail})
        shape_occurrences.extend(penalties)
        shape_observations.append(obs)
    if shape_occurrences:
        judge.deduction("D10", "triggered", shape_observations,
                        "price or penalty answer length outside tolerance", shape_occurrences)
    elif doc.body_state == "identified" and groups is None:
        judge.deduction("D10", "ambiguous", shape_observations,
                        "level-1 blocks cannot be attributed to the price or penalty unit")
    else:
        judge.deduction("D10", "not_triggered", shape_observations,
                        "price and penalty answer length within tolerance or declared gap")


def evaluate(registry: dict, judge: ProgramJudge) -> None:
    """Call positive() once per P and deduction() once per D."""
    if registry.get("parse_failure"):
        for item_id in judge.positives:
            judge.positive(item_id, 0.0, "obs.parse_failure", "artifact could not be parsed", "different")
        for item_id in judge.deductions:
            judge.deduction(item_id, "parse_failure", ["obs.parse_failure"], "artifact could not be parsed")
        for item_id in judge.gates:
            judge.gate(item_id, False, "obs.parse_failure", "artifact could not be parsed")
        return
    doc = registry["doc"]
    for fn in (eval_p02, eval_p07, eval_p08, eval_p10, eval_p11, eval_p12, eval_p13, eval_p14):
        fn(judge, doc)
    for item_id in ("P15", "P16", "P17"):
        credit(judge, doc, item_id, 0.0, "missing", "semantic owner", [], "semantic." + item_id)
    eval_deductions(judge, doc)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("artifact", type=Path)
    parser.add_argument("--contract", type=Path, default=CANONICAL_CONTRACT)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--declared-path-missing", action="store_true",
                        help="the validator found no file at the declared deliverable path and scores another one")
    args = parser.parse_args()
    contract_path = args.contract.resolve()
    judge = ProgramJudge(load_contract(contract_path), args.artifact.resolve(), sha256(contract_path))
    judge.declared_path_missing = args.declared_path_missing
    evaluate(normalize(extract_raw(args.artifact.resolve()), judge), judge)
    result = judge.finish()
    # A missing required pleading part is a completeness failure, even when
    # the remaining positive facets happen to clear the generic damage-count
    # proxy used by the shared runtime.
    if any(item.get("id") == "D17" and item.get("state") == "triggered"
           for item in result.get("deduction_items", [])):
        result.setdefault("rewards", {})["lenient"] = 0.0
    rendered = json.dumps(result, ensure_ascii=False, indent=2)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
