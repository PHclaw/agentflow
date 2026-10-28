// AgentFlow 演示录屏器（Edge headless + CDP screencast + ffmpeg 合成）
//
// 为什么这么做
// ------------
// 1. 用 CDP 的 Page.startScreencast 抓帧：页面**有变化才出帧**，每帧带时间戳；
//    合成时按「相邻帧时间差」回填每帧 duration —— 真实耗时被原样保留，
//    静止画面不会被凭空拉长，也不会被吃掉。
// 2. 注入一个跟随鼠标的假光标。headless 下没有系统光标，不画一个的话
//    观众根本不知道点了哪里，营销视频基本没法看。
// 3. 鼠标移动做缓动插值、输入逐字回放，避免"瞬移"造成的廉价感。
//
// 用法
// ----
//   node scripts/ui-record.mjs tour        # 落地页 → 登录 → 控制台 → Agent 列表 → 对话
//   node scripts/ui-record.mjs workflow    # 工作流画布：加节点 → 摆位 → 连线 → 保存
//   node scripts/ui-record.mjs knowledge   # 知识库：上传文档 → 语义检索
//   node scripts/ui-record.mjs skills      # Skill 广场
//   node scripts/ui-record.mjs tour --keep-frames    # 保留中间帧，便于排查
//
//   分段录制（宣传片用，四段各自独立、失败只重录那一段）：
//   node scripts/ui-record.mjs seg-landing     # 落地页 + 真实登录
//   node scripts/ui-record.mjs seg-agent       # Agent 列表 → 空白创建 → 对话
//   node scripts/ui-record.mjs seg-skill       # Skill：PPT 生成 + Excel 出图（最久，约 10 分钟）
//   node scripts/ui-record.mjs seg-templates   # 模板市场 → 筛选 → 使用模板 → 落地成 Agent
//   node scripts/concat-segments.mjs           # 把 seg-1 ~ seg-4 拼成一条完整宣传片
//
// 前置条件：后端 8001、前端 5173 均在运行；本机装有 Edge 与 ffmpeg。
// 产物：assets/videos/<name>.mp4 与 assets/gifs/<name>.gif

import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const EDGE =
  process.env.EDGE_PATH || 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const FFMPEG = process.env.FFMPEG || 'ffmpeg'
const CDP_PORT = Number(process.env.CDP_PORT || 9511)
const FRONTEND = process.env.FRONTEND_URL || 'http://localhost:5173'
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001'
const W = 1440
const H = 900
const FPS = 30
/** 兜底抓帧的间隔（毫秒）—— 页面没动静时靠它保证时间轴不断 */
const GRAB_INTERVAL = Number(process.env.GRAB_INTERVAL || 200)
const DEMO_EMAIL = process.env.DEMO_EMAIL || 'smoke@test.com'
const DEMO_PASSWORD = process.env.DEMO_PASSWORD || 'Smoke@12345'

/** Skill 演示用哪个技能 / 哪个 Agent（避开当前有问题的 PPT Master） */
const SKILL_DEMO_NAME = process.env.SKILL_DEMO_NAME || 'Excel表格助手'
// 必须选「没有配工作流」的 Agent：配了工作流的那条链路会压制技能，
// 页面上还会顶出一条"已选技能不会随本次对话执行"的警告，镜头不能用。
const SKILL_DEMO_AGENT = process.env.SKILL_DEMO_AGENT || '办公助手'

/**
 * 技能演示的输入。
 *
 * 故意用一张「带中文单位的空格表」：技能会自动把「10支」「5块」收成数字，
 * 正好体现"贴一张随手记的表就能分析"这个卖点，比上传附件更容易看懂。
 */
const SKILL_DEMO_INPUT = process.env.SKILL_DEMO_INPUT || [
  '月份  铅笔  钢笔  橡皮',
  '1月   10支  8支   5块',
  '2月   12支  9支   6块',
  '3月   15支  11支  9块',
  '4月   9支   7支   4块',
  '',
  '请按月份画出销量的柱状图',
].join('\n')

const REPO = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const VIDEO_DIR = path.join(REPO, 'assets', 'videos')
const GIF_DIR = path.join(REPO, 'assets', 'gifs')

const DEMO = process.argv[2] || 'tour'
const KEEP_FRAMES = process.argv.includes('--keep-frames')

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

/** 每个场景的产物名。知识库沿用 README 里已有的 demo-knowledge-rag，直接原地替换旧素材 */
const OUTPUT_NAME = {
  tour: 'demo-product-tour',
  workflow: 'demo-workflow-canvas',
  knowledge: 'demo-knowledge-rag',
  skills: 'demo-skill-plaza',
  ppt: 'demo-ppt-generation',
  'ppt-preview': 'demo-ppt-result-preview',
  // 分段产物的名字带序号，拼接时按字典序就是成片顺序
  'seg-landing': 'seg-1-landing',
  'seg-agent': 'seg-2-agent',
  'seg-skill': 'seg-3-skill',
  'seg-templates': 'seg-4-templates',
}

// ---------------------------------------------------------------------------
// 假光标
// ---------------------------------------------------------------------------
const CURSOR_JS = `
(function () {
  if (window.__afCursorReady) return;
  window.__afCursorReady = true;
  function inject() {
    if (document.getElementById('__af_cursor')) return;
    var s = document.createElement('style');
    s.textContent =
      '#__af_cursor{position:fixed;left:-200px;top:-200px;width:18px;height:18px;' +
      'margin:-9px 0 0 -9px;border-radius:50%;background:rgba(99,102,241,.92);' +
      'border:2px solid #fff;box-shadow:0 0 0 1px rgba(15,23,42,.18),0 4px 14px rgba(15,23,42,.35);' +
      'z-index:2147483647;pointer-events:none;' +
      'transition:left .18s ease-out,top .18s ease-out,transform .09s ease-out;will-change:left,top}' +
      '#__af_cursor.__click{transform:scale(.68);background:rgba(67,56,202,1)}' +
      '#__af_cursor.__click::after{content:"";position:absolute;inset:-8px;border-radius:50%;' +
      'border:2px solid rgba(99,102,241,.55)}';
    (document.head || document.documentElement).appendChild(s);
    var d = document.createElement('div');
    d.id = '__af_cursor';
    (document.body || document.documentElement).appendChild(d);
    window.__afCursor = d;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
})();
`

// ---------------------------------------------------------------------------
// 字幕条
// ---------------------------------------------------------------------------
// 只靠鼠标点击，观众只能看到「某个按钮被按了一下」，不知道这一步在干什么。
// 这里在画面底部挂一条字幕，把每一步写成人话 —— 片子不用配旁白也能看懂。
const HINT_CSS =
  '#__af_hint{position:fixed;left:50%;bottom:108px;transform:translate(-50%,16px);' +
  'max-width:900px;padding:12px 24px;border-radius:999px;pointer-events:none;' +
  'background:rgba(15,23,42,.92);color:#F8FAFC;' +
  'font:600 17px/1.3 "Microsoft YaHei","PingFang SC",system-ui,sans-serif;' +
  'letter-spacing:.3px;box-shadow:0 12px 34px rgba(2,6,23,.4);opacity:0;' +
  'transition:opacity .3s ease,transform .3s ease;z-index:2147483646;text-align:center}' +
  '#__af_hint.__on{opacity:1;transform:translate(-50%,0)}'

const HINT_JS = `
(function () {
  if (window.__afHintReady) return;
  window.__afHintReady = true;
  function inject() {
    if (document.getElementById('__af_hint')) return;
    var s = document.createElement('style');
    s.textContent = ${JSON.stringify(HINT_CSS)};
    (document.head || document.documentElement).appendChild(s);
    var d = document.createElement('div');
    d.id = '__af_hint';
    (document.body || document.documentElement).appendChild(d);
    window.__afHint = d;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', inject);
  else inject();
})();
`

// ---------------------------------------------------------------------------
// 录屏器
// ---------------------------------------------------------------------------
class Recorder {
  constructor() {
    this.frames = []
    this.seq = 0
    this.msgId = 0
    this.pending = new Map()
    this.consoleErrors = []
    this._cursor = { x: -200, y: -200 }
    this.marks = []
    this.t0 = 0
  }

  /** 打一个时间标记（相对录制起点的秒数），用于事后裁剪 GIF */
  mark(label) {
    const t = this.t0 ? (Date.now() - this.t0) / 1000 : 0
    this.marks.push({ label, t })
    console.log(`  ⏱  ${t.toFixed(1).padStart(6)}s  ${label}`)
  }

  /** 取标记对应的秒数；找不到则返回 fallback */
  markTime(label, fallback = 0) {
    const hit = [...this.marks].reverse().find((m) => m.label === label)
    return hit ? hit.t : fallback
  }

  // ------------------------------------------------------------ 生命周期

  async launch() {
    if (!fs.existsSync(EDGE)) throw new Error('找不到 Edge：' + EDGE)
    this.profile = path.join(os.tmpdir(), 'af-record-profile-' + CDP_PORT)
    this.edge = spawn(
      EDGE,
      [
        '--headless=new',
        `--remote-debugging-port=${CDP_PORT}`,
        `--user-data-dir=${this.profile}`,
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-gpu',
        '--hide-scrollbars',
        '--disable-extensions',
        '--force-device-scale-factor=1',
        `--window-size=${W},${H}`,
        'about:blank',
      ],
      { stdio: 'ignore' }
    )

    let target = null
    for (let i = 0; i < 60; i++) {
      try {
        const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()
        target = list.find((t) => t.type === 'page')
        if (target) break
      } catch {
        /* devtools 还没起来 */
      }
      await sleep(250)
    }
    if (!target) {
      this.edge.kill()
      throw new Error('Edge devtools 未能就绪')
    }

    this.ws = new WebSocket(target.webSocketDebuggerUrl)
    await new Promise((resolve, reject) => {
      this.ws.addEventListener('open', resolve)
      this.ws.addEventListener('error', reject)
    })

    this.ws.addEventListener('message', (ev) => {
      const msg = JSON.parse(ev.data)
      if (msg.id && this.pending.has(msg.id)) {
        const { resolve, reject } = this.pending.get(msg.id)
        this.pending.delete(msg.id)
        msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
        return
      }
      if (msg.method === 'Page.screencastFrame') {
        const { data, sessionId } = msg.params
        this.frames.push({ t: Date.now(), data })
        // 必须 ack，否则浏览器会停止推帧
        this.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
      }
      if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
        this.consoleErrors.push(
          msg.params.args.map((a) => a.value ?? a.description ?? '').join(' ')
        )
      }
    })

