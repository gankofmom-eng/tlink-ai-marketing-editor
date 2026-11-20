"""Render channel-specific Korean promotional drafts from an approved content brief.
Run: python render_channels.py instagram|email brief.json --out RUN_DIRECTORY
Outputs: RUN_DIRECTORY/instagram/ or RUN_DIRECTORY/email/. Images are relative to brief.json.
"""
import argparse
import base64
from email import policy
from email.message import EmailMessage
from email.utils import make_msgid
from functools import lru_cache
from html import escape
import io
import json
from pathlib import Path
import tempfile
from urllib.parse import urlparse

import fitz
from PIL import Image, ImageDraw, ImageFont, ImageOps


INK = '#173b3e'
MINT = '#b1e4ca'
PAPER = '#f5f1e8'
RUST = '#be5034'
WIDTH, HEIGHT = 1080, 1350


@lru_cache(maxsize=64)
def font(size, bold=False):
    weight = 'Bold' if bold else 'Regular'
    path = Path(f'/usr/share/fonts/opentype/noto/NotoSansCJK-{weight}.ttc')
    if path.is_file():
        return ImageFont.truetype(str(path), size, index=1)
    return ImageFont.truetype(io.BytesIO(fitz.Font('korea').buffer), size)


def wrap(value, face, width):
    lines = []
    for paragraph in value.splitlines():
        line = ''
        for word in paragraph.split():
            attempt = (line+' '+word).strip()
            if face.getlength(attempt) <= width:
                line = attempt
                continue
            if line:
                lines.append(line)
            line = ''
            for char in word:
                if line and face.getlength(line+char) > width:
                    lines.append(line)
                    line = ''
                line += char
        if line:
            lines.append(line)
    return lines


def block(draw, value, box, size, minimum, color, bold=False):
    x,y,right,bottom = box
    for points in range(size, minimum-1, -2):
        face = font(points, bold)
        lines = wrap(value, face, right-x)
        leading = round(points*1.4)
        if leading*len(lines) <= bottom-y:
            for line in lines:
                draw.text((x,y),line,font=face,fill=color,anchor='lt')
                y += leading
            return
    raise ValueError('문구가 영역보다 깁니다. 문장을 줄이세요: '+value)


def read_image(base, asset):
    if not asset.get('alt','').strip() or not asset.get('credit','').strip():
        raise ValueError('사진에는 대체텍스트와 출처 설명이 필요합니다.')
    with Image.open(base / asset['file']) as source:
        return ImageOps.exif_transpose(source).convert('RGB')


def verify_refs(refs, sources):
    if not isinstance(refs,list) or not refs or any(key not in sources for key in refs):
        raise ValueError(f'출처/활용 예시 식별자를 확인하세요: {refs}')


def safe_url(url):
    parts=urlparse(url)
    if parts.scheme not in ('http','https') or not parts.netloc:
        raise ValueError('공식 문의 URL을 확인하세요.')
    return url


