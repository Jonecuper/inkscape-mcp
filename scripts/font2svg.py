"""Рендер текста как SVG-пути напрямую из TTF (без реестра шрифтов Windows).
fontTools: глиф -> SVGPathPen; позиция по advance; y-флип scale(s,-s)."""
import sys, argparse
from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

def measure_and_paths(ttf, text, size, tracking=0.0):
    f=TTFont(ttf)
    cmap=f.getBestCmap(); gs=f.getGlyphSet(); upem=f['head'].unitsPerEm
    hmtx=f['hmtx']
    s=size/upem
    x=0.0; items=[]
    for ch in text:
        gname=cmap.get(ord(ch))
        if gname is None: continue
        pen=SVGPathPen(gs)
        tpen=TransformPen(pen, (s,0,0,-s,x,0))
        try:
            gs[gname].draw(tpen)
        except Exception:
            # composite через рекурсивный pen не нужен: gs.draw уже раскрывает
            raise
        adv,_=hmtx[gname]
        d=pen.getCommands()
        if d and d.strip(): items.append(d)
        x+=adv*s+tracking
    return x-tracking, items

def svg_word(ttf, text, size, cx, baseline, tracking=0.0, extra=''):
    w,paths=measure_and_paths(ttf,text,size,tracking)
    ox=cx-w/2
    body=''.join(f'<path d="{p}"{extra}/>' for p in paths)
    return f'<g transform="translate({round(ox,3)},{round(baseline,3)})">{body}</g>', w

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--ttf'); ap.add_argument('--text'); ap.add_argument('--size',type=float)
    ap.add_argument('--cx',type=float); ap.add_argument('--baseline',type=float)
    ap.add_argument('--fill',default='#000')
    ap.add_argument('--out')
    a=ap.parse_args()
    g,_=svg_word(a.ttf,a.text,a.size,a.cx,a.baseline)
    g=g.replace('><path',f' fill="{a.fill}"><path',1)
    open(a.out,'w',encoding='utf-8').write(g)
    print('wrote',a.out)
