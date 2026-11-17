from PIL import Image
img = Image.open(r"C:\Users\MONSTER\AppData\Local\Microsoft\VisualStudio\CopilotCli\session-state\af64c31e-2ae9-498a-ac7c-a0b1f1d5241e\files\smoke_fix9_hit_live.png").convert("RGB")
w,h = img.size
print("size", w, h)
px = img.load()
def near(c,t,tol=12):
    return abs(c[0]-t[0])<=tol and abs(c[1]-t[1])<=tol and abs(c[2]-t[2])<=tol
# find bounding box of board-ish region: look for bar color (177,141,101)
xs=[];ys=[]
for y in range(0,h,2):
    for x in range(0,w,2):
        if near(px[x,y],(177,141,101),10):
            xs.append(x);ys.append(y)
print("bar/tray bbox", min(xs),min(ys),max(xs),max(ys))
