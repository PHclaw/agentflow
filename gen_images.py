"""AgentFlow 推广图生成"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = r"C:\Users\16846\.qclaw\workspace-agent-b1823e5f\projects\agentflow\promo_images"
os.makedirs(OUT, exist_ok=True)

def c(hex_str):
    h = hex_str.lstrip('#')
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))

# 调色板
BLUE   = c("#3B82F6")
INDIGO = c("#6366F1")
PURPLE = c("#8B5CF6")
VIOLET = c("#7C3AED")
WHITE  = c("#FFFFFF")
G50    = c("#F8FAFC")
G100   = c("#F1F5F9")
G200   = c("#E2E8F0")
G300   = c("#CBD5E1")
G400   = c("#94A3B8")
G500   = c("#64748B")
G600   = c("#475569")
G700   = c("#334155")
G800   = c("#1E293B")
G900   = c("#0F172A")

def fnt(size, bold=False):
    # 优先使用 Windows 中文字体
    if bold:
        for p in [
            r"C:\Windows\Fonts\msyhbd.ttc",  # 微软雅黑粗体(ttc)
            r"C:\Windows\Fonts\Dengb.ttf",   # 等线粗体
            r"C:\Windows\Fonts\simhei.ttf",  # 黑体
        ]:
            try: return ImageFont.truetype(p, size)
            except: pass
    for p in [
        r"C:\Windows\Fonts\msyh.ttc",      # 微软雅黑(ttc)
        r"C:\Windows\Fonts\Deng.ttf",      # 等线
        r"C:\Windows\Fonts\simhei.ttf",    # 黑体
        r"C:\Windows\Fonts\simsun.ttc",    # 宋体
    ]:
        try: return ImageFont.truetype(p, size)
        except: pass
    return ImageFont.load_default()

def grad(w, h, c1, c2):
    img = Image.new("RGB", (w, h))
    draw = ImageDraw.Draw(img)
    for y in range(h):
        t = y / h
        r = int(c1[0]*(1-t) + c2[0]*t)
        g = int(c1[1]*(1-t) + c2[1]*t)
        b = int(c1[2]*(1-t) + c2[2]*t)
        draw.line([(0,y),(w,y)], fill=(r,g,b))
    return img

def rrect(draw, x1, y1, x2, y2, r, fill):
    w = x2-x1; h = y2-y1; r = min(r, w//2, h//2)
    if r <= 0:
        draw.rectangle([x1,y1,x2,y2], fill=fill); return
    draw.rectangle([x1+r,y1,x2-r,y2], fill=fill)
    draw.rectangle([x1,y1+r,x2,y2-r], fill=fill)
    draw.pieslice([x1,y1,x1+2*r,y1+2*r], 180, 270, fill=fill)
    draw.pieslice([x2-2*r,y1,x2,y1+2*r], 270, 360, fill=fill)
    draw.pieslice([x1,y2-2*r,x1+2*r,y2], 90, 180, fill=fill)
    draw.pieslice([x2-2*r,y2-2*r,x2,y2], 0, 90, fill=fill)

def tc(draw, text, cx, y, size, color, bold=False):
    f = fnt(size, bold)
    bb = draw.textbbox((0,0), text, font=f)
    w = bb[2]-bb[0]
    draw.text((cx-w//2, y), text, font=f, fill=color)

def tl(draw, text, x, y, size, color, bold=False):
    draw.text((x, y), text, font=fnt(size, bold), fill=color)

# ============================================================
# 1. Hero Banner - AgentFlow 主视觉
# ============================================================
def fig1():
    W, H = 1200, 630
    img = grad(W, H, G900, c("#1e1b4b"))
    d = ImageDraw.Draw(img)
    
    # 背景光晕
    for cx,cy,r,a,col in [(900, 100, 400, 40, INDIGO), (300, 500, 350, 30, BLUE)]:
        for i in range(r, 0, -20):
            alpha = int(a * (i/r))
            d.ellipse([cx-i, cy-i, cx+i, cy+i], fill=(*col, alpha) if len(col)==3 else col)
    
    # Logo 区域
    rrect(d, 80, 180, 180, 280, 20, INDIGO)
    tc(d, "A", 130, 205, 72, WHITE, True)
    
    # 标题
    tc(d, "AgentFlow", 350, 180, 64, WHITE, True)
    tc(d, "AI Agent 部署平台", 350, 260, 32, G300)
    tc(d, "拖拽式构建 · 多模型支持 · 浏览器自动化", 350, 310, 20, G400)
    
    # CTA 按钮样式
    rrect(d, 350, 380, 580, 440, 8, BLUE)
    tc(d, "开始构建 Agent", 465, 395, 20, WHITE, True)
    
    img.save(f"{OUT}/01_hero.png")
    print("01_hero.png saved")

# ============================================================
# 2. Features - 核心特性
# ============================================================
def fig2():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), G50)
    d = ImageDraw.Draw(img)
    
    tc(d, "核心特性", W//2, 60, 40, G800, True)
    
    features = [
        ("拖拽式工作流", "可视化节点编辑器\n无需编码构建 AI 工作流", INDIGO),
        ("多模型支持", "GPT-4 / Claude / DeepSeek\n一键切换", BLUE),
        ("浏览器自动化", "内置 Browser-Use\nAI 控制浏览器", PURPLE),
        ("知识库 RAG", "文档分块 + 向量检索\n精准回答", c("#10B981")),
    ]
    
    for i, (title, desc, col) in enumerate(features):
        x = 80 + i * 280
        y = 180
        rrect(d, x, y, x+260, y+350, 16, WHITE)
        rrect(d, x+20, y+20, x+80, y+80, 12, col)
        tl(d, title, x+20, y+100, 22, G800, True)
        for j, line in enumerate(desc.split('\n')):
            tl(d, line, x+20, y+140+j*28, 16, G500)
    
    img.save(f"{OUT}/02_features.png")
    print("02_features.png saved")

# ============================================================
# 3. Workflow Builder - 工作流编辑器
# ============================================================
def fig3():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), G900)
    d = ImageDraw.Draw(img)
    
    tc(d, "可视化工作流编辑器", W//2, 50, 36, WHITE, True)
    
    # 模拟工作流节点
    nodes = [
        (100, 200, "START", G700),
        (300, 200, "LLM", INDIGO),
        (500, 200, "TOOL", BLUE),
        (700, 200, "BROWSER", PURPLE),
        (900, 200, "END", G700),
    ]
    
    # 连接线
    for i in range(len(nodes)-1):
        x1 = nodes[i][0] + 80
        y1 = nodes[i][1] + 40
        x2 = nodes[i+1][0]
        y2 = nodes[i+1][1] + 40
        d.line([(x1, y1), (x2, y2)], fill=G600, width=3)
        d.polygon([(x2-8, y2-5), (x2, y2), (x2-8, y2+5)], fill=G600)
    
    # 节点
    for x, y, label, col in nodes:
        rrect(d, x, y, x+160, y+80, 12, col)
        tc(d, label, x+80, y+28, 18, WHITE, True)
    
    # 侧边栏
    rrect(d, 20, 150, 60, 500, 8, G800)
    for i, icon in enumerate(["+", "LLM", "T", "B", "K"]):
        rrect(d, 28, 170+i*60, 52, 220+i*60, 6, G700)
        tc(d, icon, 40, 185+i*60, 14, G300)
    
    img.save(f"{OUT}/03_workflow.png")
    print("03_workflow.png saved")

# ============================================================
# 4. Browser Automation - 浏览器自动化
# ============================================================
def fig4():
    W, H = 1200, 630
    img = grad(W, H, c("#1e1b4b"), G900)
    d = ImageDraw.Draw(img)
    
    tc(d, "Browser-Use 浏览器自动化", W//2, 60, 36, WHITE, True)
    tc(d, "让 AI 像人一样操作浏览器", W//2, 110, 20, G400)
    
    # 左侧：代码示例
    rrect(d, 80, 180, 550, 550, 12, G800)
    tl(d, "# AgentFlow 浏览器控制", 100, 200, 16, G400)
    tl(d, "task = \"去 GitHub 搜索 AI Agent 热门项目\"", 100, 240, 16, c("#60A5FA"))
    tl(d, "result = await browser_control(task)", 100, 280, 16, WHITE)
    tl(d, "", 100, 320, 16, WHITE)
    tl(d, "# AI 自动执行：", 100, 360, 16, G400)
    tl(d, "1. 打开 github.com", 120, 400, 16, G300)
    tl(d, "2. 搜索 trending", 120, 440, 16, G300)
    tl(d, "3. 分析项目信息", 120, 480, 16, G300)
    tl(d, "4. 截图返回结果", 120, 520, 16, G300)
    
    # 右侧：浏览器窗口示意
    rrect(d, 600, 180, 1120, 550, 12, WHITE)
    rrect(d, 600, 180, 1120, 220, 12, G100)  # 地址栏
    rrect(d, 620, 190, 1100, 210, 8, WHITE)  # 地址栏输入框
    tl(d, "github.com/trending", 630, 194, 14, G500)
    
    # 网页内容示意
    rrect(d, 640, 240, 1080, 280, 6, G200)
    rrect(d, 640, 300, 900, 330, 4, G300)
    rrect(d, 640, 340, 950, 370, 4, G300)
    rrect(d, 640, 380, 880, 410, 4, G300)
    
    # AI 指示器
    rrect(d, 1020, 480, 1100, 520, 20, PURPLE)
    tc(d, "AI", 1060, 490, 16, WHITE, True)
    
    img.save(f"{OUT}/04_browser.png")
    print("04_browser.png saved")

# ============================================================
# 5. Tech Stack - 技术栈
# ============================================================
def fig5():
    W, H = 1200, 630
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    
    tc(d, "技术栈", W//2, 60, 40, G800, True)
    
    stacks = [
        ("后端", ["FastAPI", "SQLAlchemy", "LangGraph", "Celery"], BLUE),
        ("前端", ["React", "TypeScript", "Vite", "Tailwind"], c("#38BDF8")),
        ("AI/LLM", ["OpenAI", "Claude", "DeepSeek", "Browser-Use"], PURPLE),
        ("数据库", ["PostgreSQL", "pgvector", "Redis"], c("#10B981")),
    ]
    
    for i, (cat, items, col) in enumerate(stacks):
        x = 80 + i * 280
        y = 180
        rrect(d, x, y, x+260, y+400, 16, G50)
        rrect(d, x, y, x+260, y+60, 16, col)
        tc(d, cat, x+130, y+18, 22, WHITE, True)
        
        for j, item in enumerate(items):
            rrect(d, x+20, y+80+j*70, x+240, y+140+j*70, 8, WHITE)
            tc(d, item, x+130, y+95+j*70, 18, G700)
    
    img.save(f"{OUT}/05_tech.png")
    print("05_tech.png saved")

# ============================================================
# 6. GitHub Social Preview - GitHub 社交预览
# ============================================================
def fig6():
    W, H = 1280, 640
    img = grad(W, H, G900, c("#1e1b4b"))
    d = ImageDraw.Draw(img)
    
    # 大 Logo
    rrect(d, 100, 220, 220, 420, 24, INDIGO)
    tc(d, "A", 160, 280, 96, WHITE, True)
    
    # 标题
    tl(d, "AgentFlow", 260, 260, 72, WHITE, True)
    tl(d, "AI Agent 部署平台", 260, 350, 32, G300)
    
    # 标签
    badges = ["FastAPI", "React", "LangGraph", "Browser-Use"]
    bx = 260
    for badge in badges:
        bw = len(badge) * 14 + 32
        rrect(d, bx, 420, bx+bw, 460, 20, G800)
        tc(d, badge, bx+bw//2, 430, 16, G300)
        bx += bw + 16
    
    img.save(f"{OUT}/06_github.png")
    print("06_github.png saved")

if __name__ == "__main__":
    fig1()
    fig2()
    fig3()
    fig4()
    fig5()
    fig6()
    print(f"\nAll images saved to: {OUT}")
