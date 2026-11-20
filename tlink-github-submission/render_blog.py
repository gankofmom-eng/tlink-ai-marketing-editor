"""Render a case article from portable Markdown to offline HTML and PDF.

Usage: python render_blog.py outputs/tlink-blog.md --brand 티링크 --label '영업팀 활용 예시'
Dependencies: Pillow, PyMuPDF, ReportLab. Supported blocks: H1, H2, paragraph,
blockquote and standalone Markdown image followed by an italic caption.
"""
import argparse
import base64
import html
import io
import mimetypes
import re
from pathlib import Path

import fitz
from PIL import Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (Image as PdfImage, KeepTogether, Paragraph, SimpleDocTemplate,
                                Spacer, Table, TableStyle)

IMAGE = re.compile(r'^!\[([^\]]+)\]\(([^)]+)\)$')
LINK = re.compile(r'\[([^\]]+)\]\((https?://[^\s)]+)\)')
CSS = """
*{box-sizing:border-box}body{margin:0;background:#f4f2ed;color:#182725;font:17px/1.8 system-ui,'Malgun Gothic',sans-serif;word-break:keep-all;overflow-wrap:anywhere}
header{background:#133e38;color:#fff;padding:25px max(6%,calc((100% - 1050px)/2)) 44px;border-top:7px solid #edb870}
nav{border-bottom:1px solid #ffffff50;padding-bottom:15px;display:flex;justify-content:space-between;gap:18px;color:#d4eee3;letter-spacing:.05em;font-size:.84em;font-weight:650}
.hero{display:grid;grid-template-columns:1.65fr 1fr;align-items:center;gap:6%;margin-top:28px}.hero.single{display:block}
h1{font-size:clamp(32px,4.3vw,58px);line-height:1.22;letter-spacing:-.055em;margin:0}h1 small{display:block;font-size:.34em;line-height:1.6;letter-spacing:0;color:#c6e0d6;margin-top:18px}
main{max-width:840px;margin:auto;background:white;padding:36px clamp(20px,5vw,60px) 55px}
p{margin:12px 0 18px}.lead{font-size:1.12em;line-height:1.85}h2{font-size:clamp(23px,3vw,31px);line-height:1.42;border-top:2px solid #286756;margin:37px 0 16px;padding-top:18px;letter-spacing:-.045em}
figure{padding:15px;margin:20px 0;background:#eef3f0;border-radius:10px;text-align:center}figure img{display:block;margin:auto;max-width:100%;height:auto;max-height:480px;object-fit:contain}figcaption{margin-top:10px;font-size:.83em;text-align:left;color:#425451}
.hero figure{background:#ffffff12;margin:0}.hero img{max-height:230px;border-radius:5px}.hero figcaption,.hero a{color:#e4eee8}.hero figcaption{font-size:.75em}
blockquote{border-left:4px solid #dba657;background:#fffaef;padding:13px 20px;margin:20px 0}a{color:#14614f;text-underline-offset:3px}footer{font-size:.8em;color:#68736d;border-top:1px solid #c5d3ca;margin-top:35px;padding-top:12px}
@media(max-width:650px){.hero{grid-template-columns:1fr;gap:20px}.hero img{max-height:205px}header{padding:18px 20px 24px}main{padding-top:21px}}
@media print{body{background:white}header{print-color-adjust:exact}figure{break-inside:avoid}}
"""

def inline(value, pdf=False):
    # Protect escaped literal stars before applying Markdown emphasis.
    val = html.escape(value.replace(r'\*', '\uE000'), quote=True)
    val = LINK.sub(lambda m: '<a href="'+m[2]+'">'+m[1]+'</a>', val)
    val = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', val)
    val = re.sub(r'\*([^*]+)\*', r'\1' if pdf else r'<em>\1</em>', val)
    return val.replace('\uE000','*')

def read_article(path):
    parts = re.split(r'\n\s*\n', path.read_text(encoding='utf-8').strip())
    if not parts or not parts[0].startswith('# '):
        raise ValueError('The first paragraph must be an H1.')
    title = parts.pop(0)[2:].strip()
    blocks = []
    i = 0
    while i < len(parts):
        txt = parts[i].strip()
        img = IMAGE.fullmatch(txt)
        if img:
            f = (path.parent / img[2]).resolve()
            with Image.open(f) as im:
                im.load()
                # Normalizing formats makes WebP and transparent inputs portable in both exports.
                im.thumbnail((1800,1800))
                buf = io.BytesIO()
                bg = Image.new('RGB',im.size,'white')
                rgba=im.convert('RGBA')
                bg.paste(rgba,mask=rgba.getchannel('A'))
                bg.save(buf, 'PNG' if im.format!='JPEG' else 'JPEG')
                data=buf.getvalue()
                mime='image/png' if im.format!='JPEG' else 'image/jpeg'
                size=bg.size
            if i+1 >= len(parts) or not parts[i+1].startswith('*'):
                raise ValueError(f'Missing caption for {f.name}')
            i+=1
            blocks.append(('figure', (img[1],data,mime,size,parts[i])))
        elif txt.startswith('## '): blocks.append(('h2',txt[3:]))
        elif txt.startswith('> '): blocks.append(('quote',txt[2:]))
        else: blocks.append(('p',txt))
        i+=1
    return title,blocks

