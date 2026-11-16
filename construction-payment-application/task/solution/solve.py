"""Reproduce a payment application from public records; never reads Golden."""
from pathlib import Path
from decimal import Decimal
import argparse,sys
from openpyxl import load_workbook
from docx import Document
from docx.shared import Pt,Cm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
import public_records as source

def solve(inputs,out):
    ref=source.source(inputs);out.mkdir(parents=True,exist_ok=True)
    opening=ref["opening"];categories=["合同单价项目","变更项目","计日工项目"]
    current={k:Decimal(0) for k in opening if k!="银行累计支付"}
    for line in ref["lines"].values():current[line["category"]]+=line["amount"]
    earned=sum(current[k] for k in categories)
    current["材料预付款"]=ref["material_new"]
    current["材料预付款扣回"]=ref["material_recovery"]
    eng_open=opening["工程预付款"]-opening["工程预付款扣回"]
    current["工程预付款扣回"]=min(max(source.money(earned*ref["rates"]["工程预付款"]),Decimal(0)),eng_open)
    current["保留金"]=source.money(earned*ref["rates"]["保留金"])
    current["其他扣款"]=ref["other"]
    plus=categories+["工程预付款","材料预付款"]
    minus=["工程预付款扣回","材料预付款扣回","保留金","其他扣款"]
    def total(vals):
        a=sum(vals[k] for k in plus);b=sum(vals[k] for k in minus)
        return {"应付款金额合计":a,"扣除金额合计":b,"进度付款申请金额":a-b}
    closing={k:opening[k]+v for k,v in current.items()}
    columns=[dict(opening,**total(opening)),dict(current,**total(current)),dict(closing,**total(closing))]
    w=load_workbook(inputs/"第五期付款申报表（空表）.xlsx")
    for row in w["支付汇总"].iter_rows(min_row=5):
        key=row[1].value
        if key in columns[0]:
            for col,values in enumerate(columns,3):w["支付汇总"].cell(row[0].row,col,float(values[key]))
    for r,(code,line) in enumerate(ref["lines"].items(),5):
        for c,value in enumerate([code,line["name"],line["unit"],line["quantity"],line["rate"],line["amount"],line["category"],line["ref"]],1):
            w["计价明细"].cell(r,c,float(value) if isinstance(value,Decimal) else value)
    eng_close=eng_open-current["工程预付款扣回"]
    mat_open=opening["材料预付款"]-opening["材料预付款扣回"]
    mat_close=mat_open+current["材料预付款"]-current["材料预付款扣回"]
    calcs={
        "本期已完工程价款":(earned,"计价明细合计"),
        "保留金":(current["保留金"],f"{earned:.2f}元已完工程价款（含Q03签认负计量，不含材料预付款）×{ref['rates']['保留金']:.0%}"),
        "工程预付款期初余额":(eng_open,f"{opening['工程预付款']:.2f}元已发放－{opening['工程预付款扣回']:.2f}元以前期扣回"),
        "工程预付款本期扣回":(current["工程预付款扣回"],f"{earned:.2f}元已完工程价款×{ref['rates']['工程预付款']:.0%}，以期初余额{eng_open:.2f}元为限"),
        "工程预付款期末余额":(eng_close,f"期初余额{eng_open:.2f}元－本期扣回{current['工程预付款扣回']:.2f}元"),
        "材料预付款本期新增":(current["材料预付款"],"批准入库未使用材料货值×约定比例"),
        "材料预付款本期扣回":(current["材料预付款扣回"],"8.250×4200.00元原计付单价×70%原比例"),
        "材料预付款期末余额":(mat_close,"期初余额加新增减扣回"),
        "其他扣款":(current["其他扣款"],"DK05-01临时供电代付款凭据；仅在支付汇总扣减一次"),
    }
    for row in w["扣款计算"].iter_rows(min_row=5):
        if row[0].value in calcs:
            value,basis=calcs[row[0].value];row[1].value=float(value);row[2].value=basis
    s=w["附件与待办"]
    items=[
        ["本期附件","计量及核价记录","；".join(x["ref"] for x in ref["lines"].values())+"；合同清单；变价01、02；计日价01","随计价明细报送有效计量及核价记录；计05-05B替代计05-05A，旧件仅存档；Q03签认复测负差保留"],
        ["本期附件","合同及资金资料","合同条款、期初结转、材料收发及代扣凭据","随申请表报送"],
    ]
    actions={
        "Q08":"计量工程师确认其6月26日签认晚于6月25日截止日，转第六期申报并保留已签累计量；本期未计价",
        "V03":"合同计价工程师取得正式核价确认后申报；保留已签工程量，不以申报价计入本期",
        "D02":"现场工程师补齐监理工作量签认后报送；未签认数量不计入本期",
    }
    pending_basis={"Q08":"计05-08，签认日2019-06-26", "V03":"计变05-03；变价03申报价尚待确认",
                   "D02":"计日05-02工作量签认未回"}
    for code,line in ref["pending"].items():items.append([code,line["name"],pending_basis[code],actions[code]])
    for r,values in enumerate(items,5):
        for c,value in enumerate(values,1):s.cell(r,c,value)
    s.row_dimensions[5].height=120
    for s in w:s.sheet_properties.tabColor=None
    w.save(out/"第五期进度付款申报表.xlsx")
    doc=Document()
    sec=doc.sections[0];sec.top_margin=Cm(2.2);sec.bottom_margin=Cm(2.2)
    sec.left_margin=Cm(2.4);sec.right_margin=Cm(2.4)
    normal=doc.styles["Normal"];normal.font.name="宋体";normal.font.size=Pt(12)
    normal.element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"),"宋体")
    normal.paragraph_format.line_spacing=1.5
    p=doc.add_paragraph();p.alignment=1
    run=p.add_run("第五期工程进度付款申请函");run.bold=True;run.font.size=Pt(18)
    net=columns[1]["进度付款申请金额"]
    for text in [
        "青溪河工程监理部：",
        f"现报送青溪河近期治理工程（QXH-2018-01）第五期付款申请，计量时段为2019年5月26日至6月25日，采用6月25日截止前的有效签认材料。本期申请金额为人民币{net:,.2f}元，请审核办理。",
        f"本期已完工程价款为{earned:,.2f}元，另列材料预付款；工程预付款与材料预付款分别列账，新增与扣回、保留金和代扣款均在汇总中独立列示。材料预付款扣回按原计付单价4,200.00元及原比例计算。计05-05B替代计05-05A，经签认的Q03复测负计量保留；单价均按合同、变价01、变价02和计日价01的含税费口径。",
        "计05-08于6月26日签认，晚于6月25日截止日，由计量工程师转第六期办理；计变05-03由合同计价工程师取得正式核价后申报，不采用申报价；计日05-02由现场工程师补齐监理工作量签认后报送。三项均未计入本期申报。",
        "附件：支付汇总、计价明细及有效签认核价依据、扣款计算及资金凭据、附件与待办清单。",
        "青溪水利工程有限公司、清源水利勘测设计有限公司\n青溪河项目部\n2019年6月28日",
        "项目经理：____________    （签章）",
    ]:doc.add_paragraph(text)
    doc.save(out/"第五期进度付款申请函.docx")
    return {"output": str(out), "current_net": str(net), "line_count": len(ref["lines"])}

if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--input",type=Path,default=ROOT/"environment/workspace/input")
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args();print(solve(a.input,a.out))
