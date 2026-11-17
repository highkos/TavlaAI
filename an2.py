from PIL import Image
img = Image.open(r"C:\Users\MONSTER\AppData\Local\Microsoft\VisualStudio\CopilotCli\session-state\af64c31e-2ae9-498a-ac7c-a0b1f1d5241e\files\smoke_fix9_hit_live.png").convert("RGB")
w,h = img.size
px = img.load()
def near(c,t,tol=10):
    return abs(c[0]-t[0])<=tol and abs(c[1]-t[1])<=tol and abs(c[2]-t[2])<=tol
def blobs(target, tol):
    seen=[[False]*w for _ in range(h)]
    out=[]
    for y0 in range(h):
        for x0 in range(w):
            if seen[y0][x0]: continue
            if not near(px[x0,y0],target,tol): continue
            stack=[(x0,y0)]; seen[y0][x0]=True; n=0; sx=0; sy=0; minx=x0;maxx=x0;miny=y0;maxy=y0
            while stack:
                x,y=stack.pop(); n+=1; sx+=x; sy+=y
                if x<minx:minx=x
                if x>maxx:maxx=x
                if y<miny:miny=y
                if y>maxy:maxy=y
                for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
                    nx,ny=x+dx,y+dy
                    if 0<=nx<w and 0<=ny<h and not seen[ny][nx] and near(px[nx,ny],target,tol):
                        seen[ny][nx]=True; stack.append((nx,ny))
            if n>=200:
                out.append((n, sx//n, sy//n, minx,miny,maxx,maxy))
    return out
for name,t,tol in (("WHITE",(240,236,226),10),("BLACK",(52,56,68),12)):
    b=blobs(t,tol)
    b.sort(key=lambda z:(z[2],z[1]))
    print(name, len(b))
    for n,cx,cy,minx,miny,maxx,maxy in b:
        print("   n=%5d center=(%4d,%4d) box=(%d,%d)-(%d,%d)"%(n,cx,cy,minx,miny,maxx,maxy))