def render(path,brand,label):
    title,blocks=read_article(path)
    hero=next((v for k,v in blocks if k=='figure'),None)
    main,sep,sub=title.partition(' | ')
    def html_figure(f):
        alt,data,mime,_,cap=f
        src='data:'+mime+';base64,'+base64.b64encode(data).decode('ascii')
        return '<figure><img alt="'+html.escape(alt,quote=True)+'" src="'+src+'"><figcaption>'+inline(cap)+'</figcaption></figure>'
    b=html.escape(brand); lab=html.escape(label)
    page=['<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+html.escape(main)+'</title><style>'+CSS+'</style><header><nav><span>'+b+'</span><span>'+lab+'</span></nav><div class="hero'+('' if hero else ' single')+'"><h1>'+inline(main)+('<small>'+inline(sub)+'</small>' if sep else '')+'</h1>'+ (html_figure(hero) if hero else '')+'</div></header><main>']
    for idx,(k,v) in enumerate(blocks):
        if k=='figure':
            if v is not hero: page.append(html_figure(v))
        else:
            tag={'p':'p','h2':'h2','quote':'blockquote'}[k]
            page.append('<'+tag+(' class="lead"' if idx==0 else '')+'>'+inline(v)+'</'+tag+'>')
    page.append('<footer>'+b+' · '+lab+'</footer></main></html>')
    path.with_suffix('.html').write_text(''.join(page),encoding='utf-8')
    pdfmetrics.registerFont(TTFont('BodyK',io.BytesIO(fitz.Font('korea').buffer)))
    pdfmetrics.registerFontFamily('BodyK',normal='BodyK',bold='BodyK',italic='BodyK',boldItalic='BodyK')
    green='#164b41'; tone='#1c2e2a'
    def para(v,size=10.4,leading=17,ink=tone,after=8,before=0,keep=False):
        st=ParagraphStyle('article',fontName='BodyK',fontSize=size,leading=leading,textColor=colors.HexColor(ink),spaceAfter=after,spaceBefore=before,wordWrap=None,alignment=TA_LEFT,keepWithNext=keep)
        return Paragraph(inline(v,True),st)
    doc=SimpleDocTemplate(str(path.with_suffix('.pdf')),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=48,bottomMargin=46,title=title,author=brand)
    width=doc.width-12
    def pic(f,w,h):
        _,data,_,(iw,ih),_=f; scale=min(w/iw,h/ih)
        return PdfImage(io.BytesIO(data),width=iw*scale,height=ih*scale,hAlign='CENTER')
    def card(data,widths,bg,pad):
        t=Table(data,colWidths=widths,hAlign='LEFT')
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor(bg)),('VALIGN',(0,0),(-1,-1),'MIDDLE'),('ALIGN',(0,0),(-1,-1),'CENTER'),*[(k,(0,0),(-1,-1),pad) for k in ('LEFTPADDING','RIGHTPADDING','TOPPADDING','BOTTOMPADDING')]]))
        return t
    left=[para(main,24,33,'#ffffff',9)]
    if sub:left.append(para(sub,9.5,14,'#d4e5db',0))
    if hero:
        story=[card([[left,pic(hero,width*.31-16,127)]],[width*.65,width*.35],green,12),Spacer(1,5),para(hero[4],8,12,'#52675e',7)]
    else:story=[card([[left]],[width],green,14)]
    for idx,(k,v) in enumerate(blocks):
        if k=='h2': story.append(para(v,16,23,green,7,11,True))
        elif k=='p':story.append(para(v,11 if idx==0 else 10.4,18 if idx==0 else 17))
        elif k=='quote':story.extend([card([[para(v,10,16,tone,0)]],[width],'#fff2d8',10),Spacer(1,9)])
        elif v is not hero:
            story.append(KeepTogether([card([[pic(v,width-32,153)]],[width],'#edf3ef',7),Spacer(1,4),para(v[4],8.8,13,'#52675e',9)]))
    def decorate(c,d):
        w,h=A4
        c.setFont('BodyK',9);c.setFillColor(colors.HexColor(green));c.drawString(44,h-28,brand);c.drawRightString(w-44,h-28,label)
        c.setStrokeColor(colors.HexColor('#b7c9be'));c.line(44,34,w-44,34)
        c.setFont('BodyK',8);c.drawRightString(w-44,20,str(d.page))
    doc.build(story,onFirstPage=decorate,onLaterPages=decorate)
    expected=sum(k=='figure' for k,v in blocks)
    with fitz.open(path.with_suffix('.pdf')) as pdf:
        visible=sum(len(p.get_image_info()) for p in pdf)
        if visible!=expected: raise ValueError(f'PDF contains {visible} of {expected} images.')
        print(f'{len(pdf)} PDF pages, {visible} embedded images. HTML images: {expected}.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('article',type=Path)
    parser.add_argument('--brand',required=True)
    parser.add_argument('--label',default='활용 예시')
    args=parser.parse_args()
    render(args.article.resolve(),args.brand,args.label)
