"""Эталонный пример «доводки» ручной векторизации надписи:
1) полигональные заглавные (метки redI/redT) -> скругление выпуклых углов истинными дугами
2) острые прямоугольные «дефисы» (redDefis) -> явная капсула из 4 дуг
3) склеенный путь мелкого кегля (redCluster) -> нормализация pen-state, разбивка на глифы,
   счётчики (counter) группируются с родителем, каждый глиф = отдельный <path>,
   translate к эталонным bbox букв
4) перекраска групп; подложка-эталон удаляется
Использование: python -I build_final.py [вход.svg] [выход.svg] (умолч. input.red.svg -> input.new.svg)
Пути к файлам, размеры канваса, REF-bbox и подписи слоёв — подстроить под свой кейс.
Ключевые переносимые части: normalize_subpaths (полный pen-state), fillet, capsule,
flatten-без-потерь сериализация seralize()."""
import re, math, sys

SRC=sys.argv[1] if len(sys.argv)>1 else 'input.red.svg'
OUT=sys.argv[2] if len(sys.argv)>2 else SRC.rsplit('.',1)[0]+'.new.svg'
R_CAP=2.8   # радиус скругления заглавных, в единицах канваса

# ---------- мини-парсер path ----------
def tokenize(d):
    toks=re.findall(r'[MmHhVvLlQqTtSsCcZz]|-?[\d.]+(?:e-?\d+)?',d)
    return toks
def to_abs_polys(d):
    """список замкнутых полилиний [(x,y)...] только если путь состоит из прямых"""
    toks=tokenize(d); polys=[]; i=0
    cx=cy=0.0; px=py=0.0; cur=[]; ok=True
    while i<len(toks):
        if re.match(r'[A-Za-z]',toks[i]): c=toks[i]; i+=1
        else: c='L' if (cur and c in 'mM') else c  # implicit lineto
        if c in 'zZ':
            if cur: polys.append(cur); cur=[]
            cx,cy=px,py
            if c=='Z': px,py=cx,cy
            continue
        if c in 'mM':
            if cur: ok=False
            x,y=float(toks[i]),float(toks[i+1]); i+=2
            if c=='m': x+=cx; y+=cy
            cx,cy=x,y; px,py=cx,cy; cur=[(cx,cy)]
            # implicit lineto pairs
            while i+1<len(toks) and not re.match(r'[A-Za-z]',toks[i]):
                nx,ny=float(toks[i]),float(toks[i+1])
                if c=='m': nx+=cx; ny+=cy
                cx,cy=nx,ny; cur.append((cx,cy))
                i+=2
            px,py=cur[0]
        elif c in 'lL':
            while i+1<len(toks) and not re.match(r'[A-Za-z]',toks[i]):
                nx,ny=float(toks[i]),float(toks[i+1]); i+=2
                if c=='l': nx+=cx; ny+=cy
                cx,cy=nx,ny; cur.append((cx,cy))
        elif c in 'hH':
            while i<len(toks) and not re.match(r'[A-Za-z]',toks[i]):
                nx=float(toks[i]); i+=1
                if c=='h': nx+=cx
                cx=nx; cur.append((cx,cy))
        elif c in 'vV':
            while i<len(toks) and not re.match(r'[A-Za-z]',toks[i]):
                ny=float(toks[i]); i+=1
                if c=='v': ny+=cy
                cy=ny; cur.append((cx,cy))
        else:
            ok=False; break
    if cur and len(cur)>1 and not polys: polys.append(cur)
    return polys if ok and all(polys) else None
def bbox(pts):
    xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
    return min(xs),min(ys),max(xs),max(ys)
def area(poly):
    s=0
    n=len(poly)
    for i in range(n):
        x1,y1=poly[i]; x2,y2=poly[(i+1)%n]
        s+=x1*y2-x2*y1
    return s/2

