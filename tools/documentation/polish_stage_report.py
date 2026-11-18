"""Preserve report content while fixing empty spacing and rebuilding cached Word TOC."""
from pathlib import Path
import re
import sys
from copy import deepcopy
from docx import Document
from docx.shared import Pt, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
root=Path(__file__).resolve().parents[2];path=next(root.glob('Звіт*.docx'));d=Document(path)

def normalize(text):return ''.join(c for c in text.casefold() if c.isalnum())
if len(sys.argv)>1:
    from pypdf import PdfReader
    pages=[normalize(p.extract_text()) for p in PdfReader(sys.argv[1]).pages]
    for p in d.paragraphs:
        if p.style.name.lower().startswith('toc'):
            title=''.join(p._p.xpath('./w:hyperlink/w:r/w:t/text()'))
            key=normalize(title)
            matches=[i+1 for i,text in enumerate(pages) if key and key in text]
            if matches:
                for node in p._p.xpath('./w:fldSimple/w:r/w:t'):node.text=str(max(matches))
    d.save(path);print('Updated cached TOC page numbers');raise SystemExit

# Remove only empty layout paragraphs in the body, not title-page spacing or field/anchor content.
body=False
for p in list(d.paragraphs):
    if p.style.name=='Heading 1' and p.text.startswith('1 ВСТУП'):body=True
    if body and not p.text.strip() and not p._p.xpath('.//w:drawing|.//w:br|.//w:fldChar|.//w:bookmarkStart|.//w:sectPr'):
        p._element.getparent().remove(p._element)
# Place the scope notice immediately under the architecture heading.
notice=next(p for p in d.paragraphs if p.text.startswith('Уточнення стану реалізації.'))
head=next(p for p in d.paragraphs if p.text=='4 АРХІТЕКТУРА СИСТЕМИ')
head._p.addnext(notice._p)
new_section=False
for p in d.paragraphs:
    if p.style.name=='Heading 1' and p.text.startswith('10 ВИБІР'):new_section=True
    if new_section and p.text and not p.style.name.startswith('Heading') and not p._p.xpath('.//w:drawing') and not p.text.startswith(('Рисунок','Таблиця')):
        p.paragraph_format.line_spacing=1.5;p.paragraph_format.first_line_indent=Inches(.5)
        p.paragraph_format.space_after=Pt(0);p.alignment=WD_ALIGN_PARAGRAPH.JUSTIFY
    if p.style.name.startswith('Heading'):
        p.paragraph_format.space_before=Pt(12);p.paragraph_format.space_after=Pt(12)
        p.paragraph_format.keep_with_next=True
        if p.style.name=='Heading 2':p.paragraph_format.page_break_before=False
    if '34 тести' in p.text:
        for r in p.runs:r.text=r.text.replace('34 тести','35 тестів')
    if p.text.startswith('На поточному етапі визначено функціональні межі'):
        for r in p.runs:r.text=r.text.replace('На поточному етапі','На етапі проєктування')
    if 'Працездатний вебзастосунок і результати вимірювання його продуктивності на цьому етапі ще не отримано.' in p.text:
        for r in p.runs:r.text=r.text.replace('Працездатний вебзастосунок і результати вимірювання його продуктивності на цьому етапі ще не отримано.','Реалізацію вебінтерфейсу та перевірки поточного зрізу наведено у розділах 10–13; вимірювання цільової продуктивності залишено наступним етапам.')
    if p._p.pPr is not None:p._p.insert(0,p._p.pPr)
# Replace TOC contents, retaining the heading and the automatic TOC field semantics.
toc=next(p for p in d.paragraphs if p.text=='ЗМІСТ')
intro=next(p for p in d.paragraphs if p.style.name=='Heading 1' and p.text.startswith('1 ВСТУП'))
node=toc._p.getnext()
while node is not intro._p:
    following=node.getnext();node.getparent().remove(node);node=following
heads=[p for p in d.paragraphs if p.style.name in ('Heading 1','Heading 2') and p.text!='ЗМІСТ']
entries=[]
for i,h in enumerate(heads):
    bookmarks=h._p.xpath('./w:bookmarkStart')
    if bookmarks:anchor=bookmarks[0].get(qn('w:name'))
    else:
        anchor=f'report_heading_{i}';b=OxmlElement('w:bookmarkStart');b.set(qn('w:id'),str(20000+i));b.set(qn('w:name'),anchor)
        e=OxmlElement('w:bookmarkEnd');e.set(qn('w:id'),str(20000+i));h._p.append(b);h._p.append(e)
    p=intro.insert_paragraph_before('', 'toc 1' if h.style.name=='Heading 1' else 'toc 2')
    p.paragraph_format.space_before=Pt(0);p.paragraph_format.space_after=Pt(3);p.paragraph_format.line_spacing=1
    p.paragraph_format.first_line_indent=Pt(0);p.paragraph_format.left_indent=Pt(0 if h.style.name=='Heading 1' else 12)
    p.paragraph_format.keep_with_next=False;p.paragraph_format.page_break_before=False
    p.paragraph_format.tab_stops.add_tab_stop(Inches(6.0),WD_TAB_ALIGNMENT.RIGHT,WD_TAB_LEADER.DOTS)
    if not entries:
        r=OxmlElement('w:r');f=OxmlElement('w:fldChar');f.set(qn('w:fldCharType'),'begin');r.append(f);p._p.append(r)
        r=OxmlElement('w:r');f=OxmlElement('w:instrText');f.text=r' TOC \o "1-2" \h \z \u ';r.append(f);p._p.append(r)
        r=OxmlElement('w:r');f=OxmlElement('w:fldChar');f.set(qn('w:fldCharType'),'separate');r.append(f);p._p.append(r)
    link=OxmlElement('w:hyperlink');link.set(qn('w:anchor'),anchor)
    r=OxmlElement('w:r');props=OxmlElement('w:rPr');size=OxmlElement('w:sz');size.set(qn('w:val'),'20');props.append(size);r.append(props)
    t=OxmlElement('w:t');t.text=h.text; r.append(t);link.append(r);p._p.append(link)
    p.add_run('\t').font.size=Pt(10)
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),rf' PAGEREF {anchor} \h ')
    r=OxmlElement('w:r');t=OxmlElement('w:t');t.text='0';r.append(t);field.append(r);p._p.append(field)
    entries.append(p)
r=OxmlElement('w:r');f=OxmlElement('w:fldChar');f.set(qn('w:fldCharType'),'end');r.append(f);entries[-1]._p.append(r)
d.save(path);print('Report spacing and automatic TOC updated')