def render_card(brand, card, number, total, base):
    dark = number in (1,total)
    bg = INK if dark else PAPER
    fg = '#ffffff' if dark else INK
    accent = MINT if dark else RUST
    canvas=Image.new('RGB',(WIDTH,HEIGHT),bg)
    d=ImageDraw.Draw(canvas)
    block(d,brand,(74,65,820,135),36,26,accent,True)
    d.text((1002,70),f'{number:02} / {total:02}',fill=accent,font=font(27),anchor='rt')
    d.line((74,146,1006,146),fill=accent,width=2)
    if 'image' in card:
        block(d,card['headline'],(72,212,1006,482),77,49,fg,True)
        block(d,card['body'],(76,510,1000,723),41,32,fg)
        image=read_image(base,card['image'])
        panel=(74,744,1006,1168)
        d.rounded_rectangle(panel,radius=24,fill='#335654' if dark else '#dfe8e0')
        inner=(panel[2]-panel[0]-32,panel[3]-panel[1]-32)
        placed=ImageOps.contain(image,inner,method=Image.Resampling.LANCZOS)
        canvas.paste(placed,(panel[0]+(panel[2]-panel[0]-placed.width)//2,panel[1]+(panel[3]-panel[1]-placed.height)//2))
        block(d,card['image']['credit'],(76,1198,1006,1322),27,22,accent)
    else:
        block(d,card['headline'],(72,243,1006,700),88,56,fg,True)
        d.rectangle((76,758,180,769),fill=accent)
        block(d,card['body'],(76,838,1000,1250),48,34,fg)
    return canvas


def uri(mime, data):
    return 'data:'+mime+';base64,'+base64.b64encode(data).decode('ascii')


def mark_row(location, content, refs, sources):
    def cell(s):
        return str(s).replace('|',r'\|').replace('\n',' ')
    return '| '+' | '.join(cell(v) for v in (
        location, content, ' / '.join(sources[k] for k in refs)))+' |'


def create_social(brief, stage, base):
    social=brief['instagram']
    cards=social['cards']
    if len(cards)!=5:
        raise ValueError('카드 5장의 문구가 필요합니다.')
    sources=brief['sources']
    caption=social['caption'].strip()
    verify_refs(social['refs'],sources)
    alt_lines=[]
    proof=[]
    gallery=[]
    for i,card in enumerate(cards,1):
        verify_refs(card['refs'],sources)
        if not card['headline'].strip() or not card['body'].strip():
            raise ValueError('각 카드에 제목과 본문이 필요합니다.')
        filename=f'card-{i:02}.png'
        target=stage/filename
        render_card(brief['brand'],card,i,len(cards),base).save(target)
        with Image.open(target) as image:
            image.verify()
        alt=card['headline']+' '+card['body']
        if 'image' in card:
            alt+=' '+card['image']['alt']+' '+card['image']['credit']
        alt_lines.append(f'{i}장. {alt}')
        proof.append(mark_row(f'{i}장',alt,card['refs'],sources))
        src=uri('image/png',target.read_bytes())
        gallery.append(f'<figure><img src="{src}" alt="{escape(alt,quote=True)}"><figcaption><a download="{filename}" href="{src}">{i}장 PNG 저장</a></figcaption></figure>')
    proof.append(mark_row('게시문',caption,social['refs'],sources))
    copy=caption+'\n\n대체텍스트\n'+'\n\n'.join(alt_lines)+'\n'
    (stage/'caption.txt').write_text(copy,encoding='utf-8')
    copy_url=uri('text/plain;charset=utf-8',copy.encode())
    html='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>카드뉴스</title><style>*{box-sizing:border-box}body{margin:30px auto;padding:0 18px;max-width:950px;background:#f5f1e8;color:#173b3e;font:16px/1.5 system-ui}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,255px),1fr));gap:24px 14px}figure{margin:0}img{display:block;width:100%;height:auto}a{color:#155448}figcaption{padding-top:7px}p{white-space:pre-line}</style>'''
    (stage/'cardnews.html').write_text(html+'<h1>'+escape(brief['brand'])+' 카드뉴스</h1><main>'+''.join(gallery)+'</main><h2>게시문</h2><p>'+escape(caption)+'</p><a download="caption.txt" href="'+copy_url+'">게시문과 장별 대체텍스트 저장</a></html>',encoding='utf-8')
    return proof


def create_email(brief, stage, base):
    data=brief['email']
    sources=brief['sources']
    verify_refs(data['refs'],sources)
    paragraphs=data['paragraphs']
    if not 1<=len(paragraphs)<=5 or not all(isinstance(p,str) and p.strip() for p in paragraphs):
        raise ValueError('메일 본문을 1~5개 문단으로 작성하세요.')
    for key in ('subject','preheader','title','cta','url'):
        if not data[key].strip():
            raise ValueError('이메일 필드 누락: '+key)
    safe_url(data['url'])
    msg=EmailMessage(policy=policy.SMTP)
    msg['Subject']=data['subject']
    msg['X-Unsent']='1'
    photo=data.get('image')
    brand=brief['brand']
    plain=data['title']+'\n\n'+'\n\n'.join(paragraphs)+'\n\n'+data['cta']+'\n'+data['url']+'\n\n'+brand
    if photo:
        plain+='\n'+photo['credit']
    plain+='\n'
    msg.set_content(plain)
    cid=make_msgid(domain='assets.local') if photo else None
    jpeg=b''
    if photo:
        im=read_image(base,photo);im.thumbnail((1000,800))
        buf=io.BytesIO();im.save(buf,'JPEG',quality=89);jpeg=buf.getvalue()
    def template(src):
        top='<div style="display:none;max-height:0;overflow:hidden;mso-hide:all">'+escape(data['preheader'])+'</div>'
        pic=''
        if photo:
            pic='<tr><td style="padding:0 32px 22px"><img width="220" style="display:block;max-width:100%;height:auto" src="'+src+'" alt="'+escape(photo['alt'],quote=True)+'"><p style="font-size:13px;color:#45615d">'+escape(photo['credit'])+'</p></td></tr>'
        body=''.join('<p style="margin:0 0 16px">'+escape(p)+'</p>' for p in paragraphs)
        return ('<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>'+escape(data['subject'])+'</title></head><body style="margin:0;background:#f3f2ed;font-family:Arial,Malgun Gothic,sans-serif;color:#173b3e">'+top+
                '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:20px 8px"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;background:#fff;text-align:left"><tr><td style="padding:30px 32px;background:#173b3e;color:white"><p style="margin:0 0 15px;color:#b1e4ca">'+escape(brand)+'</p><h1 style="margin:0;font-size:29px;line-height:1.4">'+escape(data['title'])+'</h1></td></tr><tr><td style="padding:26px 32px 8px;font-size:16px;line-height:1.75">'+body+'</td></tr>'+pic+
                '<tr><td style="padding:0 32px 32px"><a href="'+escape(data['url'],quote=True)+'" style="display:inline-block;background:#165449;color:#fff;padding:12px 20px;text-decoration:none;font-weight:bold">'+escape(data['cta'])+'</a></td></tr></table></td></tr></table></body></html>')
    msg.add_alternative(template('cid:'+cid[1:-1] if photo else ''),subtype='html')
    if photo:
        msg.get_payload()[-1].add_related(jpeg,maintype='image',subtype='jpeg',cid=cid,disposition='inline',filename='field.jpg')
    (stage/'intro.eml').write_bytes(msg.as_bytes())
    (stage/'intro.html').write_text(template(uri('image/jpeg',jpeg) if photo else ''),encoding='utf-8')
    (stage/'intro.txt').write_text('제목: '+data['subject']+'\n미리보기: '+data['preheader']+'\n\n'+plain,encoding='utf-8')
    return [mark_row('제목·미리보기·본문·문의',data['subject']+' / '+data['preheader']+' / '+plain,data['refs'],sources)]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('channel',choices=['instagram','email'])
    parser.add_argument('brief',type=Path)
    parser.add_argument('--out',required=True,type=Path)
    args=parser.parse_args()
    brief=json.loads(args.brief.read_text(encoding='utf-8'))
    output=args.out/args.channel
    output.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as temp:
        stage=Path(temp)
        build=create_social if args.channel=='instagram' else create_email
        rows=build(brief,stage,args.brief.resolve().parent)
        audit='# '+brief['brand']+' · '+args.channel+' 표현 검수\n\n| 위치 | 최종 문구 | 대조 자료·조건 |\n|---|---|---|\n'
        (stage/'check.md').write_text(audit+'\n'.join(rows)+'\n',encoding='utf-8')
        for item in stage.iterdir():
            item.replace(output/item.name)

if __name__=='__main__':
    main()