def fillet(poly,r):
    n=len(poly); out=[]
    for i in range(n):
        p_prev=poly[(i-1)%n]; p=poly[i]; p_next=poly[(i+1)%n]
        v1=(p[0]-p_prev[0],p[1]-p_prev[1]); v2=(p_next[0]-p[0],p_next[1]-p[1])
        l1=math.hypot(*v1); l2=math.hypot(*v2)
        if l1<1e-9 or l2<1e-9: out.append(('L',p)); continue
        cosang=(v1[0]*v2[0]+v1[1]*v2[1])/(l1*l2)
        cosang=max(-1,min(1,cosang))
        ang=math.acos(cosang)          # 0 = прямо, pi = разворот
        if ang<0.12:  # ~7° — угол почти прямой, не трогаем
            out.append(('L',p)); continue
        theta=math.pi-ang              # экстерьер
        t=r/math.tan(theta/2) if theta>1e-3 else 0
        t=min(t,0.45*l1,0.45*l2)
        if t<0.05:
            out.append(('L',p)); continue
        a=(p[0]-v1[0]/l1*t, p[1]-v1[1]/l1*t)
        b=(p[0]+v2[0]/l2*t, p[1]+v2[1]/l2*t)
        cross=v1[0]*v2[1]-v1[1]*v2[0]
        sweep=1 if cross>0 else 0      # y-down: positive cross = clockwise turn
        out.append(('P',a)); out.append(('A',r,r,sweep,b))
    return out
def emit_filleted(poly,r):
    segs=fillet(poly,r)
    outd=''
    for seg in segs:
        if seg[0]=='P':
            outd+=f" L {seg[1][0]:.3f} {seg[1][1]:.3f}"
        elif seg[0]=='A':
            outd+=f" A {seg[1]:.3f} {seg[1]:.3f} 0 0 {seg[3]} {seg[4][0]:.3f} {seg[4][1]:.3f}"
        elif seg[0]=='L':
            outd+=f" L {seg[1][0]:.3f} {seg[1][1]:.3f}"
    first=segs[0]
    p0=first[1] if first[0]!='A' else first[3]
    return f'M {p0[0]:.3f} {p0[1]:.3f}'+outd+' Z'
def capsule(x0,y0,x1,y1):
    r=(y1-y0)/2
    return (f'M {x0+r:.3f} {y0:.3f} L {x1-r:.3f} {y0:.3f} '
            f'A {r:.3f} {r:.3f} 0 0 1 {x1:.3f} {y0+r:.3f} L {x1:.3f} {y1-r:.3f} '
            f'A {r:.3f} {r:.3f} 0 0 1 {x1-r:.3f} {y1:.3f} L {x0+r:.3f} {y1:.3f} '
            f'A {r:.3f} {r:.3f} 0 0 1 {x0:.3f} {y1-r:.3f} L {x0:.3f} {y0+r:.3f} '
            f'A {r:.3f} {r:.3f} 0 0 1 {x0+r:.3f} {y0:.3f} Z')

def normalize_subpaths(d):
    """полный честный парсер: -> [ [(cmd, abs params...)] ], плюс bbox субпути.
    Поддерживает MmLlHhVvQqTtZz + implicit lineto; всё в абсолют."""
    toks=tokenize(d); subs=[]; cur=[]
    cx=cy=sx=sy=0.0; c=None
    def pairs(nums,k,step):
        res=[]
        while k+step<=len(nums):
            res.append(nums[k:k+step]); k+=step
        return res,k
    i=0
    while i<len(toks):
        t=toks[i]
        if re.match(r'[A-Za-z]',t): c=t; i+=1
        if c is None: break
        if c in 'zZ':
            cx,cy=sx,sy; cur.append(('Z',))
            if c=='Z': c='L' if False else c
            subs.append(cur); cur=[]
            i_start=True
            c=None
            continue
        nums=[]
        while i<len(toks) and not re.match(r'[A-Za-z]',toks[i]): nums.append(float(toks[i])); i+=1
        rel=c.islower(); C=c.upper()
        k=0
        if C in ('M','L','T'):
            step=2; first=True
            while k+2<=len(nums):
                a,b=nums[k],nums[k+1]; k+=2
                ax=a+(cx if rel else 0); by=b+(cy if rel else 0)
                if C=='M' and first:
                    cur=[('M',ax,by)]
                    sx,sy=ax,by
                    first=False
                elif C=='T':
                    cur.append(('Q',cx,cy,ax,by))  # smooth quad: reflection needed ideally
                else:
                    cur.append(('L',ax,by))
                cx,cy=ax,by
            if C=='M' and not cur: continue
            # implicit lineto after M:
            if C=='M':
                while k+2<=len(nums):
                    a,b=nums[k],nums[k+1]; k+=2
                    ax=a+(sx if rel else 0); by=b+(sy if rel else 0)
                    cur.append(('L',ax,by)); cx,cy=ax,by
        elif C=='H':
            for a in nums:
                ax=a+(cx if rel else 0); cur.append(('L',ax,cy)); cx=ax
        elif C=='V':
            for b in nums:
                by=b+(cy if rel else 0); cur.append(('L',cx,by)); cy=by
        elif C=='Q':
            while k+4<=len(nums):
                x1=nums[k]+(cx if rel else 0); y1=nums[k+1]+(cy if rel else 0)
                x2=nums[k+2]+(cx if rel else 0); y2=nums[k+3]+(cy if rel else 0)
                cur.append(('Q',x1,y1,x2,y2)); cx,cy=x2,y2; k+=4
        else:
            raise ValueError('cmd '+c)
    if cur: subs.append(cur)
    def sbb(s):
        pts=[]
        for seg in s:
            if seg[0]=='Z': continue
            if seg[0]=='Q': pts+=[(seg[1],seg[2]),(seg[3],seg[4])]
            else: pts.append((seg[1],seg[2]))
        xs=[p[0] for p in pts]; ys=[p[1] for p in pts]
        return (min(xs),min(ys),max(xs),max(ys)) if xs else None
    return subs,[sbb(s) for s in subs]
