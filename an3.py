from PIL import Image
img = Image.open(r"C:\Users\MONSTER\AppData\Local\Microsoft\VisualStudio\CopilotCli\session-state\af64c31e-2ae9-498a-ac7c-a0b1f1d5241e\files\smoke_fix9_hit_live.png").convert("RGB")
w,h = img.size
px = img.load()
def near(c,t,tol=14):
    return abs(c[0]-t[0])<=tol and abs(c[1]-t[1])<=tol and abs(c[2]-t[2])<=tol
# scan a horizontal line near the bottom of the bottom row (y=980) and near top of top row (y=170)
for y in (975, 170):
    runs=[]
    cur=None
    for x in range(0,w):
        c=px[x,y]
        k = 'L' if near(c,(203,194,168)) else ('D' if near(c,(56,20,17)) else '.')
        if cur and cur[0]==k: cur[2]=x
        else:
            if cur: runs.append(cur)
            cur=[k,x,x]
    if cur: runs.append(cur)
    print("y=",y)
    for k,a,b in runs:
        if k!='.' and b-a>10: print("   ",k,a,b,"w=",b-a+1)
