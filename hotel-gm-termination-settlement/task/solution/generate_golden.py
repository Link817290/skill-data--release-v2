#!/usr/bin/env python3
"""Generate the corrected v3 golden workbook with only stdlib OOXML."""

from __future__ import annotations

from pathlib import Path
import sys
from xml.sax.saxutils import escape, quoteattr
from zipfile import ZIP_DEFLATED, ZipFile


def col_name(index: int) -> str:
    value = index + 1
    out = ""
    while value:
        value, rem = divmod(value - 1, 26)
        out = chr(65 + rem) + out
    return out


def sheet_xml(rows: list[list[object]]) -> str:
    max_col = max((len(row) for row in rows), default=1)
    parts = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
        f'<dimension ref="A1:{col_name(max_col - 1)}{len(rows)}"/>',
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews>',
        '<sheetFormatPr defaultRowHeight="18"/><sheetData>',
    ]
    for row_no, row in enumerate(rows, 1):
        parts.append(f'<row r="{row_no}">')
        for col_no, value in enumerate(row):
            if value in (None, ""):
                continue
            ref = f"{col_name(col_no)}{row_no}"
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                parts.append(f'<c r="{ref}" s="1"><v>{value}</v></c>')
            else:
                parts.append(f'<c r="{ref}" t="inlineStr" s="2"><is><t>{escape(str(value))}</t></is></c>')
        parts.append('</row>')
    parts.append('</sheetData><pageMargins left="0.25" right="0.25" top="0.5" bottom="0.5" header="0.2" footer="0.2"/></worksheet>')
    return "".join(parts)


