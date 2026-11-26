"""fitgeom3: geom-фиттер с лечением найденных дефектов.
Отличия от fitgeom.py: (1) медианное сглаживание якорей (убирает AA-дрожь/scallop),
(2) симметричный фит прямой (вертикали не взрываются), (3) snap к 0/90/45,
(4) концы сегментов проецируются на fitted-прямые/дуги (чистые стыки),
(5) более мягкие допуски.
Использование: python -I fitgeom3.py [вход.svg] [выход.svg]
(умолчательно: input.svg -> input.geom3.svg; вход — SVG, где глифы это <path transform="translate(...) scale(...)" fill-rule="evenodd" d="...M/C только...">)"""
import re, math, sys

SRC=sys.argv[1] if len(sys.argv)>1 else 'input.svg'
OUT=sys.argv[2] if len(sys.argv)>2 else SRC.rsplit('.',1)[0]+'.geom3.svg'
LINE_DEV=0.12; ARC_DEV=0.10; DP_TOL=0.12; SNAP_DEG=1.6

def fmt(v): return '%g'%round(v,2)

def parse_subpaths(d):
    subs=[]
    for sm in re.finditer(r'M([^MLCZ]*)((?:C[^MLCZ]*)+)?', d):
        m=[float(x) for x in sm.group(1).split()]
        cs=[float(x) for x in (sm.group(2) or '').replace('C',' ').split()]
        subs.append([(m[0],m[1])]+[(cs[i+4],cs[i+5]) for i in range(0,len(cs),6)])
    return subs

def medsmooth(pts,w=5):
    n=len(pts); out=[]
    h=w//2
    for i in range(n):
        xs=[]; ys=[]
        for k in range(-h,h+1):
            p=pts[(i+k)%n]; xs.append(p[0]); ys.append(p[1])
        xs.sort(); ys.sort()
        out.append((xs[h],ys[h]))
    return out

def perp(a,b,p):
    dx,dy=b[0]-a[0],b[1]-a[1]; L=math.hypot(dx,dy)
    if L==0: return math.hypot(p[0]-a[0],p[1]-a[1])
    return abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)/L

def dp(pts,tol):
    n=len(pts); keep=[False]*n; keep[0]=keep[-1]=True
    st=[(0,n-1)]
    while st:
        i,j=st.pop()
        if j-i<2: continue
        dm,k=-1,i+1
        for x in range(i+1,j):
            dd=perp(pts[i],pts[j],pts[x])
            if dd>dm: dm,k=dd,x
        if dm>tol: keep[k]=True; st+=[(i,k),(k,j)]
    return [i for i,k in enumerate(keep) if k]

def fit_line_sym(run):
    """возвращает (ux,uy,cx,cy) направление единичное + центр масс + dev"""
    n=len(run); mx=sum(p[0] for p in run)/n; my=sum(p[1] for p in run)/n
    # PCA по ковариации
    cxx=sum((p[0]-mx)**2 for p in run)/n; cyy=sum((p[1]-my)**2 for p in run)/n
    cxy=sum((p[0]-mx)*(p[1]-my) for p in run)/n
    t=0.5*math.atan2(2*cxy, cxx-cyy)
    ux,uy=math.cos(t),math.sin(t)
    dev=max(abs((p[0]-mx)*(-uy)+(p[1]-my)*ux) for p in run)
    return ux,uy,mx,my,dev

def snap_angle(ux,uy):
    th=math.degrees(math.atan2(uy,ux))%180
    for target in (0.0,45.0,90.0,135.0,180.0):
        if abs(th-target)<=SNAP_DEG:
            r=math.radians(target)
            return math.cos(r),math.sin(r)
    return ux,uy

def fit_circle_kasa(run):
    if len(run)<5: return None
    mx=sum(p[0] for p in run)/len(run); my=sum(p[1] for p in run)/len(run)
    rx=[p[0]-mx for p in run]; ry=[p[1]-my for p in run]
    sxx=sum(a*a for a in rx); syy=sum(b*b for b in ry); sxy=sum(a*b for a,b in zip(rx,ry))
    q=[a*a+b*b for a,b in zip(rx,ry)]
    sxr=sum(a*qq for a,qq in zip(rx,q)); syr=sum(b*qq for b,qq in zip(ry,q))
    det=sxx*syy-sxy*sxy
    if abs(det)<1e-8: return None
    u=0.5*(sxr*syy-syr*sxy)/det; v=0.5*(syr*sxx-sxr*sxy)/det
    cx,cy=mx+u,my+v
    r=math.sqrt(sum(q)/len(q)+u*u+v*v)
    dev=max(abs(math.hypot(p[0]-cx,p[1]-cy)-r) for p in run)
    return (cx,cy,r,dev)

