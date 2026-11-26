"""Сглаживание 'лесенок' пиксель-трейса + минимизация SVG.
Использование: python -I smoothmin.py [вход.svg] [выход.svg] [DP-допуск] [Chaikin-итераций].
Метод: baking translate/scale -> DP-прореживание якорей -> пересборка кривых Catmull-Rom."""
import re, math, sys

SRC=sys.argv[1] if len(sys.argv)>1 else 'input.svg'
OUT=sys.argv[2] if len(sys.argv)>2 else SRC.rsplit('.',1)[0]+'.min.svg'
TOL=float(sys.argv[3]) if len(sys.argv)>3 else 0.22
CHAIKIN=int(sys.argv[4]) if len(sys.argv)>4 else 0

def fmt(v):
    return '%g'%round(v,2)

def parse_path(d):
    subs=[]
    for sm in re.finditer(r'M([^MLCZ]*)((?:C[^MLCZ]*)+)?', d):
        m=[float(x) for x in sm.group(1).split()]
        start=(m[0],m[1]); pts=[]
        cs=[float(x) for x in (sm.group(2) or '').replace('C',' ').split()]
        for i in range(0,len(cs),6):
            pts.append((cs[i+4],cs[i+5]))
        subs.append([start]+pts)
    return subs  # list of closed polygons

def perp(a,b,p):
    dx,dy=b[0]-a[0],b[1]-a[1]; L=math.hypot(dx,dy)
    if L==0: return math.hypot(p[0]-a[0],p[1]-a[1])
    return abs((p[0]-a[0])*dy-(p[1]-a[1])*dx)/L

def dp_closed(pts,tol):
    # кольцевой DP: фиксируем крайние, потом склеиваем
    if len(pts)<4: return pts
    def seg(pts,i,j,keep):
        if j-i<2: return
        dmax,k=-1,i+1
        for n in range(i+1,j):
            dd=perp(pts[i],pts[j],pts[n])
            if dd>dmax: dmax,k=dd,n
        if dmax>tol: keep[k]=True; seg(pts,i,k,keep); seg(pts,k,j,keep)
    keep=[False]*len(pts); keep[0]=True
    seg(pts,0,len(pts)-1,keep)
    # хвостовой сегмент last->first
    out=[p for p,k in zip(pts,keep) if k]
    return out

def chaikin(poly, it=1):
    for _ in range(it):
        n=len(poly); q=[]
        for i in range(n):
            a,b=poly[i],poly[(i+1)%n]
            q.append((0.75*a[0]+0.25*b[0],0.75*a[1]+0.25*b[1]))
            q.append((0.25*a[0]+0.75*b[0],0.25*a[1]+0.75*b[1]))
        poly=q
    return poly

def catmull_to_bezier(poly):
    n=len(poly)
    if n<3: return ''
    d=f"M {fmt(poly[0][0])} {fmt(poly[0][1])} C "
    segs=[]
    for i in range(n):
        p0,p1,p2,p3=poly[(i-1)%n],poly[i],poly[(i+1)%n],poly[(i+2)%n]
        # исходное направление касательной (CR) с ограничением длины <= 1/3 отрезка
        edge=math.hypot(p2[0]-p1[0],p2[1]-p1[1])
        lim=edge/3.0
        t1=(p2[0]-p0[0],p2[1]-p0[1]); l1=math.hypot(*t1) or 1
        h1=min(l1/6.0, lim)
        c1=(p1[0]+t1[0]/l1*h1, p1[1]+t1[1]/l1*h1)
        t2=(p3[0]-p1[0],p3[1]-p1[1]); l2=math.hypot(*t2) or 1
        h2=min(l2/6.0, lim)
        c2=(p2[0]-t2[0]/l2*h2, p2[1]-t2[1]/l2*h2)
        segs.extend([c1[0],c1[1],c2[0],c2[1],p2[0],p2[1]])
    d+=' '.join(fmt(v) for v in segs)
    return d+' Z'

def process():
    s=open(SRC,encoding='utf-8').read()
    def bake(m):
        tr,d=m.group(1),m.group(2)
        tx=ty=0.0; sc=1.0
        mt=re.search(r'translate\(([-\d.]+),([-\d.]+)\)',tr)
        ms=re.search(r'scale\(([-\d.]+)\)',tr)
        if mt: tx,ty=map(float,mt.groups())
        if ms: sc=float(ms.group(1))
        polys=parse_path(d)
        out=[]
        for poly in polys:
            bbx=[p[0] for p in poly]; bby=[p[1] for p in poly]
            w=max(bbx)-min(bbx); h=max(bby)-min(bby)
            if w*sc<0.01: continue
            g=[(tx+x*sc, ty+y*sc) for x,y in poly]
            g2=dp_closed(g,TOL)
            if CHAIKIN: g2=chaikin(g2,CHAIKIN)
            if len(g2)<3: continue
            out.append(catmull_to_bezier(g2))
        return f'<path fill-rule="evenodd" d="{" ".join(out)}"/>'
    s2=re.sub(r'<path transform="([^"]+)" fill-rule="evenodd" d="([^"]+)"/>',bake,s)
    open(OUT,'w',encoding='utf-8').write(s2)
    print(len(s),'->',len(s2))

if __name__=='__main__':
    process()