SHEETS: dict[str, list[list[object]]] = {
    "结算总览": [
        ["项目", "低值/确定值(元)", "高值/条件值(元)", "是否进入一次性总额", "说明"],
        ["已确定一次性应付", 240292.34, 248474.71, "是", "区间仅来自2025Q1绩效系数，并同步传导至年假基数；不含尚未确定适用基准的经济补偿"],
        ["经济补偿后见情景", 363526.88, 363526.88, "有条件", "193,881元于解除日后公布；只作情景测算，需补解除日适用的官方口径和法务意见"],
        ["含后见情景的备付金额", 603819.21, 612001.59, "非确定值", "已确定一次性应付+经济补偿后见情景"],
        ["竞业限制月标准", 19411.25, 19601.25, "否", "离职后按月支付24个月；区间来自绩效补差"],
        ["竞业24个月预算", 465870, 470430, "否", "持续义务，不是解除日一次性到期额"],
        ["解除性质", "公司提出并协商一致解除", "N，非2N", "否", "无代通知金"],
    ],
    "结算项目": [
        ["项目", "状态", "低值", "高值", "公式/判断", "事实依据", "规则依据", "汇总处理"],
        ["2026年3月工资", "应支付", 46500, 46500, "38000+6000+2000+500", "材料05 K15：付款批次待执行", "劳动合同第四条", "进入一次性总额"],
        ["经济补偿N（后见情景）", "待补适用时点证据", 363526.88, 363526.88, "193881÷12×3×7.5", "材料02、11、14；材料14发布晚于解除日", "材料15第四十七条", "不进入确定额；仅进入情景备付"],
        ["违法解除赔偿2N", "无需支付", 0, 0, "双方真实协商一致", "材料11、12", "解除协议及劳动合同法路径", "不进入"],
        ["代通知金", "无需支付", 0, 0, "协商解除不适用", "材料11、12", "法定单方解除路径", "不进入"],
        ["2025Q4绩效", "应支付", 53200, 53200, "38000×1.4", "材料06b H8：已审批未支付", "材料06a第三、五条", "进入一次性总额"],
        ["2026Q1绩效", "应支付", 53200, 53200, "38000×1.4×90÷90", "材料06b：最近已完成Q4系数1.4", "材料06a第五条", "进入一次性总额"],
        ["2025Q1绩效历史补差", "应支付最低额并待确认系数", 3800, 11400, "96分对应1.30~1.50；38000×(1.30~1.50-1.20)", "材料06b C5/D5/F5/H5", "材料06a第三条系数区间", "低值进入，高值为条件上限"],
        ["未休年休假工资", "应支付区间", 58992.34, 59574.71, "10天×[(772650+绩效补差3800~11400-加班6600)÷12÷21.75]×200%", "材料02参加工作时间；05收入；06绩效补差；01/08通讯约定；16系统记录", "累计工龄、离职折算取整、剔除加班；通讯按个人合同固定约定纳入", "进入一次性总额并随绩效参数联动"],
        ["虚拟股权未付分红", "应支付", 24600, 24600, "2400+3000+7200+12000", "材料09 VX台账；17归属协议", "已归属应付未付离职结算", "进入一次性总额"],
        ["2025年度经营奖金", "已结清", 0, 0, "33250已在2026-02工资及奖金台账双向勾稽", "材料05 C14/K14；09第7行", "不得重复支付", "不进入"],
        ["跟投计划分红", "已结清", 0, 0, "18000属于GT且已支付", "材料09第6行及台账说明", "与VX分开", "不进入"],
        ["新增加班费", "暂待确认，不重复支付已付部分", 0, 0, "审批覆盖岗位和期间；6600已付不追回；法定节假日差额及适用地方计薪规则待核", "材料03、05、07", "不定时审批不能单独排除法定节假日差额", "不进入"],
        ["竞业限制补偿", "离职后按月支付区间", 19411.25, 19601.25, "(772650+绩效补差3800~11400)÷12×30%", "材料04、05、06、01、08、18", "按应得工资修正；通讯按个人合同固定约定纳入", "不进入一次性总额"],
        ["住房安排", "已结清", 0, 0, "公寓已退；现金住房项目作为工资口径判断", "材料18", "实物返还与现金待遇分开", "不进入"],
    ],
    "参数账": [
        ["参数", "采用值", "单位", "来源", "理由/用途"],
        ["本公司入职日", "2019-03-01", "日期", "材料01、02、11", "经济补偿工龄"],
        ["参加工作时间", "2012-07-15", "日期", "材料02人事档案字段", "累计工作年限与年假档位"],
        ["解除日", "2026-03-31", "日期", "材料11、12", "N、年假、竞业起算"],
        ["经济补偿月数N", 7.5, "月", "2019-03-01至2026-03-31", "7整年+不足6个月按0.5"],
        ["2025深圳在岗职工年平均工资", 193881, "元/年", "材料14公开来源摘录；2026-07-24发布", "不得使用材料10缴费上限；不得忽略解除日时点"],
        ["经济补偿3倍封顶后见情景", 48470.25, "元/月", "193881÷12×3", "非无条件采用值；需补解除日适用基准"],
        ["工资表I口径合计", 772650, "元", "材料05 I4:I15逐月合计", "含全部薪资批次项目"],
        ["通讯项目", 6000, "元", "材料01固定约定；08一般报销条款与01个人合同固定约定的冲突；05 H列", "个人合同及连续履行支持纳入；费用票据仅作实施核验"],
        ["已付加班工资", 6600, "元", "材料05 E列、07", "年假日工资基数剔除"],
        ["年假月工资基数区间", "64154.17~64787.50", "元/月", "(772650+绩效补差3800~11400-6600)÷12", "绩效参数变化必须同步传导"],
        ["竞业月平均工资区间", "64704.17~65337.50", "元/月", "(772650+绩效补差3800~11400)÷12", "协议指应得工资性收入"],
        ["2025年未休结转", 8, "天", "10天应享-2天已休", "公司系统错用本单位司龄"],
        ["2026年折算", 2, "天", "INT(90÷365×10)", "不足整天舍弃"],
        ["累计未休年假", 10, "天", "8+2", "用于年假工资"],
    ],
    "证据与终检": [
        ["检查点", "采用结论", "冲突/反证", "定位"],
        ["社保缴费上限与经济补偿封顶", "使用公开统计年值换算48,470.25", "材料10的37,175仅为申报系统字段且来源未附", "材料10、14、15"],
        ["累计工龄与公司司龄", "2012-07-15参加工作，年假10天档", "材料16公司系统仅按2019入职及5天档维护", "材料02、16"],
        ["住房项目性质", "固定无票据现金，按实际履行纳入工资性收入", "合同及内部会计将其称福利；员工自有住房仍持续领取", "材料01、05、08、18"],
        ["通讯项目性质", "个人劳动合同约定500元/月随薪，且连续固定履行，纳入工资性收入", "员工手册一般条款要求凭票；个人合同另约定500元/月随薪，连续支付记录支持工资性履行判断，须说明权衡理由", "材料01、05、08"],
        ["最近完成绩效", "2025Q4已完成并批准1.4", "最近已经支付的是2025Q3的1.3", "材料05、06b"],
        ["3月工资付款", "应付未付", "解除协议概括确认发生于月末前", "材料05 K15、11签署日"],
        ["长期激励", "VX未付24,600；GT 18,000已付", "计划名称及付款代码不同", "材料09、17"],
        ["一次性总额", "确定项目240,292.34~248,474.71；若经济补偿后见情景成立，备付603,819.21~612,001.59", "历史绩效参数同步影响年假；竞业持续月付不混入", "结算项目逐项合计"],
        ["隐私", "仅使用员工A等脱敏称谓", "无证件、电话、详细地址", "全工作簿"],
    ],
}


def write_xlsx(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    names = list(SHEETS)
    with ZipFile(path, "w", ZIP_DEFLATED) as z:
        overrides = "".join(
            f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            for i in range(1, len(names) + 1)
        )
        z.writestr("[Content_Types].xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' + overrides + '</Types>')
        z.writestr("_rels/.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        sheet_tags = "".join(f'<sheet name={quoteattr(name)} sheetId="{i}" r:id="rId{i}"/>' for i, name in enumerate(names, 1))
        z.writestr("xl/workbook.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets>' + sheet_tags + '</sheets><calcPr calcMode="auto"/></workbook>')
        rels = "".join(f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>' for i in range(1, len(names) + 1))
        rels += f'<Relationship Id="rId{len(names)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        z.writestr("xl/_rels/workbook.xml.rels", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' + rels + '</Relationships>')
        z.writestr("xl/styles.xml", '<?xml version="1.0" encoding="UTF-8" standalone="yes"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="1"><font><sz val="10"/><name val="Aptos"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="3"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="4" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"><alignment wrapText="1" vertical="top"/></xf></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
        for i, name in enumerate(names, 1):
            z.writestr(f"xl/worksheets/sheet{i}.xml", sheet_xml(SHEETS[name]))


if __name__ == "__main__":
    output = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[2] / "golden" / "赔付清单.xlsx"
    write_xlsx(output)
    print(output)