    await this.send('Page.enable')
    await this.send('Runtime.enable')
    await this.send('DOM.enable')
    await this.send('Emulation.setDeviceMetricsOverride', {
      width: W,
      height: H,
      deviceScaleFactor: 1,
      mobile: false,
    })
    await this.send('Page.addScriptToEvaluateOnNewDocument', { source: CURSOR_JS })
    await this.send('Page.addScriptToEvaluateOnNewDocument', { source: HINT_JS })
    // 页面加载中的那一瞬间，浏览器默认铺白底 —— 录出来就是「开头一段白屏」。
    // 把默认背景改成深藏青，闪屏就成了转场效果而不是穿帮。
    // 老版本 Edge 没有这个命令，失败也不影响录制。
    await this.send('Emulation.setDefaultBackgroundColorOverride', {
      color: { r: 15, g: 23, b: 42, a: 1 },
    }).catch(() => {})
  }

  send(method, params = {}) {
    const id = ++this.msgId
    return new Promise((resolve, reject) => {
      this.pending.set(id, { resolve, reject })
      this.ws.send(JSON.stringify({ id, method, params }))
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id)
          reject(new Error('CDP 超时：' + method))
        }
      }, 120000)
    })
  }

  async evaluate(expression) {
    const { result, exceptionDetails } = await this.send('Runtime.evaluate', {
      expression,
      returnByValue: true,
      awaitPromise: true,
    })
    if (exceptionDetails) {
      throw new Error(exceptionDetails.exception?.description || exceptionDetails.text)
    }
    return result.value
  }

  start() {
    this.t0 = Date.now()
    this.screencast = this.send('Page.startScreencast', {
      format: 'jpeg',
      quality: 80,
      maxWidth: W,
      maxHeight: H,
      everyNthFrame: 1,
    })
    // 兜底抓帧。
    //
    // CDP 的 screencast 是「页面有变化才推帧」，可一旦页面静下来（比如
    // 检索请求在飞、界面没动画），它就干脆不推了 —— 之前知识库那段就因为
    // 提交检索后页面没动，录像在结果出来前 5 秒就断了，最后只剩一片没变化的
    // 画面，GIF 里当然「没出结果」。
    // 所以再叠一个定时截图：不管页面动不动，每 200ms 存一张，
    // 至少保证时间轴是连续的、内容是最新的。
    this._grabTimer = setInterval(() => this._grab(), GRAB_INTERVAL)
    return this.screencast
  }

  /** 定时兜底截图（抓帧期间不重复触发） */
  async _grab() {
    if (this._grabbing || this._stopped) return
    this._grabbing = true
    try {
      const { data } = await this.send('Page.captureScreenshot', {
        format: 'jpeg',
        quality: 80,
        captureBeyondViewport: false,
      })
      if (data) this.frames.push({ t: Date.now(), data, shot: true })
    } catch {
      /* 页面正在跳转时抓不到很正常，忽略 */
    } finally {
      this._grabbing = false
    }
  }

  // ------------------------------------------------------------ 基础动作

  /**
   * 显示底部字幕。
   *
   * 传 null 就收起。字幕是给人看懂的，鼠标光标只说明「点在哪儿」，
   * 字幕说明「这一步在干什么」—— 两者一起才是一条自解释的片子。
   */
  async caption(text) {
    const on = text ? 'true' : 'false'
    const body = text ? JSON.stringify(text) : "''"
    await this.evaluate(`(()=>{
      let h=window.__afHint;
      // 页面重渲染 / 路由切换后，原来的字幕节点可能已经被冲掉，
      // 这时重新挂一个，否则后面的字幕全都写进了空气里。
      if(!h || !document.body.contains(h)){
        const old=document.getElementById('__af_hint');
        if(old) old.remove();
        const st=document.createElement('style');
        st.textContent=${JSON.stringify(HINT_CSS)};
        (document.head||document.documentElement).appendChild(st);
        h=document.createElement('div');
        h.id='__af_hint';
        (document.body||document.documentElement).appendChild(h);
        window.__afHint=h;
      }
      h.textContent=${body};
      h.classList.toggle('__on', ${on});
      return 1;
    })()`)
  }

  /**
   * 等页面真正画完。
   *
   * Page.navigate 返回时文档往往还是空的，接着就抓帧会拍到一片空白。
   * 这里等到 readyState 完成且正文有内容为止，首帧就是有内容的画面。
   */
  async waitForPaint(timeout = 15000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      const ok = await this.evaluate(
        `(document.readyState==='complete'||document.readyState==='interactive')` +
          `&&(document.body.innerText||'').trim().length>0`
      )
      if (ok) return true
      await sleep(200)
    }
    return false
  }

  async goto(url, settle = 1600) {
    await this.send('Page.navigate', { url })
    await this.waitForPaint()
    await sleep(settle)
  }

  /**
   * 光标移动到 (x, y)。
   *
   * 位移交给 CSS transition 做，这里只落一次最终位置 —— 早先按 14 步逐帧派发
   * CDP 事件，每步两个往返，一次移动就要 1.5s 上下，整条片子被拖到 2 分钟。
   */
  async moveTo(x, y) {
    await this.evaluate(
      `(()=>{const c=window.__afCursor;if(c){c.style.left='${x.toFixed(1)}px';c.style.top='${y.toFixed(1)}px';}return 1})()`
    )
    await this.send('Input.dispatchMouseEvent', { type: 'mouseMoved', x, y, button: 'none' })
    await sleep(170)
    this._cursor = { x, y }
  }

  async clickPoint(x, y) {
    await this.moveTo(x, y)
    await sleep(110)
    await this.evaluate(`(()=>{const c=window.__afCursor;if(c)c.classList.add('__click');return 1})()`)
    await this.send('Input.dispatchMouseEvent', {
      type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1,
    })
    await sleep(75)
    await this.send('Input.dispatchMouseEvent', {
      type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: 1,
    })
    await this.evaluate(`(()=>{const c=window.__afCursor;if(c)c.classList.remove('__click');return 1})()`)
    await sleep(160)
  }

  async rectOf(selector) {
    return this.evaluate(`(()=>{
      const el=document.querySelector(${JSON.stringify(selector)});
      if(!el)return null;
      const r=el.getBoundingClientRect();
      if(r.width===0&&r.height===0)return null;
      return {x:r.x,y:r.y,w:r.width,h:r.height,cx:r.x+r.width/2,cy:r.y+r.height/2};
    })()`)
  }

  async clickSelector(selector) {
    const r = await this.rectOf(selector)
    if (!r) throw new Error('未找到元素：' + selector)
    await this.clickPoint(r.cx, r.cy)
  }

  /**
   * 按可见文本点击。
   *
   * 元素往往晚一步才渲染出来（登录后要先拉一遍数据才出侧边栏），
   * 所以这里不是查一次就报错，而是轮询等到它出现为止。
   */
  async clickText(text, { tag = 'a,button,[role="button"]', nth = 0, partial = false, timeout = 10000 } = {}) {
    const probe = `(()=>{
      const want=${JSON.stringify(text)};
      const hit=[...document.querySelectorAll(${JSON.stringify(tag)})].filter((n)=>{
        const t=(n.textContent||'').replace(/\\s+/g,' ').trim();
        if(!(${partial ? 't.includes(want)' : 't===want'}))return false;
        const rc=n.getBoundingClientRect();
        return rc.width>0&&rc.height>0;
      });
      const el=hit[${nth}];
      if(!el)return null;
      el.scrollIntoView({block:'center',inline:'center'});
      const r2=el.getBoundingClientRect();
      return {cx:r2.x+r2.width/2,cy:r2.y+r2.height/2};
    })()`
    const t0 = Date.now()
    let r = null
    while (Date.now() - t0 < timeout) {
      r = await this.evaluate(probe)
      if (r) break
      await sleep(250)
    }
    if (!r) throw new Error('未找到文本元素：' + text)
    await sleep(140)
    await this.clickPoint(r.cx, r.cy)
  }

  /** 逐字输入（React 受控组件需要原生 setter + input 事件） */
  async typeInto(selector, text, perChar = 42) {
    await this.clickSelector(selector)
    await sleep(160)
    const clear = `(()=>{
      const el=document.querySelector(${JSON.stringify(selector)});
      const proto=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto,'value').set.call(el,'');
      el.dispatchEvent(new Event('input',{bubbles:true}));
      return 1;
    })()`
    await this.evaluate(clear)
    for (const ch of text) {
      await this.evaluate(`(()=>{
        const el=document.querySelector(${JSON.stringify(selector)});
        const proto=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
        Object.getOwnPropertyDescriptor(proto,'value').set.call(el, el.value + ${JSON.stringify(ch)});
        el.dispatchEvent(new Event('input',{bubbles:true}));
        return el.value;
      })()`)
      await sleep(perChar)
    }
  }

  /**
   * 一次性灌入长文本（模拟「粘贴」）。
   *
   * 表格类输入逐字敲要好几百毫秒 ×上百字符，画面又长又呆；
   * 而技能演示的剧本本来就是"用户复制一份表格贴进来"，
   * 所以这里直接落值 + 派发一次 input，读起来更像真实操作。
   */
  async pasteInto(selector, text) {
    await this.clickSelector(selector)
    await sleep(180)
    await this.evaluate(`(()=>{
      const el=document.querySelector(${JSON.stringify(selector)});
      const proto=el.tagName==='TEXTAREA'?window.HTMLTextAreaElement.prototype:window.HTMLInputElement.prototype;
      Object.getOwnPropertyDescriptor(proto,'value').set.call(el, ${JSON.stringify(text)});
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.style.height='auto';
      el.style.height=Math.min(el.scrollHeight,200)+'px';
      return el.value.length;
    })()`)
    await sleep(420)
  }

  /**
   * 点页面主体里的按钮。
   *
   * 「创建 Agent」这个文案侧边栏里也有一个（NavLink 包着的同名按钮），
   * 按文档顺序取第一个就会点到导航上去 —— 页面看起来毫无反应，
   * 而真实原因是提交压根没触发，光看页面查不出来。
   * 所以先把 aside / nav 里的同名元素排掉再点。
   */
  async clickMainButton(text) {
    const r = await this.evaluate(`(()=>{
      const want=${JSON.stringify(text)};
      const hit=[...document.querySelectorAll('button,[role="button"]')].filter((n)=>{
        const t=(n.textContent||'').replace(/\\s+/g,' ').trim();
        if(t!==want) return false;
        if(n.closest('aside,nav,[role="navigation"]')) return false;
        const rc=n.getBoundingClientRect();
        return rc.width>0&&rc.height>0;
      });
      const el=hit[hit.length-1];
      if(!el) return null;
      el.scrollIntoView({block:'center',inline:'center'});
      const r2=el.getBoundingClientRect();
      return {cx:r2.x+r2.width/2, cy:r2.y+r2.height/2, total:hit.length};
    })()`)
    if (!r) throw new Error('未找到主体按钮：' + text)
    await sleep(160)
    await this.clickPoint(r.cx, r.cy)
    return r.total
  }

  /**
   * 按表单标签文本定位控件。
   *
   * 项目里的 Input/Textarea/Select 都没配 htmlFor，label 和控件只是兄弟节点，
   * 拿不到 id 可直接选中。所以从 label 上溯一层找到控件，顺手打一个 data 属性
   * 当稳定选择器 —— 比 `textarea:nth-of-type(2)` 这种位置选择器靠谱得多。
   *
   * 比对前要把文本归一化：必填项的 label 尾部会多一个 `*`（见 Input.tsx），
   * 直接全等匹配会把「Agent 名称」判成找不到。
   */
  async controlByLabel(label) {
    const sel = await this.evaluate(`(()=>{
      const norm=(s)=>String(s||'').replace(/\\s+/g,'').replace(/\\*+$/,'');
      const want=norm(${JSON.stringify(label)});
      const labs=[...document.querySelectorAll('label')].filter((l)=>norm(l.textContent)===want);
      for(const l of labs){
        const wrap=l.parentElement;
        if(!wrap) continue;
        const ctl=wrap.querySelector('input,textarea,select');
        if(ctl){
          ctl.setAttribute('data-af-ctl', want);
          return '[data-af-ctl="'+want+'"]';
        }
      }
      return null;
    })()`)
    if (!sel) throw new Error('未找到标签对应的控件：' + label)
    return sel
  }

  /**
   * 平滑滚动。
   *
   * 交给浏览器原生的 scroll-behavior: smooth 做，只发一次指令 ——
   * 早先自己按 22 步逐帧滚，每步一个 CDP 往返，一次滚动要 2s，
   * 整片时间大半耗在这里。
   */
  async smoothScrollTo(y, duration = 900) {
    await this.evaluate(`window.scrollTo({ top: ${y}, behavior: 'smooth' })`)
    await sleep(Math.max(500, duration * 0.65))
  }

  async scrollToSelector(selector, offset = 90, duration = 1000) {
    const y = await this.evaluate(`(()=>{
      const el=document.querySelector(${JSON.stringify(selector)});
      return el?window.scrollY+el.getBoundingClientRect().top-${offset}:null;
    })()`)
    if (y == null) return false
    await this.smoothScrollTo(y, duration)
    return true
  }

  async waitForSelector(selector, timeout = 20000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      if (await this.evaluate(`!!document.querySelector(${JSON.stringify(selector)})`)) return true
      await sleep(200)
    }
    return false
  }

  async waitForText(text, timeout = 30000) {
    const t0 = Date.now()
    while (Date.now() - t0 < timeout) {
      if (await this.evaluate(`(document.body.innerText||'').includes(${JSON.stringify(text)})`)) {
        return true
      }
      await sleep(250)
    }
    return false
  }

  /**
   * 等按钮 title 从 A 变成 B（用于判断流式开始/结束）。
   *
   * 结束判定要「消失后稳住」：生成中途按钮可能因为重渲染短暂消失一下，
   * 见到它不见了就收工，会把还在跑的活儿当成做完了（PPT 那段就栽在这）。
   */
  async waitForTitleCycle(appearTitle, timeout = 90000, stableMs = 2500) {
    const sel = `button[title="${appearTitle}"]`
    if (!(await this.waitForSelector(sel, 8000))) return { appeared: false, ms: 0 }
    const t0 = Date.now()
    let goneSince = null
    while (Date.now() - t0 < timeout) {
      const present = await this.evaluate(`!!document.querySelector(${JSON.stringify(sel)})`)
      if (present) {
        goneSince = null
      } else if (goneSince === null) {
        goneSince = Date.now()
      } else if (Date.now() - goneSince >= stableMs) {
        return { appeared: true, ms: Date.now() - t0 }
      }
      await sleep(250)
    }
    return { appeared: true, ms: Date.now() - t0 }
  }

  /** 按下左键（拖拽的第一拍）。会顺带把光标移到该点。 */
  async mouseDown(x, y) {
    await this.evaluate(`(()=>{const c=window.__afCursor;if(c)c.style.transition='none';return 1})()`)
    await this.moveTo(x, y)
    await sleep(150)
    await this.send('Input.dispatchMouseEvent', {
      type: 'mousePressed', x, y, button: 'left', buttons: 1, clickCount: 1,
    })
    await sleep(160)
  }

  /** 保持按住，把指针沿缓动路径挪到目标点 */
  async mouseMoveAlong(from, to, steps = 24) {
    for (let i = 1; i <= steps; i++) {
      const t = i / steps
      const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2
      const x = from.cx + (to.cx - from.cx) * ease
      const y = from.cy + (to.cy - from.cy) * ease
      await this.evaluate(
        `(()=>{const c=window.__afCursor;if(c){c.style.left='${x.toFixed(1)}px';c.style.top='${y.toFixed(1)}px';}return 1})()`
      )
      await this.send('Input.dispatchMouseEvent', {
        type: 'mouseMoved', x, y, button: 'left', buttons: 1,
      })
      await sleep(20)
    }
    this._cursor = { x: to.cx, y: to.cy }
  }

  /** 松开左键，并把光标的过渡动效恢复回来 */
  async mouseUp(x, y) {
    await sleep(170)
    await this.send('Input.dispatchMouseEvent', {
      type: 'mouseReleased', x, y, button: 'left', buttons: 0, clickCount: 1,
    })
    await this.evaluate(
      `(()=>{const c=window.__afCursor;if(c)c.style.transition='left .18s ease-out,top .18s ease-out,transform .09s ease-out';return 1})()`
    )
    await sleep(300)
  }

  /** 鼠标拖拽（用于 ReactFlow 拖节点 / 拉连线） */
  async drag(from, to, steps = 24) {
    await this.mouseDown(from.cx, from.cy)
    await this.mouseMoveAlong(from, to, steps)
    await this.mouseUp(to.cx, to.cy)
  }

  async setFileInput(selector, absPath) {
    const { result } = await this.send('Runtime.evaluate', {
      expression: `document.querySelector(${JSON.stringify(selector)})`,
    })
    if (!result?.objectId) throw new Error('未找到文件输入框：' + selector)
    await this.send('DOM.setFileInputFiles', { files: [absPath], objectId: result.objectId })
    // 有些情况下 CDP 只把文件挂上去、不派发事件，
    // React 的 onChange 就不会触发 —— 手动补一刀 change。
    await this.evaluate(`(()=>{
      const el=document.querySelector(${JSON.stringify(selector)});
      if(!el) return 0;
      const files=el.files?el.files.length:0;
      el.dispatchEvent(new Event('input',{bubbles:true}));
      el.dispatchEvent(new Event('change',{bubbles:true}));
      return files;
    })()`)
    await sleep(500)
  }

  // ------------------------------------------------------------ 收尾与合成

  async stop() {
    this._stopped = true
    if (this._grabTimer) {
      clearInterval(this._grabTimer)
      this._grabTimer = null
    }
    try {
      await this.send('Page.stopScreencast')
    } catch {
      /* 忽略 */
    }
  }

  async close() {
    try {
      this.ws.close()
    } catch {
      /* 忽略 */
    }
    await sleep(300)
    try {
      this.edge.kill()
    } catch {
      /* 忽略 */
    }
  }

  render(name, gifWindow) {
    fs.mkdirSync(VIDEO_DIR, { recursive: true })
    fs.mkdirSync(GIF_DIR, { recursive: true })
    if (!this.frames.length) throw new Error('没有采集到任何帧')

    const stamp = Date.now()
    const frameDir = path.join(os.tmpdir(), `af-frames-${name}-${stamp}`)
    const seqDir = path.join(os.tmpdir(), `af-seq-${name}-${stamp}`)
    fs.mkdirSync(frameDir, { recursive: true })
    fs.mkdirSync(seqDir, { recursive: true })

    // 1) 原始帧落盘
    //    兜底截图和 screencast 帧会交错，按时间戳排一下，
    //    否则后到的旧帧会被当成「倒退」，时间轴就断了。
    this.frames.sort((a, b) => a.t - b.t)
    const srcPaths = this.frames.map((f, idx) => {
      const p = path.join(frameDir, `f_${String(idx).padStart(6, '0')}.jpg`)
      fs.writeFileSync(p, Buffer.from(f.data, 'base64'))
      return p
    })

    // 2) 按绝对时间摊平成固定 30fps 序列。
    //
    //    早先的写法是「每帧各占 相邻帧时间差 × FPS 帧」，四舍五入会把每帧
    //    至少撑成 1 帧，页面越流畅（帧越密）撑得越狠 —— 实测 70s 的录制能撑成
    //    112s，整个片子像被人按了 1.6 倍慢放。
    //    现在改成按绝对时间对齐：第 i 帧应该出现在 round(相对秒数 × FPS) 处，
    //    不足就补上一帧同样的画面，成片长度与真实耗时一致。
    const seqPath = (n) => path.join(seqDir, `s_${String(n).padStart(6, '0')}.jpg`)
    const t0 = this.frames[0].t
    let seq = 0
    for (let i = 0; i < srcPaths.length; i++) {
      const target = Math.round(((this.frames[i].t - t0) / 1000) * FPS)
      // 最后一帧多留 0.6s，收尾不至于戛然而止
      const end = i === srcPaths.length - 1 ? target + Math.round(0.6 * FPS) : target
      while (seq <= end) {
        const dst = seqPath(seq++)
        try {
          fs.linkSync(srcPaths[i], dst)
        } catch {
          fs.copyFileSync(srcPaths[i], dst)
        }
      }
    }

    const mp4 = path.join(VIDEO_DIR, `${name}.mp4`)
    const r = spawnSync(
      FFMPEG,
      [
        '-y', '-hide_banner', '-loglevel', 'error',
        '-framerate', String(FPS),
        '-start_number', '0',
        '-i', path.join(seqDir, 's_%06d.jpg').replace(/\\/g, '/'),
        '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
        '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
        mp4,
      ],
      { encoding: 'utf8' }
    )
    if (r.status !== 0) throw new Error('ffmpeg 合成失败：' + (r.stderr || r.error))

    console.log(
      `[视频] ${path.relative(REPO, mp4)}  ` +
        `${(fs.statSync(mp4).size / 1048576).toFixed(2)} MB  ` +
        `采样帧=${this.frames.length}  成片帧=${seq}  时长=${(seq / FPS).toFixed(1)}s`
    )
    // 诊断：抓到的最后一帧落在录制时间的哪一刻。
    // 页面明明还在变、录像却提前收尾时，看这条就知道是「没抓到帧」还是「时间轴算错」。
    const lastT = this.frames[this.frames.length - 1]?.t ?? 0
    const maxT = Math.max(...this.frames.map((f) => f.t))
    let gap = 0
    let gapAt = 0
    for (let i = 1; i < this.frames.length; i++) {
      const d = this.frames[i].t - this.frames[i - 1].t
      if (d > gap) {
        gap = d
        gapAt = this.frames[i - 1].t - this.t0
      }
    }
    console.log(
      `       末帧落点 ${((lastT - this.t0) / 1000).toFixed(1)}s / 最新帧 ${((maxT - this.t0) / 1000).toFixed(1)}s` +
        ` / 收尾落点 ${((Date.now() - this.t0) / 1000).toFixed(1)}s / 最大断档 ${(gap / 1000).toFixed(1)}s@${(gapAt / 1000).toFixed(1)}s`
    )

    // GIF：README 里内嵌展示用，必须短且小，所以只取一段窗口
    if (gifWindow) {
      const total = seq / FPS
      if (gifWindow.start + gifWindow.duration > total) {
        // 锚点标记得太靠后，就把窗口往前贴回来，保证整段都在片子里
        gifWindow = { duration: gifWindow.duration, start: Math.max(0, total - gifWindow.duration - 0.2) }
      }
    }
    const gif = path.join(GIF_DIR, `${name}.gif`)
    const gifArgs = ['-y', '-hide_banner', '-loglevel', 'error']
    if (gifWindow && gifWindow.start > 0.5) gifArgs.push('-ss', gifWindow.start.toFixed(2))
    gifArgs.push('-i', mp4)
    if (gifWindow && gifWindow.duration > 0) gifArgs.push('-t', gifWindow.duration.toFixed(2))
    gifArgs.push(
      '-vf',
      'fps=11,scale=860:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer:bayer_scale=3',
      '-loop', '0',
      gif
    )
    const g = spawnSync(FFMPEG, gifArgs, { encoding: 'utf8' })
    if (g.status === 0) {
      const gifMB = fs.statSync(gif).size / 1048576
      console.log(
        `[GIF]  ${path.relative(REPO, gif)}  ${gifMB.toFixed(2)} MB` +
          (gifWindow ? `  （取 ${gifWindow.start.toFixed(1)}s 起 ${gifWindow.duration.toFixed(1)}s）` : '')
      )
      if (gifMB > 12) {
        console.warn('[GIF] 体积偏大，README 里加载会卡；建议缩小窗口或降分辨率')
      }
    } else {
      console.warn('[GIF] 生成失败：' + (g.stderr || g.error))
    }

    if (KEEP_FRAMES) {
      console.log('[调试] 中间帧保留在：' + frameDir + ' / ' + seqDir)
    } else {
      fs.rmSync(frameDir, { recursive: true, force: true })
      fs.rmSync(seqDir, { recursive: true, force: true })
    }

    return mp4
  }
}