def seralize(sub, dx=0.0, dy=0.0):
    out=[]
    for seg in sub:
        if seg[0]=='Z': out.append('Z'); continue
        if seg[0]=='M': out.append(f"M {seg[1]+dx:.3f} {seg[2]+dy:.3f}")
        elif seg[0]=='L': out.append(f"L {seg[1]+dx:.3f} {seg[2]+dy:.3f}")
        elif seg[0]=='Q': out.append(f"Q {seg[1]+dx:.3f} {seg[2]+dy:.3f} {seg[3]+dx:.3f} {seg[4]+dy:.3f}")
    return ' '.join(out)
def subpath_d(full_d):
    subs,_=normalize_subpaths(full_d)
    return subs
def flatten_bbox(sp):
    """bbox субпути с кривыми: грубо — все числа как координаты относительно текущей точки; делаем симуляцию"""
    toks=tokenize(sp); xs=[]; ys=[]; cx=cy=0.0; sx=sy=0.0
    i=0; c=None
    while i<len(toks):
        if re.match(r'[A-Za-z]',toks[i]): c=toks[i]; i+=1
        if c is None: break
        rel=c.islower()
        if c in 'zZ': cx,cy=sx,sy; continue
        nums=[]
        while i<len(toks) and not re.match(r'[A-Za-z]',toks[i]): nums.append(float(toks[i])); i+=1
        k=0
        step={'q':4,'Q':4,'c':6,'C':6,'t':2,'T':2,'l':2,'L':2}[c[0].lower() if c in 'qQcCtTlL' else c] if c.lower() in 'qct l'.replace(' ','') else None
        if c in 'mMlLtT':
            pairs=step or 2
            while k+1<len(nums):
                a,b=nums[k],nums[k+1]; k+=2
                if rel: a+=cx; b+=cy
                if c in 'tT':
                    # quad smooth: reflect; bbox control approx
                    cx,cy=a,b
                else:
                    cx,cy=a,b
                xs.append(cx); ys.append(cy)
            if c in 'mM' and nums: sx,sy=xs[-1],ys[-1]
        elif c in 'qQ':
            while k+1<len(nums):
                x1=nums[k]+(cx if rel else 0); y1=nums[k+1]+(cy if rel else 0); x2=nums[k+2]+(cx if rel else 0); y2=nums[k+3]+(cy if rel else 0)
                k+=4
                for u in (0.25,0.5,0.75):
                    xs.append((1-u)**2*cx+2*(1-u)*u*x1+u*u*x2); ys.append((1-u)**2*cy+2*(1-u)*u*y1+u*u*y2)
                cx,cy=x2,y2
        elif c in 'hH':
            for a in nums:
                cx=a+(cx if rel else 0); xs.append(cx); ys.append(cy)
        elif c in 'vV':
            for b in nums:
                cy=b+(cy if rel else 0); xs.append(cx); ys.append(cy)
        else:
            break
    if not xs: return None
    return min(xs),min(ys),max(xs),max(ys)

