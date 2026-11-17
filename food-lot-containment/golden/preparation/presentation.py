"""English business forms based on inspected trade-notice and distribution-list forms."""
from docx import Document
from docx.shared import Inches,Pt,Cm
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

def document(title,subtitle):
    d=Document();s=d.sections[0];s.page_width=Inches(8.5);s.page_height=Inches(11)
    s.left_margin=s.right_margin=Inches(.7);s.top_margin=s.bottom_margin=Inches(.65)
    n=d.styles['Normal'];n.font.name='Arial';n.font.size=Pt(10)
    n._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Arial')
    n.paragraph_format.space_after=Pt(7);n.paragraph_format.line_spacing=1.05
    title_line(d,title);d.add_paragraph(subtitle)
    return d

def title_line(d,text):
    p=d.add_paragraph();r=p.add_run(text);r.bold=True;r.font.size=Pt(16)
    p.paragraph_format.space_after=Pt(10);return p

def table(d,headers,rows,widths):
    t=d.add_table(rows=1,cols=len(headers));t.autofit=False
    for col,width in zip(t.columns,widths):col.width=Cm(width)
    for c,h in zip(t.rows[0].cells,headers):c.text=h
    for row in rows:
        for c,v in zip(t.add_row().cells,row):c.text=str(v)
    for i,row in enumerate(t.rows):
        row._tr.get_or_add_trPr().append(OxmlElement('w:cantSplit'))
        for c,width in zip(row.cells,widths):
            c.width=Cm(width);b=OxmlElement('w:tcBorders')
            for edge in ['top','bottom','left','right']:
                e=OxmlElement('w:'+edge)
                for k,v in [('val','single'),('sz','4'),('color','888888')]:e.set(qn('w:'+k),v)
                b.append(e)
            c._tc.get_or_add_tcPr().append(b)
            for p in c.paragraphs:
                p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4);p.paragraph_format.line_spacing=1
                for r in p.runs:r.font.name='Arial';r.font.size=Pt(9);r.bold=i==0
    t.rows[0]._tr.get_or_add_trPr().append(OxmlElement('w:tblHeader'))
    p=d.add_paragraph();p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0)
    return t

def write_report(out,data):
    d=document('PRODUCT RECALL — ACTION REQUIRED','To: Inventory holders and distribution contacts\nPrepared by: Channel Quality\nInformation available through December 2, 2024')
    d.add_paragraph('Reason for recall: the identified carrot products may contain Shiga toxin-producing E. coli O121:H19. The notice concerns a potential serious health risk; a product need not have a positive laboratory result to fall within the identified recall scope.')
    d.add_paragraph('Please use the attached register to check for affected stock. Stop sale and use of matching products, isolate them, and carry out the disposal or destruction requested in the notices. Clean and sanitize surfaces and containers that contacted the products. Hold unidentified or partly labelled stock separately while Purchasing obtains photographs, purchase records and supplier confirmation.')
    table(d,['Product','Identification to use','Notice'],[
        ['Organic whole carrots','43 brand/pack combinations. Retail sale period: August 14–October 23, 2024. No Best-if-Used-by date on the package.','N01, N02'],
        ['Organic baby carrots','37 brand/pack combinations. Apply each brand’s own Best-if-Used-by dates. Retain the Cal-Organic 2pk/2lbs pack as listed.','N01'],
        ['F&S prepared products','Two 15 oz products. Codes GH236–GH284; Best if sold by September 1–October 19, 2024.','N03'],
        ['4Earth products','Eight distinct products, including organic and conventional vegetable mixes. Best by September 7–November 2, 2024.','N04']],[3.4,12.2,2.4])
    d.add_paragraph(f"The register contains {len(data['scopes'])} identification rules, not stock units or production lots. Actual holdings and disposition quantities remain unconfirmed. Blank UPC fields are retained where the notice did not provide a code.")
    d.add_paragraph('N02 adds four packs to N01: Bunny Luv 50 lb; Cal-Organic 15 lb and 50 lb; and Good & Gather 1 lb. The other N01 products remain in scope. The 2pk/2lbs description has not been interpreted as two separate 2 lb bags. Downstream date windows are kept separately from the upstream retail sale period.')
    d.add_paragraph('N02 records additions to the public notice, not the first date on which those retailers were notified: its account says retailers received all correct pack-size details on November 16. Do not treat November 21 as permission to release earlier matching stock.')
    d.add_paragraph('For the notice log, N02 is dated November 21 and was published November 22; N04 is dated November 26 and was published December 2. The review covers N01–N04 at this historical cutoff. Later notices require a separate update.')
    d.add_page_break();title_line(d,'Distribution checks and outstanding returns')
    table(d,['Business','Documented distribution','Follow-up'],[
        ['F&S','Whole Foods Market; AZ, CA, HI, ID and NV.','Check the two products against holdings, deliveries, sales and returns.'],
        ['4Earth','Nine product/customer relationships, six channels and seven states: NH, FL, CA, PA, MN, IL and CO.','Retain both Albert’s Organics and UNFI for Wild Harvest UPC 711535517733. Walmart covers four Marketside products.'],
        ['Grimmway','N01 describes distribution nationwide in the United States, Puerto Rico and Canada, including supply links to F&S and 4Earth.','The downstream state lists do not restrict the original carrot recall. Check actual customer deliveries; obtain lot and processing records.']],[2.5,7.5,8])
    d.add_paragraph('The two downstream notices give 11 product/channel relationships. A state list describes overall distribution; individual product deliveries require transaction evidence. Wild Harvest is one product with two channel relationships, rather than two distinct products.')
    d.add_paragraph('If you supplied affected products onward, promptly pass the identification and action instructions to those customers, using your delivery records. Ask them to confirm receipt and report their findings. Return your response to the contact that sent you this notice, including an explicit nil holding where checked; do not wait for a positive stock finding before acknowledging receipt.')
    table(d,['Contact','Information needed','Close-out evidence'],[
        ['Stockholders and channels','By product and location: units of measure, count date, quantities held, dispatched, returned and disposed; include refrigerated and frozen stock.','Match identities to the scope register; reconcile quantities to receiving, sales, return and disposition records, with unexplained balances open.'],
        ['Purchasing and processors','Package photographs, supplier confirmation, receiving lots, processing and repacking records.','Unidentified stock and batch relationships resolved.'],
        ['Quality and customer contacts','Isolation logs, disposal or destruction records, and customer acknowledgements.','Disposition and communications verified item by item before closure.']],[3.4,8.1,6.5])
    d.add_paragraph('The attached notices do not include those counts or completion records. Actions remain open. Expiry, an expectation that stock is no longer on sale, or an absence of reported illness does not establish clearance; frozen holdings still need checking under the recall identification rules.')
    d.add_paragraph('Attachments: product-scope.csv, pack-changes.csv and distribution-list.csv. Preparation scripts and instructions are supplied separately under preparation/. This review is not a statement of the entire current market recall position.')
    d.save(out/'trade-recall-notice.docx')
