"""Derive the payment facts used by the reference solution from issued records."""
from decimal import Decimal, ROUND_HALF_UP
import re

from docx import Document
from openpyxl import load_workbook


def dec(value):
    if isinstance(value, bool):
        raise ValueError("Boolean is not a financial value")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("Nonfinite value")
    return result


def money(value):
    return dec(value).quantize(Decimal(".01"), rounding=ROUND_HALF_UP)


def norm(value):
    return re.sub(r"\s+", "", str(value if value is not None else ""))


def records(sheet, required):
    for row in sheet:
        labels = [norm(cell.value) for cell in row]
        if all(norm(header) in labels for header in required):
            indexes = {header: labels.index(norm(header)) for header in required}
            return [
                {key: values[index] if index < len(values) else None
                 for key, index in indexes.items()}
                for values in sheet.iter_rows(min_row=row[0].row + 1, values_only=True)
                if any(value is not None for value in values)
            ]
    raise ValueError("Missing required fields in " + sheet.title)


def source(input_dir):
    document = Document(input_dir / "合同条款及报送联系单.docx")
    text = "\n".join(paragraph.text for paragraph in document.paragraphs)
    cutoff_match = re.search(r"签认资料截止时间为(\d+)月(\d+)日", text)
    if not cutoff_match:
        raise ValueError("Document cutoff unavailable")
    cutoff = f"2019-{int(cutoff_match[1]):02d}-{int(cutoff_match[2]):02d}"
    clauses = {row.cells[0].text: row.cells[1].text
               for table in document.tables for row in table.rows[1:]}
    rates = {key: dec(re.search(r"(\d+(?:\.\d+)?)%", clauses[key])[1]) / 100
             for key in ("保留金", "工程预付款", "材料预付款")}

    workbook = load_workbook(input_dir / "第五期计量签认资料.xlsx", data_only=True)
    prices = {norm(row["编码"]): row for row in records(
        workbook["单价清单"], ["编码", "项目名称", "单位", "单价（元）", "价格依据",
                              "确认日期", "价格状态"])}
    lines = {}
    pending = {}

    def insert(code, quantity, date, state, reference):
        if code in lines or code in pending:
            raise ValueError("Ambiguous active measurement " + code)
        rate = prices[code]
        eligible = (bool(date) and str(date) <= cutoff and state == "已签认"
                    and bool(rate["确认日期"]) and str(rate["确认日期"]) <= cutoff
                    and "申报价" not in str(rate["价格状态"]))
        row = {"quantity": quantity, "rate": dec(rate["单价（元）"]), "ref": reference,
               "name": rate["项目名称"], "unit": rate["单位"]}
        row["category"] = ("变更项目" if code.startswith("V") else
                           "计日工项目" if code.startswith("D") else "合同单价项目")
        row["amount"] = money(quantity * row["rate"])
        (lines if eligible else pending)[code] = row

    for row in records(workbook["工程计量"],
                       ["单据号", "编码", "上期末累计量", "本期末累计量", "签认日期", "记录状态"]):
        if "替代" in str(row["记录状态"]):
            continue
        insert(norm(row["编码"]), dec(row["本期末累计量"]) - dec(row["上期末累计量"]),
               row["签认日期"], row["记录状态"], row["单据号"])
    for row in records(workbook["计日工"], ["单据号", "编码", "台时", "现场确认日期", "记录状态"]):
        insert(norm(row["编码"]), dec(row["台时"]), row["现场确认日期"],
               row["记录状态"], row["单据号"])

    funds = load_workbook(input_dir / "资金往来及代扣资料.xlsx", data_only=True)
    opening = {norm(row["项目"]): dec(row["累计金额（元）"])
               for row in records(funds["期初结转"], ["项目", "累计金额（元）"])
               if row["累计金额（元）"] is not None}
    material_new = Decimal(0)
    material_recovery = Decimal(0)
    for row in records(funds["材料收发"], ["凭据", "数量", "原计付/确认单价", "比例", "业务记录"]):
        proportion = dec(str(row["比例"]).replace("%", "")) / 100
        amount = money(dec(row["数量"]) * dec(row["原计付/确认单价"]) * proportion)
        if "核销" in str(row["业务记录"]):
            material_recovery += amount
        elif "批准计付" in str(row["业务记录"]):
            material_new += amount
        else:
            raise ValueError("Unclassified material advance")
    other = sum(dec(row["金额（元）"])
                for row in records(funds["代扣凭据"], ["凭据编号", "金额（元）"])
                if row["金额（元）"] is not None)
    return {"lines": lines, "pending": pending, "rates": rates, "opening": opening,
            "material_new": material_new, "material_recovery": material_recovery,
            "other": other, "cutoff": cutoff}