def main():
    s=open(SRC,encoding='utf-8').read()
    def get_path(lab):
        m=re.search(r'<path[^>]*inkscape:label="'+lab+r'"[^>]*/?>|<path[^>]*d="[^"]*"[^>]*>',s)
        # надёжнее: найти все path и проверить label
        for mm in re.finditer(r'<path[^>]*/>',s):
            if lab in mm.group(0): return mm.group(0)
        raise Exception('no '+lab)
    dI=re.search(r'd="([^"]+)"',get_path('redI')).group(1)
    dT=re.search(r'd="([^"]+)"',get_path('redT')).group(1)
    dC=re.search(r'd="([^"]+)"',get_path('redCluster')).group(1)
    polyI=to_abs_polys(dI); polyT=to_abs_polys(dT)
    assert polyI and len(polyI)==1, 'redI не чистый полигон'
    assert polyT and len(polyT)==1, 'redT не чистый полигон'
    capI=emit_filleted(polyI[0],R_CAP); capT=emit_filleted(polyT[0],R_CAP)
    # дефис
    mD=re.search(r'M ([\d.]+),([\d.]+) V ([\d.]+) h ([\d.-]+) v ([\d.-]+)',dC) # не тут
    dDe=re.search(r'd="([^"]+)"',get_path('redDefis')).group(1)
    nums=[float(x) for x in re.findall(r'-?[\d.]+',dDe)]
    # M x0,y1 V y0 h W v H z  → реконструируем
    x0,y1v=nums[0],nums[1]; y0=nums[2]; W=nums[3]; H=nums[4]
    dash=capsule(x0,y0,x0+W,y0+H)
    # cluster: нормализованные субпути + группировка counters по вложенности bbox
    subs,boxes=normalize_subpaths(dC)
    items=[(s,b) for s,b in zip(subs,boxes) if b]
    outer=[]; inner=[]
    used=set()
    for i,(sp,b) in enumerate(items):
        hole=False
        for j,(sp2,b2) in enumerate(items):
            if j==i: continue
            if b2[0]<=b[0]+0.05 and b2[1]<=b[1]+0.05 and b2[2]>=b[2]-0.05 and b2[3]>=b[3]-0.05 and (b2[2]-b2[0])*(b2[3]-b2[1])>(b[2]-b[0])*(b[3]-b[1]):
                hole=True; break
        (inner if hole else outer).append((sp,b))
        if hole: used.add(i)
    outer.sort(key=lambda t:t[1][0])
    # эталонные bbox букв примера (измеряются с референсного PNG: canvas = px/scale - 0.5)
    REF=[(40.0,106.25,53.5,120.0),(55.0,106.25,70.0,120.0),(71.75,106.0,85.0,120.25),
         (87.0,106.0,100.0,120.25),(100.75,106.25,112.25,120.0),(112.75,106.0,126.5,120.25),
         (128.5,106.0,143.0,125.25)]
    transforms=[]
    for idx,(sp,b) in enumerate(outer):
        if idx<len(REF):
            rx0,ry0,rx1,ry1=REF[idx]
            dx=(rx0+rx1)/2-(b[0]+b[2])/2
            dy=(ry0+ry1)/2-(b[1]+b[3])/2
        else: dx=dy=0.0
        hs=[(s2,b2) for s2,b2 in inner
            if b2[0]>=b[0]-0.05 and b2[2]<=b[2]+0.05 and b2[1]>=b[1]-0.05 and b2[3]<=b[3]+0.05]
        parts=[seralize(sp,dx,dy)]+[seralize(s2,dx,dy) for s2,_ in hs]
        transforms.append((' '.join(parts),''))
    # сборка финала: берём defs/ромб из исходника
    defs=re.search(r'<defs[^>]*>.*?</defs>',s,re.S).group(0)
    rhomb=re.search(r'<g[^>]*filter="url\(#shadow\)"[^>]*>.*?</g>',s,re.S).group(0)
    g_green=(f'<g fill="url(#green)"><path d="{capI}"/><path d="{capT}"/><path d="{dash}"/></g>')
    items_dark=[]
    for d,t in transforms:
        items_dark.append(f'<path d="{d}"{" "+t if t else ""}/>')
    g_dark='<g fill="#27262a" fill-rule="evenodd">'+''.join(items_dark)+'</g>'
    # правая граница градиента — по факту до дефиса
    fin=f'''<svg xmlns="http://www.w3.org/2000/svg" width="192" height="193" viewBox="0 0 192 193" fill="none">
{defs}
{rhomb}
{g_green}
{g_dark}
</svg>'''
    open(OUT,'w',encoding='utf-8').write(fin)
    print('outer glyphs:',len(outer),'inner holes:',len(inner),'->',OUT,len(fin),'bytes')
if __name__=='__main__': main()