def cr_chain(run):
    if len(run)<4: return [f"L {fmt(run[-1][0])} {fmt(run[-1][1])}"]
    out=[]
    for i in range(len(run)-1):
        p0=run[max(i-1,0)]; p1=run[i]; p2=run[i+1]; p3=run[min(i+2,len(run)-1)]
        edge=math.hypot(p2[0]-p1[0],p2[1]-p1[1]); lim=edge/3
        t1=(p2[0]-p0[0],p2[1]-p0[1]); l1=math.hypot(*t1) or 1
        c1=(p1[0]+t1[0]/l1*min(l1/6,lim), p1[1]+t1[1]/l1*min(l1/6,lim))
        t2=(p3[0]-p1[0],p3[1]-p1[1]); l2=math.hypot(*t2) or 1
        c2=(p2[0]-t2[0]/l2*min(l2/6,lim), p2[1]-t2[1]/l2*min(l2/6,lim))
        out.append(f"C {fmt(c1[0])} {fmt(c1[1])} {fmt(c2[0])} {fmt(c2[1])} {fmt(p2[0])} {fmt(p2[1])}")
    return out

def emit_line(run):
    ux,uy,mx,my,dev=fit_line_sym(run)
    su,sv=snap_angle(ux,uy)
    px,py=run[-1]
    t=(px-mx)*su+(py-my)*sv
    return f"L {fmt(mx+su*t)} {fmt(my+sv*t)}", ('line',su,sv,mx,my)

def emit_arc(run):
    cx,cy,r,_=fit_circle_kasa(run)
    def proj(p):
        dd=math.hypot(p[0]-cx,p[1]-cy) or 1
        return (cx+(p[0]-cx)/dd*r, cy+(p[1]-cy)/dd*r)
    p1,p2=proj(run[0]),proj(run[-1])
    a1=math.atan2(p1[1]-cy,p1[0]-cx); a2=math.atan2(p2[1]-cy,p2[0]-cx)
    delta=(a2-a1+math.pi)%(2*math.pi)-math.pi
    sweep=1 if delta>=0 else 0
    large=1 if abs(delta)>math.pi else 0
    return f"A {fmt(r)} {fmt(r)} 0 {large} {sweep} {fmt(p2[0])} {fmt(p2[1])}", None

def max_line_cover(raw,i,n):
    best=None; j=i+2
    while j<=min(n-1,i+600):
        run=raw[i:j+1]
        ux,uy,mx,my,dev=fit_line_sym(run)
        if dev<=LINE_DEV: best=j; j+=1
        else: break
    return best  # None если даже 3 точки не легли

def max_arc_cover(raw,i,n):
    best=None; j=i+5
    while j<=min(n-1,i+300):
        c=fit_circle_kasa(raw[i:j+1])
        if c and c[3]<=ARC_DEV: best=j; j+=1
        else: break
    return best

def grow_regions(raw):
    """прямая и дуга КОНКУРИРУЮТ за длинупокрытия; побеждает длиннее.
    линя требователен к доказательству (min 6 точек)."""
    n=len(raw); i=0; frags=[]
    frags.append(f"M {fmt(raw[0][0])} {fmt(raw[0][1])}")
    while i<n-1:
        bl=max_line_cover(raw,i,n)
        ba=max_arc_cover(raw,i,n)
        covL=(bl-i) if bl is not None else 0
        covA=(ba-i) if ba is not None else 0
        if covL>=6 and covL>=covA:
            s,_=emit_line(raw[i:bl+1]); frags.append(s); i=bl
        elif covA>=5:
            s,_=emit_arc(raw[i:ba+1]); frags.append(s); i=ba
        elif covL>=3:
            s,_=emit_line(raw[i:bl+1]); frags.append(s); i=bl
        else:
            step=min(3,n-1-i)
            frags.extend(cr_chain(raw[i:i+step+1]))
            i+=step
    frags.append('Z')
    return ' '.join(frags)

def build(raw):
    raw=medsmooth(raw,5)
    if raw[0]!=raw[-1]: raw=raw+[raw[0]]
    return grow_regions(raw)

def main():
    s=open(SRC,encoding='utf-8').read()
    def bake(m):
        tr,d=m.group(1),m.group(2)
        tx=ty=0.0; sc=1.0
        mt=re.search(r'translate\(([-\d.]+),([-\d.]+)\)',tr); ms=re.search(r'scale\(([-\d.]+)\)',tr)
        if mt: tx,ty=map(float,mt.groups())
        if ms: sc=float(ms.group(1))
        out=[]
        for poly in parse_subpaths(d):
            g=[(tx+x*sc,ty+y*sc) for x,y in poly]
            if len(g)>=6: out.append(build(g))
        return '<path fill-rule="evenodd" d="'+' '.join(out)+'"/>'
    s2=re.sub(r'<path transform="([^"]+)" fill-rule="evenodd" d="([^"]+)"/>',bake,s)
    open(OUT,'w',encoding='utf-8').write(s2)
    l=len(re.findall(r' L ',s2)); a=len(re.findall(r' A ',s2)); c=len(re.findall(r'C ',s2))
    print(len(s),'->',len(s2),f'| L={l} A={a} C={c}')

if __name__=='__main__': main()