// ---------------------------------------------------------------------------
// 后端辅助
// ---------------------------------------------------------------------------
async function apiLogin() {
  const res = await fetch(`${BACKEND}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: DEMO_EMAIL, password: DEMO_PASSWORD }),
  })
  if (!res.ok) throw new Error('登录失败：' + res.status)
  return (await res.json()).token
}

async function apiGet(pathname, token) {
  const res = await fetch(`${BACKEND}/api/v1${pathname}`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  return res.ok ? res.json() : null
}

/** 直接注入 token，跳过手动登录（用于聚焦某个功能页的场景） */
async function loginByToken(rec, token) {
  await rec.goto(FRONTEND + '/login', 1800)
  await rec.evaluate(`localStorage.setItem('token', ${JSON.stringify(token)})`)
}

/** 读当前画布缩放 */
function readZoom(rec) {
  return rec.evaluate(`(()=>{
    const v=document.querySelector('.react-flow__viewport');
    const m=/scale\\(([\\d.]+)\\)/.exec((v&&v.style.transform)||'');
    return m?parseFloat(m[1]):1;})()`)
}

/** 用 ctrl + 滚轮把画布缩到目标倍率（ReactFlow 把 ctrl+wheel 当捏合缩放） */
async function zoomOut(rec, target = 1.0, maxSteps = 10) {
  const canvas = await rec.rectOf('.react-flow')
  if (!canvas) return null
  let scale = await readZoom(rec)
  for (let i = 0; i < maxSteps && scale > target + 0.05; i++) {
    await rec.send('Input.dispatchMouseEvent', {
      type: 'mouseWheel',
      x: canvas.cx,
      y: canvas.cy,
      deltaX: 0,
      deltaY: 120,
      modifiers: 2, // Ctrl
    })
    await sleep(340)
    scale = await readZoom(rec)
  }
  return scale
}

/**
 * 点击指定技能卡片上的「开始对话」。
 *
 * 卡片结构是 h3(技能名) + 描述 + button(开始对话)，但它们不一定同级，
 * 所以从 h3 往上找第一个包含该按钮的祖先，再点它。
 */
async function clickSkillCard(rec, name) {
  const r = await rec.evaluate(`(()=>{
    const want=${JSON.stringify(name)};
    const h=[...document.querySelectorAll('h3')].find((e)=>(e.textContent||'').trim()===want);
    if(!h)return null;
    let el=h;
    while(el && el!==document.body){
      const btn=[...el.querySelectorAll('button')].find((b)=>/开始对话/.test(b.textContent||''));
      if(btn){
        btn.scrollIntoView({block:'center', inline:'center'});
        const rc=btn.getBoundingClientRect();
        return {cx:rc.x+rc.width/2, cy:rc.y+rc.height/2};
      }
      el=el.parentElement;
    }
    return null;
  })()`)
  if (!r) throw new Error('未找到技能卡片：' + name)
  await sleep(220)
  await rec.clickPoint(r.cx, r.cy)
}

/**
 * 往画布加一个节点。
 *
 * 左侧分类是手风琴（一次只展开一个），而且「AI 能力」默认展开 ——
 * 直接点分类可能把它点折叠。所以先看目标节点是否已经可见，可见就跳过展开。
 */
async function addNode(rec, category, label) {
  const visible = await rec.evaluate(`(()=>{
    const want=${JSON.stringify(label)};
    return [...document.querySelectorAll('button')].some((b)=>
      (b.textContent||'').replace(/\\s+/g,' ').trim()===want && b.getBoundingClientRect().width>0);
  })()`)
  if (!visible) {
    await rec.clickText(category, { tag: 'button' })
    await sleep(750)
  }
  await rec.clickText(label, { tag: 'button' })
  await sleep(1350) // 节点有 360ms 的像素拼合动画，留足时间
}

// ---------------------------------------------------------------------------
// 场景 1：产品全流程导览
// ---------------------------------------------------------------------------
async function demoTour(rec) {
  // —— 落地页：逐屏滚过，让观众先看到价值主张
  await rec.goto(FRONTEND + '/', 2800)
  await rec.caption('① 落地页：零代码搭建你的 AI Agent')
  await rec.moveTo(980, 520)
  await sleep(1200)
  rec.mark('landing')
  for (const sel of ['#agent-loop', '#pipeline', '#features', '#templates', '#pricing']) {
    await rec.scrollToSelector(sel, 80, 1100)
    await sleep(1000)
  }
  await rec.smoothScrollTo(0, 1000)
  await sleep(700)

  // —— 登录
  await rec.caption('② 登录后进入工作台')
  await rec.clickText('登录', { tag: 'a' })
  await sleep(1800)
  rec.mark('login')
  await rec.typeInto('input[type="email"]', DEMO_EMAIL)
  await sleep(250)
  await rec.typeInto('input[type="password"]', DEMO_PASSWORD)
  await sleep(400)
  await rec.clickText('登录', { tag: 'button' })
  await sleep(3000)

  // —— 控制台
  await rec.waitForSelector('aside, nav', 15000)
  await sleep(2000)
  rec.mark('dashboard')
  await rec.caption('③ 工作台：Agent、知识库、对话一眼看清')

  // —— Agent 列表
  await rec.clickText('Agent', { tag: 'a' })
  await sleep(2000)
  rec.mark('agents')
  await rec.caption('④ Agent 列表：所有智能体集中管理')

  // —— 进入对话
  await rec.clickText('对话', { tag: 'a' })
  await sleep(2600)
  await rec.waitForSelector('textarea', 15000)
  await sleep(1200)
  rec.mark('chat-open')
  await rec.caption('⑤ 直接提问，Agent 按配置自动执行')

  await rec.typeInto('textarea', '你好，用一句话介绍你能为企业做什么', 40)
  await sleep(600)
  await rec.clickSelector('button[title="发送"]')
  rec.mark('chat-sent')
  const cycle = await rec.waitForTitleCycle('停止生成', 90000)
  console.log(`[对话] 流式${cycle.appeared ? '已完成' : '未检测到'}，耗时 ${(cycle.ms / 1000).toFixed(1)}s`)
  rec.mark('chat-reply')
  await sleep(2000)

  // 向上滚一点，展示完整气泡
  await rec.smoothScrollTo(0, 700)
  await sleep(1200)

  // —— 对话记录
  await rec.caption('⑥ 对话记录随时回溯')
  await rec.clickText('对话记录', { tag: 'a' })
  await sleep(2200)
  rec.mark('conversations')
  await sleep(800)
  await rec.caption(null)
}

// ---------------------------------------------------------------------------
// 场景 2：工作流画布
// ---------------------------------------------------------------------------
async function demoWorkflow(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  await rec.goto(FRONTEND + '/workflow/new', 3200)
  await rec.waitForSelector('.react-flow', 25000)
  await sleep(1400)

  // 画布对单节点开了 fitView，初始 zoom 是 2，节点大得摆不开。
  // 先缩到 1 左右，既腾出空间也更符合用户习惯（ctrl + 滚轮）。
  const zoom = await zoomOut(rec, 1.0)
  console.log('[工作流] 缩放至 zoom =', zoom)
  await sleep(900)
  rec.mark('canvas')
  await rec.caption('① 打开空白工作流：左侧节点面板点选即入画布')

  // 流水线的顺序与槽位。
  //
  // 这段绕是有原因的：
  // 1) 流向是竖的 —— 这些节点的连接桩是「上 target / 下 source」（见 NodeShell）。
  //    横着排的话连线要斜穿大半个画布，落点判定基本失效（实测三条线一条都连不上）。
  // 2) DOM 顺序 ≠ 逻辑顺序 —— ReactFlow 会把选中的节点挪到 DOM 末尾，而每加一个
  //    节点它都会被自动选中，所以不能拿 `.react-flow__node` 的下标当顺序，
  //    这里一律按 data-id 的类型前缀认身份。
  // 3) 叠在一起的节点拖不动 —— 新节点都生成在画布中心、互相盖着，鼠标按在中心
  //    抓到的是最上层那个，被盖住的纹丝不动（实测反复拖都无效）。
  //    所以不等全部加完再摆位，而是「加一个、趁它刚生成在最上层，立刻拖到位」。
  const TYPE_ORDER = ['trigger', 'llm', 'condition', 'response']
  const selOf = (id) => `.react-flow__node[data-id="${id}"]`
  const nodeIds = () =>
    rec.evaluate(
      `[...document.querySelectorAll('.react-flow__node')].map((n)=>n.getAttribute('data-id'))`
    )

  // 每次都用当前的画布尺寸重算槽位：拖拽会让 ReactFlow 自动平移，
  // 视口一变，之前算好的屏幕坐标就作废了
  const slotGeometry = async () => {
    const cr = await rec.rectOf('.react-flow')
    const any = await rec.rectOf('.react-flow__node')
    if (!cr || !any) return null
    // 间距留足：位置万一有点偏差，也不至于让上面的节点压住下面的入点
    const spacing = Math.max(any.h * 1.9, 160)
    const totalH = spacing * (TYPE_ORDER.length - 1)
    return {
      spacing,
      cx: cr.x + cr.w * 0.4, // 偏左一点，给右侧「节点配置」面板留位置
      startY: cr.y + Math.max(80, (cr.h - totalH) / 2 - any.h / 2),
    }
  }

  const placeAt = async (id, slot) => {
    const geo = await slotGeometry()
    if (!geo) return
    const box = await rec.rectOf(selOf(id))
    if (!box) return
    const target = { cx: geo.cx, cy: geo.startY + slot * geo.spacing }
    if (Math.abs(target.cx - box.cx) < 12 && Math.abs(target.cy - box.cy) < 12) return
    await rec.drag(box, target, 22)
    await sleep(620)
  }

  // /workflow/new 自带一颗「消息触发」，先让它归位。
  // 此刻它独占画布，怎么拖都不会抓错。
  const preexisting = await nodeIds()
  const triggerId = preexisting.find((id) => id.startsWith('trigger'))
  if (triggerId) await placeAt(triggerId, 0)
  rec.mark('canvas-ready')

  // 补齐后面三步；「AI 能力」默认就是展开的，addNode 会先看节点在不在，
  // 不会把默认展开的分类反手点折叠。
  for (const step of [
    { category: 'AI 能力', node: 'LLM 对话', slot: 1 },
    { category: '流程控制', node: '条件分支', slot: 2 },
    { category: '输出', node: '回复用户', slot: 3 },
  ]) {
    const before = await nodeIds()
    await addNode(rec, step.category, step.node)
    const fresh = (await nodeIds()).find((id) => !before.includes(id))
    if (fresh) await placeAt(fresh, step.slot)
    else console.warn('[工作流] 没识别出新节点，跳过摆位：' + step.node)
  }
  rec.mark('nodes-added')
  await rec.caption('② 触发器 → LLM → 条件分支 → 回复，四个节点串成一条链')

  const ordered = await rec.evaluate(`(()=>{
    const types=${JSON.stringify(TYPE_ORDER)};
    const byType={};
    [...document.querySelectorAll('.react-flow__node')].forEach((n)=>{
      const t=(n.getAttribute('data-id')||'').split('-')[0];
      if(byType[t]===undefined) byType[t]=n.getAttribute('data-id');
    });
    return types.filter((t)=>byType[t]).map((t)=>({type:t, id:byType[t]}));
  })()`)
  console.log('[工作流] 识别到的节点（按流向）:', ordered.map((n) => n.id).join(' → '))

  // 兜底校正：位置有偏差的再摆一次。此时节点各自散开、不再互相遮挡，
  // 拖动是可靠的，跑一轮就够。
  for (const [i, n] of ordered.entries()) await placeAt(n.id, i)
  rec.mark('arranged')

  const placed = await rec.evaluate(`(()=>[...document.querySelectorAll('.react-flow__node')]
    .map((n)=>{const r=n.getBoundingClientRect();
      return {id:n.getAttribute('data-id'), y:Math.round(r.y+r.height/2)};})
    .sort((a,b)=>a.y-b.y))()`)
  console.log('[工作流] 摆位后自上而下:', placed.map((p) => `${p.id.split('-')[0]}@${p.y}`).join(' '))

  // 连线：上一个节点的 source 句柄 → 下一个节点的 target 句柄。
  //
  // 这里必须「每次尝试都重新取坐标」。失败重试如果复用上一轮的坐标，
  // 那一步下去很可能不再落在句柄上，而是抓到了节点本身 —— 结果是把节点
  // 拖离原位、盖住下一个节点的上方入点，后面再怎么连都连不上。
  const edgeCount = () =>
    rec.evaluate(`document.querySelectorAll('.react-flow__edge').length`)

  const pairCoords = (aId, bId) =>
    rec.evaluate(`(()=>{
      const A=document.querySelector(${JSON.stringify(selOf(aId))});
      const B=document.querySelector(${JSON.stringify(selOf(bId))});
      /*
        句柄有一半是探到卡片外面的（!top-[-5px] / !bottom-[-5px]），而卡片设了
        overflow-hidden —— 探出去的那半边既看不见也点不到。直接按句柄的几何
        中心去点，正好压在裁切边界上，命中结果在"句柄"和"卡片"之间摇摆，
        这就是连线时灵时不灵的原因。

        所以落点先从句柄中心往节点内部偏 3px，再用 elementFromPoint 实测确认，
        不行就换几个候选点。测不出句柄就退回原点，至少不比以前更差。
      */
      const aim=(node,sel)=>{
        const h=node&&node.querySelector(sel); if(!h) return null;
        const hr=h.getBoundingClientRect(), nr=node.getBoundingClientRect();
        const cx=hr.x+hr.width/2, cy=hr.y+hr.height/2;
        const dx=Math.sign((nr.x+nr.width/2)-cx)*3;
        const dy=Math.sign((nr.y+nr.height/2)-cy)*3;
        const cands=[[cx+dx,cy+dy],[cx,cy],[cx+dx,cy],[cx,cy+dy],[cx,cy-3],[cx,cy+3],[cx-3,cy],[cx+3,cy]];
        for(const [x,y] of cands){
          const el=document.elementFromPoint(x,y);
          if(el && (el===h || h.contains(el))) return {cx:x, cy:y};
        }
        return {cx:cx, cy:cy};
      };
      return {source: aim(A,'.react-flow__handle.source'), target: aim(B,'.react-flow__handle.target')};
    })()`)

  // 拖拽进行中 ReactFlow 会画一条跟随鼠标的连接线，用它判断"按下去到底有没有抓住句柄"
  const CONNECTION_SEL =
    '.react-flow__connection, .react-flow__connectionline, .react-flow__connection-path'

  const connectPair = async (aId, bId, slotA, slotB) => {
    for (let attempt = 1; attempt <= 3; attempt++) {
      const pair = await pairCoords(aId, bId)
      if (!pair || !pair.source || !pair.target) return false
      const before = await edgeCount()

      await rec.mouseDown(pair.source.cx, pair.source.cy)
      const started = await rec.evaluate(
        `!!document.querySelector(${JSON.stringify(CONNECTION_SEL)})`
      )
      if (!started) {
        const hit = await rec.evaluate(`(()=>{
          const el=document.elementFromPoint(${Math.round(pair.source.cx)},${Math.round(pair.source.cy)});
          if(!el) return '(null)';
          const path=[]; let n=el;
          for(let i=0;i<4&&n;i++){ path.push((n.id?'#'+n.id:'')+'.'+(n.className||'').toString().split(' ').slice(0,3).join('.')); n=n.parentElement; }
          return path.join(' < ');
        })()`)
        console.warn(
          `[工作流] 第 ${attempt} 次：按下没抓住句柄 ` +
            `(${Math.round(pair.source.cx)},${Math.round(pair.source.cy)}) 命中=${hit}`
        )
        // 没开始连线就松手：继续拖只会把节点拽走
        await rec.mouseUp(pair.source.cx, pair.source.cy)
        await placeAt(aId, slotA)
        await placeAt(bId, slotB)
        continue
      }

      await rec.mouseMoveAlong(pair.source, pair.target, 26)
      await rec.mouseUp(pair.target.cx, pair.target.cy)
      await sleep(700)
      if ((await edgeCount()) > before) return true

      console.warn(`[工作流] 第 ${attempt} 次：连接线已起，但没落到入点`)
      await placeAt(aId, slotA)
      await placeAt(bId, slotB)
    }
    return false
  }

  // 连线前先取消选中。
  // 选中态会给节点加一层 pixel 取景框叠层、并把 z-index 顶到 1000，
  // 空画布点一下让所有节点回到同一层级，句柄命中判定干净得多。
  const blank = await rec.rectOf('.react-flow')
  if (blank) {
    await rec.clickPoint(blank.x + 70, blank.y + blank.h - 70)
    await sleep(700)
  }

  for (let i = 0; i < ordered.length - 1; i++) {
    const before = await edgeCount()
    const ok = await connectPair(ordered[i].id, ordered[i + 1].id, i, i + 1)
    console.log(
      `[工作流] 连线 ${ordered[i].type} → ${ordered[i + 1].type}: ` +
        `edges ${before} → ${await edgeCount()}${ok ? '' : '  ✗ 未连上'}`
    )
  }

  const summary = await rec.evaluate(`(()=>{
    const t=(document.body.innerText||'');
    const m=t.match(/(\\d+)\\s*个节点[，,]\\s*(\\d+)\\s*条连接/);
    return m?m[0]:null;
  })()`)
  console.log('[工作流] 画布统计 =', summary)
  rec.mark('connected')
  await rec.caption('③ 拖拽连线，把节点串成可执行的工作流')

  // 点一个节点，让右侧「节点配置」面板显示出来
  const llmNode = ordered.find((n) => n.type === 'llm') || ordered[ordered.length - 1]
  const pick = await rec.rectOf(selOf(llmNode.id))
  if (pick) {
    await rec.caption('④ 右侧直接改节点参数，全程不写代码')
    await rec.clickPoint(pick.cx, pick.cy)
    await sleep(1800)
  }

  // 收尾停在「节点配置」面板上，不点保存。
  //
  // 新建工作流的保存会 POST /agents 建一个 Agent，当前账号的 Agent 名额已满，
  // 点下去必弹「当前套餐最多创建 N 个 Agent」的报错 —— 营销素材里不能有这个。
  // 建流程的完整动作（加节点 → 摆位 → 连线 → 配置）已经演示完了。
  await rec.moveTo(1210, 120)
  await sleep(1200)
}

// ---------------------------------------------------------------------------
// 场景 3：知识库上传与语义检索
// ---------------------------------------------------------------------------
async function demoKnowledge(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  // 准备一份演示文档
  const docPath = path.join(os.tmpdir(), 'agentflow-demo-kb.md')
  fs.writeFileSync(
    docPath,
    [
      '# AgentFlow 产品说明',
      '',
      '## 如何配置模型？',
      '在「设置 → 模型配置」里填写 Base URL 与 API Key，保存后立即生效，无需重启服务。',
      '',
      '## 支持哪些模型？',
      '支持 OpenAI、DeepSeek、Anthropic，以及任意 OpenAI 兼容端点；本地 Ollama 也可直接接入。',
      '',
      '## 知识库怎么工作？',
      '上传 PDF / Word / Markdown 文档后，系统自动分块入库；提问时按语义相关度召回片段。',
      '',
      '## 数据存放在哪里？',
      '全部数据落在你自己的 PostgreSQL 中，不经过任何第三方服务。',
    ].join('\n'),
    'utf8'
  )

  await rec.goto(FRONTEND + '/knowledge', 3000)
  await rec.waitForText('知识库', 15000)
  await sleep(1600)
  rec.mark('kb-list')
  await rec.caption('① 知识库：上传文档，自动分块入库')

  // 先选中一个知识库 —— 新版界面里「上传文档」按钮挂在选中项的标题卡上，
  // 没选中之前页面上根本没有这个按钮。
  const pickedKb = await rec.evaluate(`(()=>{
    const btns=[...document.querySelectorAll('button')].filter(b=>/个文档/.test(b.textContent||''));
    if(!btns.length)return null;
    btns[0].click();
    return (btns[0].textContent||'').replace(/\\s+/g,' ').trim().slice(0,40);
  })()`)
  console.log('[知识库] 选中：', pickedKb)
  await sleep(2200)

  // 打开上传弹窗
  await rec.clickText('上传文档', { tag: 'button' })
  await sleep(1600)
  rec.mark('kb-upload')

  // 通过隐藏 input 投递文件
  await rec.setFileInput('#file-upload', docPath)
  await sleep(1200)

  const after = await rec.evaluate(`(document.body.innerText||'')`)
  console.log('[知识库] 弹窗内是否出现文件：', /agentflow-demo-kb/.test(after))

  // 等上传完成：文件出现在文档列表里
  const uploaded = await rec.waitForText('agentflow-demo-kb', 40000)
  console.log('[知识库] 文档已入库：', uploaded)
  await sleep(1800)
  rec.mark('kb-uploaded')

  // 关闭弹窗（按 Esc）
  await rec.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await rec.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Escape', code: 'Escape', windowsVirtualKeyCode: 27 })
  await sleep(1500)

  // 选中第一个知识库后做语义检索
  const picked = await rec.evaluate(`(()=>{
    const btns=[...document.querySelectorAll('button')].filter(b=>/个文档/.test(b.textContent||''));
    if(!btns.length)return null;
    btns[0].click();
    return (btns[0].textContent||'').trim().slice(0,40);
  })()`)
  console.log('[知识库] 选中：', picked)
  await sleep(2000)

  const searchBox = await rec.evaluate(`(()=>{
    const i=[...document.querySelectorAll('input')].find(x=>/检索内容/.test(x.placeholder||''));
    return i?i.placeholder:null;
  })()`)
  console.log('[知识库] 检索框 placeholder =', searchBox)

  if (searchBox) {
    await rec.caption('② 提问按语义相关度召回，命中片段直接标出')
    await rec.typeInto('input[placeholder="' + searchBox + '"]', '如何配置模型', 45)
    await sleep(600)
    rec.mark('kb-search')
    try {
      await rec.clickText('检索', { tag: 'button' })
    } catch {
      await rec.send('Input.dispatchKeyEvent', { type: 'keyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
      await rec.send('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    }
    await sleep(5000)
    const hit = await rec.waitForText('相关度', 20000)
    console.log('[知识库] 检索命中片段：', hit)
    // 命中片段夹在文档列表中间，不把镜头挪过去根本看不见 ——
    // 找到带「相关度」的那张片段卡，滚到画面中间。
    const focused = await rec.evaluate(`(()=>{
      const leaf=[...document.querySelectorAll('span,div,p,small')]
        .find(e=>e.children.length===0 && /相关度/.test(e.textContent||''));
      if(!leaf) return null;
      let card=leaf;
      for(let i=0;i<6 && card;i++){
        const r=card.getBoundingClientRect();
        if(r.height>=40 && r.width>200) break;
        card=card.parentElement;
      }
      if(!card) return null;
      card.scrollIntoView({block:'center', inline:'nearest'});
      const r=card.getBoundingClientRect();
      return {top:Math.round(r.top), h:Math.round(r.height)};
    })()`)
    console.log('[知识库] 命中片段已居中：', JSON.stringify(focused))
    await rec.caption('③ 命中片段带相关度，答案有出处')
    await sleep(1800)
    rec.mark('kb-result')
  }
}

// ---------------------------------------------------------------------------
// 场景 4：Skill 广场
// ---------------------------------------------------------------------------
async function demoSkills(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  await rec.goto(FRONTEND + '/skills', 3200)
  await rec.waitForText('Skill', 15000)
  await sleep(2200)
  rec.mark('plaza')
  await rec.caption('① Skill 广场：开箱即用的现成能力')

  // 浏览卡片：先下滚一屏，再回到顶部，让观众看清技能种类
  await rec.smoothScrollTo(430, 1000)
  await sleep(1300)
  await rec.moveTo(430, 300)
  await sleep(800)
  await rec.smoothScrollTo(0, 1000)
  await sleep(1200)

  try {
    // 卡片 → 技能详情页。
    // 按技能名精确定位卡片：默认按顺序点"开始对话"会落到第一张卡（PPT Master），
    // 而那个技能当前有问题，不适合放进演示。
    await clickSkillCard(rec, SKILL_DEMO_NAME)
    await sleep(2400)

    // 详情页要先选一个 Agent 才进对话（技能挂在 Agent 上执行）
    if (await rec.waitForText('选择一个 Agent', 12000)) {
      await rec.clickText(SKILL_DEMO_AGENT, { tag: 'button', partial: true })
      await sleep(3000)
    }

    const ok = await rec.waitForSelector('textarea', 15000)
    console.log('[Skill] 已进入对话页：' + ok)
    await sleep(1600)
    rec.mark('skill-chat')

    // 这个 Agent 可能还留着上一轮的问答记录，先点「新对话」清干净 ——
    // 片子只保留本轮"贴表 → 出图"的一条线索，也免得旧消息把图表顶出画面。
    if (await rec.rectOf('button[title="新对话"]')) {
      await rec.clickSelector('button[title="新对话"]')
      await sleep(1000)
      console.log('[Skill] 已开启新对话')
    }

    // —— 真跑一遍：贴表格 → 要柱状图。
    // 技能走 AI Agent 引擎，实测 20~30s；渲染时会把这段静止时间压成 3s，
    // 所以片子里不会出现漫长的空等。
    await rec.pasteInto('textarea', SKILL_DEMO_INPUT)
    await sleep(900)
    rec.mark('skill-typed')
    await rec.caption('② 贴一张随手记的表，技能直接产出图表')
    await rec.clickSelector('button[title="发送"]')
    rec.mark('skill-sent')
    await rec.caption('③ 执行过程实时可见：正在调用工具 read / bash')

    const cycle = await rec.waitForTitleCycle('停止生成', 150000)
    console.log(
      `[Skill] 生成${cycle.appeared ? '已完成' : '未检测到停止按钮'}，耗时 ${(cycle.ms / 1000).toFixed(1)}s`
    )

    // 等产物卡片出现：出图成功后聊天里会多出一条「销量柱状图.png」
    const hasChart = await rec.waitForText('销量柱状图.png', 20000)
    console.log('[Skill] 产物卡片已出现：' + hasChart)
    rec.mark('skill-done')
    await sleep(1200)

    // 把图表整幅挪进视野再收尾。
    // 消息区自己是个 overflow 容器，滚窗口没用，得让图片本身居中。
    const centered = await rec.evaluate(`(()=>{
      const img=document.querySelector('img[alt*="销量柱状图"]');
      if(!img) return false;
      img.scrollIntoView({block:'center', inline:'nearest'});
      return true;
    })()`)
    await sleep(1100)
    const img = await rec.rectOf('img[alt*="销量柱状图"]')
    if (img) {
      await rec.moveTo(img.cx, Math.max(120, Math.min(img.cy, 760)))
      console.log('[Skill] 已定位到内联图表预览（居中=' + centered + '）')
    } else {
      console.warn('[Skill] 未找到内联图表预览，停在产物卡片')
      await rec.moveTo(720, 640)
    }
    await sleep(1800)
    rec.mark('skill-reveal')
    await rec.caption('④ 产物可下载、可继续追问')
    await sleep(1200)
  } catch (e) {
    console.warn('[Skill] 流程未走完：' + e.message)
  }
}

// ---------------------------------------------------------------------------
// 场景 5：对话生成 PPT
//
// 本地模型出完整稿实测 3~7 分钟，后端默认的 PIAGENT_TIMEOUT=180 会把它掐断，
// 所以这条场景要求把 PIAGENT_TIMEOUT 调大（rec.py 里已经设成 600）。
// ---------------------------------------------------------------------------
async function demoPpt(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  await rec.goto(FRONTEND + '/skills', 3000)
  await rec.waitForText('Skill', 15000)
  await sleep(1800)
  rec.mark('skill-plaza')
  await rec.caption('① Skill 广场里挑一个「PPT助手」')

  await clickSkillCard(rec, 'PPT助手')
  await sleep(2600)
  if (await rec.waitForText('选择一个 Agent', 12000)) {
    await rec.clickText(SKILL_DEMO_AGENT, { tag: 'button', partial: true })
    await sleep(3000)
  }
  await rec.waitForSelector('textarea', 15000)

  // 这个 Agent 上有历史会话，先开新对话，片子里只留本轮
  if (await rec.rectOf('button[title="新对话"]')) {
    await rec.clickSelector('button[title="新对话"]')
    await sleep(1000)
  }

  await rec.pasteInto('textarea', SEG_PPT_PROMPT)
  await sleep(900)
  await rec.caption('② 一句话提需求，Agent 自己写稿、排版、出文件')
  await rec.clickSelector('button[title="发送"]')
  rec.mark('ppt-sent')

  // 本地模型出完整稿实测 3~7 分钟，等 10 分钟；渲染时这段会被压成几秒
  const ppt = await rec.waitForTitleCycle('停止生成', 600000, 5000)
  console.log(`[PPT] 生成${ppt.appeared ? '已完成' : '超时未完成'}，耗时 ${(ppt.ms / 1000).toFixed(1)}s`)
  const gotPptx = await waitForArtifact(rec, '.pptx', 300000)
  console.log('[PPT] 产物已出现：' + gotPptx)
  await sleep(1500)

  // 停在产物卡片上，让观众看到文件名与体积
  await rec.evaluate(`(()=>{
    const btns=[...document.querySelectorAll('button')].filter((b)=>/pptx|html/i.test(b.textContent||''));
    if(btns.length) btns[btns.length-1].scrollIntoView({block:'center', inline:'nearest'});
    return !!btns.length;
  })()`)
  await sleep(1200)
  await rec.moveTo(720, 700)
  await sleep(2000)
  rec.mark('ppt-done')
  await rec.caption('③ 生成好的 .pptx 直接作为附件交付，可下载')
  await sleep(1500)
}

// ---------------------------------------------------------------------------
// 场景 6：生成结果逐页预览
//
// 上一条场景已经把 PPT 生成出来了，对话里那几张幻灯片预览图就是最好的
// 「逐页预览」素材。这里把镜头拉到那几张图上，一页一页滚过去。
// ---------------------------------------------------------------------------
async function demoPptPreview(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  const agents = await apiGet('/agents', token)
  const list = Array.isArray(agents) ? agents : agents?.items || agents?.data || []
  const target = list.find((a) => a.name === SKILL_DEMO_AGENT) || list[0]
  if (!target) throw new Error('没有可用的 Agent')
  console.log('[预览] 使用 Agent：' + target.name)

  // 直接定位到「刚生成 PPT 的那一段会话」。
  // 不指定 session 的话，页面会恢复最近一次会话 —— 那可能还是上一轮的 Excel 对话，
  // 页面上根本没有那几张幻灯片（实测就扑空过）。
  const sessions = await apiGet('/chat/sessions?limit=50', token)
  const all = Array.isArray(sessions)
    ? sessions
    : sessions?.sessions || sessions?.items || sessions?.data || []
  const mine = all
    .filter((s) => !s.agent_id || s.agent_id === target.id)
    .sort((a, b) => String(b.updated_at || '').localeCompare(String(a.updated_at || '')))
  const withPpt = mine.find((s) => /ppt/i.test(s.title || ''))
  const session = withPpt || mine[0]
  console.log('[预览] 会话：', session?.id, '标题 =', session?.title)

  const url =
    FRONTEND + '/agents/' + target.id + '/chat' + (session?.id ? '?session=' + session.id : '')
  await rec.goto(url, 3500)
  await rec.waitForSelector('textarea', 20000)
  await sleep(2500)

  // 等幻灯片预览图加载出来。
  // 产物图走 blob:（要走鉴权才能取），但兜底也认「够大的图」——
  // 幻灯片预览动辄上千像素宽，图标和头像都不到这个尺寸。
  // 顺带给每张图算个像素指纹：Agent 有时会重复附同一批文件，
  // 不去重就会「第 1 页、第 2 页、第 1 页、第 2 页」地翻。
  let slides = []
  for (let i = 0; i < 60; i++) {
    slides = await rec.evaluate(`(()=>{
      const imgs=[...document.querySelectorAll('img')]
        .filter(i=>i.naturalWidth>=300 && i.naturalHeight>=150);
      const key=(im)=>{
        try{
          const c=document.createElement('canvas'); c.width=16; c.height=16;
          const x=c.getContext('2d'); x.drawImage(im,0,0,16,16);
          const d=x.getImageData(0,0,16,16).data;
          let h=0; for(let i=0;i<d.length;i++) h=(h*31+d[i])>>>0;
          return String(h);
        }catch(e){ return 'x'+im.naturalWidth+'x'+im.naturalHeight }
      };
      return imgs.map((im,idx)=>({idx:idx,
        top:im.getBoundingClientRect().top+window.scrollY,
        w:im.naturalWidth, h:im.naturalHeight, k:key(im)}));
    })()`)
    if (slides.length) break
    await sleep(1000)
  }
  console.log('[预览] 找到预览图：' + slides.length + ' 张')
  if (!slides.length) {
    const hint = await rec.evaluate(`(document.body.innerText||'').replace(/\\s+/g,' ').slice(-200)`)
    console.log('[预览] 页面尾部：', hint)
    await rec.moveTo(720, 500)
    await sleep(1500)
    return
  }

  slides.sort((a, b) => a.top - b.top)
  // 同一页可能被重复附了多次，按像素指纹去重
  const seen = new Set()
  const pages = slides.filter((s) => {
    if (seen.has(s.k)) return false
    seen.add(s.k)
    return true
  })
  console.log('[预览] 去重后 ' + pages.length + ' 页')

  await rec.caption('生成结果直接内联展示，逐页可看')
  await sleep(1500)

  for (let i = 0; i < pages.length; i++) {
    await rec.evaluate(`(()=>{
      const imgs=[...document.querySelectorAll('img')].filter(i=>i.naturalWidth>=300 && i.naturalHeight>=150);
      const el=imgs[${pages[i].idx}];
      if(el) el.scrollIntoView({block:'center', inline:'nearest'});
      return !!el;
    })()`)
    await sleep(1600)
    await rec.caption(`逐页预览：第 ${i + 1} / ${pages.length} 页`)
    await sleep(1600)
  }
  rec.mark('ppt-preview')
  await sleep(1200)
}

// ---------------------------------------------------------------------------
// 分段录制：四个模块各录一段，最后用 ffmpeg 拼成一条完整宣传片
//   seg-landing    落地页（含真实登录）
//   seg-agent      Agent 列表 → 空白创建 → 对话
//   seg-skill      Skill 广场 → PPT 生成 → Excel 出图
//   seg-templates  模板市场 → 筛选 → 使用模板 → 落地成一个 Agent
// 拆开录的理由：PPT 那段本地模型要跑好几分钟，混在一条里一失败就得整条重来。
// ---------------------------------------------------------------------------

/** 新建 Agent 时填的名字与描述 */
const SEG_AGENT_NAME = process.env.SEG_AGENT_NAME || '周报助手'
const SEG_AGENT_DESC = process.env.SEG_AGENT_DESC || '把一周的工作记录整理成结构化周报'
/** 新建 Agent 时填的系统提示词 */
const SEG_AGENT_PROMPT =
  process.env.SEG_AGENT_PROMPT ||
  '你是周报助手。把零散的工作记录整理成结构化周报：\n1. 本周完成\n2. 数据与结果\n3. 下周计划\n4. 风险与需要支持的事\n结论先行，不要寒暄。'
/** 建完 Agent 后问它的第一句话 */
const SEG_CHAT_Q = process.env.SEG_CHAT_Q || '我接下来把这几天的记录发你，你先说说你会怎么整理'
/** PPT 生成技能的题目（一次提问即出完整稿） */
const SEG_PPT_PROMPT =
  process.env.SEG_PPT_PROMPT || '做一份 3 页的产品介绍 PPT，主题：AgentFlow 零代码 AI Agent 平台'
/** Excel 技能的题目：一张随手记的空格表 */
const SEG_EXCEL_INPUT = process.env.SEG_EXCEL_INPUT || [
  '月份  铅笔  钢笔  橡皮',
  '1月  10支  8支  5块',
  '2月  12支  9支  6块',
  '3月  15支  11支  9块',
  '',
  '请按月份画出销量的柱状图',
].join('\n')
/** 模板市场里点的分类，用来演示筛选 */
const SEG_CATEGORY = process.env.SEG_CATEGORY || 'HR'

/** 等正文出现某个关键词，用来确认产物到位 */
async function waitForKeyword(rec, keyword, timeout = 240000) {
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) {
    if (await rec.evaluate(`(document.body.innerText||'').includes(${JSON.stringify(keyword)})`)) return true
    await sleep(300)
  }
  return false
}

/**
 * 等产物卡片真的出现。
 *
 * 光看正文里有没有 ".pptx" 不作数 —— 生成过程中的工具输出里也会提到文件名。
 * 要等到「可点的东西」上出现这个关键词，才说明产物已经交到用户手上了。
 */
async function waitForArtifact(rec, keyword, timeout = 180000) {
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) {
    const hit = await rec.evaluate(`(()=>{
      const want=${JSON.stringify(keyword)};
      const nodes=[...document.querySelectorAll('a,button,[data-artifact],[role="button"]')];
      const el=nodes.find(n=>(n.textContent||'').includes(want));
      if(!el)return null;
      const r=el.getBoundingClientRect();
      return {text:(el.textContent||'').replace(/\\s+/g,' ').trim().slice(0,60), w:r.width, h:r.height};
    })()`)
    if (hit) return hit
    await sleep(400)
  }
  return false
}

/** 读一眼页面尾部的文字，创建失败时用它定位是 toast 还是表单校验 */
async function pageHint(rec) {
  const t = await rec.evaluate(`(document.body.innerText||'').replace(/\\s+/g,' ')`)
  return String(t).slice(-260)
}

/** 等地址栏变成 /agents/{id}/edit，拿到新 Agent 的 id */
async function waitForNewAgentId(rec, timeout = 14000) {
  const t0 = Date.now()
  while (Date.now() - t0 < timeout) {
    const p = String(await rec.evaluate('window.location.pathname'))
    const m = p.match(/^\/agents\/([^/]+)\/edit$/)
    if (m) return m[1]
    await sleep(500)
  }
  return null
}

/**
 * 填表并提交。返回新 Agent id，失败返回 null（并打印页面尾部便于定位）。
 *
 * `keepBasic` 用于「使用模板」流程：模板已经把名称和描述带进来了，
 * 再覆盖一遍就等于把"套用模板"这个卖点演没了。
 */
async function fillAndSubmitAgent(rec, { keepBasic = false } = {}) {
  await rec.waitForText('创建新 Agent', 12000)
  await sleep(1400)

  try {
    if (!keepBasic) {
      await rec.pasteInto(await rec.controlByLabel('Agent 名称'), SEG_AGENT_NAME)
      await sleep(500)
      await rec.pasteInto(await rec.controlByLabel('描述'), SEG_AGENT_DESC)
      await sleep(500)
    }
    await rec.pasteInto(await rec.controlByLabel('系统提示词'), SEG_AGENT_PROMPT)
    await sleep(900)
    // 右侧「实时预览」会跟着表单变，停一下让观众看到
    await rec.moveTo(1150, 430)
    await sleep(1200)
  } catch (e) {
    console.warn('[Agent] 表单未填完：' + e.message)
  }

  // 侧边栏里也有个同名按钮，必须点页面主体这个才会真的提交
  await rec.clickMainButton('创建 Agent')
  rec.mark('agent-submit')

  const id = await waitForNewAgentId(rec)
  if (!id) console.warn('[Agent] 提交后没有跳转，页面尾部：' + (await pageHint(rec)))
  return id
}

// ---------------------------------------------------------------------------
// 分段 1：落地页（含真实登录）
// ---------------------------------------------------------------------------
async function demoSegLanding(rec) {
  await rec.goto(FRONTEND + '/', 2800)
  await rec.moveTo(980, 520)
  await sleep(1200)
  rec.mark('landing')

  for (const sel of ['#agent-loop', '#pipeline', '#features', '#templates', '#pricing']) {
    await rec.scrollToSelector(sel, 80, 1100)
    await sleep(900)
  }
  await rec.smoothScrollTo(0, 1000)
  await sleep(700)

  // 登录走真实表单：营销片里不能出现"注入 token"这种黑魔法
  await rec.clickText('登录', { tag: 'a' })
  await sleep(1800)
  rec.mark('login')
  await rec.typeInto('input[type="email"]', DEMO_EMAIL)
  await sleep(250)
  await rec.typeInto('input[type="password"]', DEMO_PASSWORD)
  await sleep(400)
  await rec.clickText('登录', { tag: 'button' })
  await sleep(3000)
  await rec.waitForSelector('aside, nav', 15000)
  await sleep(2000)
  rec.mark('dashboard')
}

// ---------------------------------------------------------------------------
// 分段 2：Agent 列表 → 空白创建 → 对话
// ---------------------------------------------------------------------------
async function demoSegAgent(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  await rec.goto(FRONTEND + '/agents', 3200)
  await rec.waitForText('创建 Agent', 15000)
  await sleep(1600)
  rec.mark('agent-list')

  // 从列表页进创建页：链路最短，也不受模板带入的干扰
  await rec.clickMainButton('创建 Agent')
  await sleep(2800)

  let newId = await fillAndSubmitAgent(rec)

  // 没成功就重来一次。之前遇到过"点了但没反应"，多半是点击被浮层吃掉。
  if (!newId) {
    console.warn('[Agent] 第一次创建未成功，重试')
    await rec.goto(FRONTEND + '/agents/new', 2500)
    await sleep(1200)
    newId = await fillAndSubmitAgent(rec)
  }
  console.log('[Agent] 新 Agent id =', newId)
  rec.mark('agent-created')
  await sleep(1800)

  if (newId) {
    await rec.goto(`${FRONTEND}/agents/${newId}/chat`, 3800)
    await rec.waitForSelector('textarea', 15000)
    await sleep(1600)
    rec.mark('agent-chat')

    await rec.pasteInto('textarea', SEG_CHAT_Q)
    await sleep(800)
    await rec.clickSelector('button[title="发送"]')
    rec.mark('agent-chat-sent')
    const cycle = await rec.waitForTitleCycle('停止生成', 180000)
    console.log(`[Agent] 回复${cycle.appeared ? '已完成' : '未检测到'}，耗时 ${(cycle.ms / 1000).toFixed(1)}s`)
    await sleep(2200)
    await rec.smoothScrollTo(0, 700)
    await sleep(1000)
  }
}

// ---------------------------------------------------------------------------
// 分段 3：Skill 广场 → PPT 生成 → Excel 出图
// ---------------------------------------------------------------------------
async function demoSegSkill(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  // —— PPT 生成助手（用的是 ppt-generation，不是有问题的 PPT Master）
  // 注意：这段在 UI 里会被后端 PIAGENT_TIMEOUT（默认 180s）掐断，
  // 实测出完整稿要 190~280s，所以默认跑不了；把超时调大后再打开这里。
  if (process.env.SKIP_PPT !== '1') try {
    await rec.goto(FRONTEND + '/skills', 3000)
    await rec.waitForText('Skill', 15000)
    await sleep(1800)
    rec.mark('skill-plaza')

    await clickSkillCard(rec, 'PPT助手')
    await sleep(2600)
    if (await rec.waitForText('选择一个 Agent', 12000)) {
      await rec.clickText(SKILL_DEMO_AGENT, { tag: 'button', partial: true })
      await sleep(3000)
    }
    await rec.waitForSelector('textarea', 15000)
    await sleep(1500)

    // 这个 Agent 上有历史会话，先开新对话，片子里只留本轮
    if (await rec.rectOf('button[title="新对话"]')) {
      await rec.clickSelector('button[title="新对话"]')
      await sleep(1000)
    }

    await rec.pasteInto('textarea', SEG_PPT_PROMPT)
    await sleep(900)
    await rec.clickSelector('button[title="发送"]')
    rec.mark('ppt-sent')

    // 本地模型出完整稿实测 3~7 分钟，等 10 分钟；渲染时这段会被压成几秒
    const ppt = await rec.waitForTitleCycle('停止生成', 600000)
    console.log(`[PPT] 生成${ppt.appeared ? '已完成' : '超时未完成'}，耗时 ${(ppt.ms / 1000).toFixed(1)}s`)
    const gotPptx = await waitForKeyword(rec, '.pptx', 60000)
    console.log('[PPT] 产物已出现：' + gotPptx)
    await sleep(1500)

    // 停在产物卡片上，让观众看到文件名与体积
    await rec.evaluate(`(()=>{
      const btns=[...document.querySelectorAll('button')].filter((b)=>/pptx|html/i.test(b.textContent||''));
      if(btns.length) btns[btns.length-1].scrollIntoView({block:'center', inline:'nearest'});
      return !!btns.length;
    })()`)
    await sleep(1200)
    await rec.moveTo(720, 700)
    await sleep(2000)
    rec.mark('ppt-done')
  } catch (e) {
    console.warn('[PPT] 流程未走完：' + e.message)
  }

  // —— Excel 表格助手：贴表 → 出图
  try {
    await rec.goto(FRONTEND + '/skills', 2600)
    await rec.waitForText('Skill', 12000)
    await sleep(1400)
    await clickSkillCard(rec, SKILL_DEMO_NAME)
    await sleep(2600)
    if (await rec.waitForText('选择一个 Agent', 12000)) {
      await rec.clickText(SKILL_DEMO_AGENT, { tag: 'button', partial: true })
      await sleep(3000)
    }
    await rec.waitForSelector('textarea', 15000)
    await sleep(1500)

    if (await rec.rectOf('button[title="新对话"]')) {
      await rec.clickSelector('button[title="新对话"]')
      await sleep(1000)
    }

    await rec.pasteInto('textarea', SEG_EXCEL_INPUT)
    await sleep(900)
    await rec.clickSelector('button[title="发送"]')
    rec.mark('excel-sent')
    const xl = await rec.waitForTitleCycle('停止生成', 240000)
    console.log(`[Excel] 生成${xl.appeared ? '已完成' : '未检测到'}，耗时 ${(xl.ms / 1000).toFixed(1)}s`)
    const gotChart = await waitForKeyword(rec, '销量柱状图.png', 30000)
    console.log('[Excel] 产物已出现：' + gotChart)
    await sleep(1500)

    // 图表居中收尾：消息区自己是 overflow 容器，得让图片本身居中
    await rec.evaluate(`(()=>{
      const img=document.querySelector('img[alt*="销量柱状图"]');
      if(img){ img.scrollIntoView({block:'center', inline:'nearest'}); return true; }
      return false;
    })()`)
    await sleep(1100)
    const img = await rec.rectOf('img[alt*="销量柱状图"]')
    if (img) {
      await rec.moveTo(img.cx, Math.max(120, Math.min(img.cy, 760)))
    } else {
      await rec.moveTo(720, 640)
    }
    await sleep(2000)
    rec.mark('excel-done')
  } catch (e) {
    console.warn('[Excel] 流程未走完：' + e.message)
  }
}

// ---------------------------------------------------------------------------
// 分段 4：模板市场 → 筛选 → 使用模板 → 落地成一个 Agent
// ---------------------------------------------------------------------------
async function demoSegTemplates(rec) {
  const token = await apiLogin()
  await loginByToken(rec, token)

  await rec.goto(FRONTEND + '/templates', 3200)
  await rec.waitForText('模板市场', 15000)
  await sleep(1600)
  rec.mark('tpl-list')

  // 先滚一屏看卡片，再回顶部操作筛选
  await rec.smoothScrollTo(520, 1000)
  await sleep(1100)
  await rec.smoothScrollTo(0, 1000)
  await sleep(800)

  // 筛选：点一个分类，网格应收窄到该分类；再点回「全部」
  try {
    await rec.clickText(SEG_CATEGORY, { tag: 'button' })
    await sleep(1500)
    await rec.clickText('全部', { tag: 'button' })
    await sleep(1200)
  } catch (e) {
    console.warn('[模板] 筛选未走完：' + e.message)
  }

  // 「使用模板」→ 创建页，模板把名称、描述、工作流一起带进来
  await rec.clickText('使用模板', { tag: 'button' })
  await sleep(3200)
  rec.mark('tpl-applied')

  const id = await fillAndSubmitAgent(rec, { keepBasic: true })
  console.log('[模板] 新 Agent id =', id)
  rec.mark('tpl-created')
  await sleep(2200)
}

// ---------------------------------------------------------------------------
// 主流程
// ---------------------------------------------------------------------------
const SCENARIOS = {
  tour: demoTour,
  workflow: demoWorkflow,
  knowledge: demoKnowledge,
  skills: demoSkills,
  ppt: demoPpt,
  'ppt-preview': demoPptPreview,
  'seg-landing': demoSegLanding,
  'seg-agent': demoSegAgent,
  'seg-skill': demoSegSkill,
  'seg-templates': demoSegTemplates,
}

/**
 * GIF 取哪一段。
 * README 里的 GIF 是内嵌的，超过十几秒、十几 MB 会拖慢页面，
 * 所以按场景挑最出彩的一段切出来，完整过程还是看 mp4。
 */
const GIF_SPEC = {
  // 一律锚在「结果出现的那一刻」上，而不是「开始动手」的那一刻 ——
  // 之前 tour 的 GIF 卡在流式输出中间、chat 的 GIF 停在思考中，
  // 观众看到的就是「没出结果」。
  tour: { from: 'chat-reply', pre: 9, duration: 13 },
  workflow: { from: 'connected', pre: 12, duration: 11.5 },
  knowledge: { from: 'kb-result', pre: 6, duration: 14 },
  // 技能场景的看点落在"产物曝光"上：截取生成结束前后那一段
  skills: { from: 'skill-done', pre: 7, duration: 12 },
  // PPT 那段最出彩的是产物出现的一刻
  ppt: { from: 'ppt-done', pre: 4, duration: 15 },
  // 逐页预览：取最后几页，翻页最密集
  'ppt-preview': { from: 'ppt-preview', pre: 8, duration: 14 },
  // 分段场景：GIF 取各自最出彩的那一小段，完整过程看 mp4
  'seg-landing': { from: 'login', pre: 1, duration: 14 },
  'seg-agent': { from: 'agent-chat-sent', pre: 2, duration: 14 },
  'seg-skill': { from: 'excel-done', pre: 6, duration: 15 },
  'seg-templates': { from: 'tpl-created', pre: 4, duration: 14 },
}

async function main() {
  const scenario = SCENARIOS[DEMO]
  if (!scenario) {
    console.error('未知场景：' + DEMO + '，可选：' + Object.keys(SCENARIOS).join(' / '))
    process.exit(1)
  }
  const outName = OUTPUT_NAME[DEMO] || `demo-${DEMO}`

  const rec = new Recorder()
  console.log(`[开始] 场景=${DEMO}  产物=${outName}  视口=${W}x${H}`)
  await rec.launch()
  await rec.start()

  let failed = null
  try {
    await scenario(rec)
  } catch (e) {
    failed = e
    console.error('[场景异常] ' + e.message)
  }

  await sleep(500)
  await rec.stop()

  const spec = GIF_SPEC[DEMO]
  const gifWindow = spec
    ? { start: Math.max(0, rec.markTime(spec.from, 0) - (spec.pre || 0)), duration: spec.duration }
    : null

  await rec.render(outName, gifWindow)
  await rec.close()

  if (rec.consoleErrors.length) {
    console.warn('[前端控制台错误] ' + rec.consoleErrors.slice(0, 5).join(' | '))
  }
  if (failed) process.exitCode = 1
  console.log('[完成] ' + outName)
}

// 只有被直接执行时才跑主流程；被 import 时可复用 Recorder
const invokedDirectly =
  process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)

if (invokedDirectly) {
  main().catch((e) => {
    console.error('[致命错误] ' + (e?.stack || e))
    process.exit(1)
  })
}

const LOGIN_HELPERS = { loginByToken, sleep }

export { Recorder, apiLogin, apiGet, FRONTEND, BACKEND, LOGIN_HELPERS }
