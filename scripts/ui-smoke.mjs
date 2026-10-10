// 对话页 UI 冒烟测试（Edge headless + CDP，零依赖）
//
// 用途：真实浏览器里跑一遍「登录 → 打开对话页 → 发消息 → 收流式结果」，
// 产出截图并收集控制台错误/页面异常。用于验证 PiAgent 引擎的前端接入。
//
// 用法：
//   node scripts/ui-smoke.mjs <agent_id> ["要发送的消息"]
//
// 前置：
//   - 后端 8001、前端 5173 均在运行
//   - 数据库里存在 smoke@test.com / Smoke@12345 账号（见 README 轻量模式）
//   - 本机装有 Edge（Windows 自带）
//
// 产物：截图输出到 %TEMP%/af-shots/，可直接查看各阶段界面状态。
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const EDGE =
  process.env.EDGE_PATH ||
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const CDP_PORT = 9333
const PROFILE = path.join(process.env.TEMP, 'af-edge-profile')
const OUT_DIR = path.join(process.env.TEMP, 'af-shots')
const FRONTEND = 'http://localhost:5173'
const BACKEND = 'http://127.0.0.1:8001'
const AGENT_ID = process.argv[2]

fs.mkdirSync(OUT_DIR, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// 先登录拿 token
const loginRes = await fetch(`${BACKEND}/api/v1/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'smoke@test.com', password: 'Smoke@12345' }),
})
const { token } = await loginRes.json()
console.log('[准备] 已获取 token，长度 =', token.length)

// 启动 Edge
const edge = spawn(
  EDGE,
  [
    '--headless=new',
    `--remote-debugging-port=${CDP_PORT}`,
    `--user-data-dir=${PROFILE}`,
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-gpu',
    '--hide-scrollbars',
    '--window-size=1440,900',
    'about:blank',
  ],
  { stdio: 'ignore' }
)

// 等 devtools 就绪
let targets = null
for (let i = 0; i < 40; i++) {
  try {
    const res = await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)
    targets = await res.json()
    if (targets.some((t) => t.type === 'page')) break
  } catch {
    /* 还没起来 */
  }
  await sleep(250)
}
if (!targets) {
  console.error('Edge devtools 未能就绪')
  edge.kill()
  process.exit(1)
}

const page = targets.find((t) => t.type === 'page')
const ws = new WebSocket(page.webSocketDebuggerUrl)

let msgId = 0
const pending = new Map()
const consoleErrors = []
const pageErrors = []

await new Promise((resolve) => ws.addEventListener('open', resolve))

ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
    return
  }
  if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning'].includes(msg.params.type)) {
    consoleErrors.push(
      msg.params.args.map((a) => a.value ?? a.description ?? a.type).join(' ')
    )
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    pageErrors.push(msg.params.exceptionDetails.exception?.description || msg.params.exceptionDetails.text)
  }
})

function send(method, params = {}) {
  const id = ++msgId
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id)
        reject(new Error(`CDP 超时: ${method}`))
      }
    }, 150000)
  })
}

async function screenshot(name) {
  const { data } = await send('Page.captureScreenshot', { format: 'png' })
  const file = path.join(OUT_DIR, name)
  fs.writeFileSync(file, Buffer.from(data, 'base64'))
  console.log(`[截图] ${file}`)
  return file
}

async function evaluate(expression) {
  const { result, exceptionDetails } = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  if (exceptionDetails) throw new Error(exceptionDetails.exception?.description || 'JS 执行失败')
  return result.value
}

await send('Page.enable')
await send('Runtime.enable')

// ---------------------------------------------------------------- 登录页
await send('Page.navigate', { url: `${FRONTEND}/login` })
await sleep(2500)
await screenshot('01-login.png')

// 注入 token（等价于用户已登录）
await evaluate(`localStorage.setItem('token', ${JSON.stringify(token)})`)

// ---------------------------------------------------------------- 对话页
await send('Page.navigate', { url: `${FRONTEND}/agents/${AGENT_ID}/chat` })
await sleep(3000)
await screenshot('02-chat-initial.png')

const engineState = await evaluate(`(() => {
  const btns = [...document.querySelectorAll('header button')].map(b => b.textContent.trim())
  const active = document.querySelector('header .bg-white.dark\\\\:bg-slate-800')?.textContent?.trim() || null
  return { headerButtons: btns, subtitle: document.querySelector('header p')?.textContent?.trim() || null }
})()`)
console.log('[页面] 头部按钮 =', JSON.stringify(engineState.headerButtons))
console.log('[页面] 副标题 =', engineState.subtitle)

// ---------------------------------------------------------------- 发消息
const USER_MESSAGE = process.argv[3] || '请只回复两个字：收到'
const typed = await evaluate(`(() => {
  const ta = document.querySelector('textarea')
  if (!ta) return 'no-textarea'
  const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set
  setter.call(ta, ${JSON.stringify(USER_MESSAGE)})
  ta.dispatchEvent(new Event('input', { bubbles: true }))
  return ta.value
})()`)
console.log('[操作] 输入框内容 =', typed)

await evaluate(`(() => {
  const btn = document.querySelector('button[title="发送"]')
  if (!btn) return 'no-send-button'
  btn.click()
  return 'clicked'
})()`).then((r) => console.log('[操作] 点击发送 =', r))

// 等流式开始后截一张「执行中」的图
let busyShot = false
for (let i = 0; i < 40; i++) {
  await sleep(1000)
  const state = await evaluate(`(() => {
    const stop = !!document.querySelector('button[title="停止生成"]')
    const bubbles = document.body.innerText
    return { stop, hasThinking: bubbles.includes('思考过程'), hasTool: bubbles.includes('正在调用工具') }
  })()`)
  if (!busyShot && (state.hasThinking || state.hasTool)) {
    await screenshot('03-chat-running.png')
    console.log(`[状态] 执行中：思考过程=${state.hasThinking} 工具调用=${state.hasTool}`)
    busyShot = true
  }
  if (!state.stop) {
    console.log(`[状态] 流式结束（第 ${i + 1} 秒）`)
    break
  }
  if (i === 39) console.log('[状态] 等待超时')
}

await sleep(800)
await screenshot('04-chat-final.png')

const finalText = await evaluate(`document.querySelector('main')?.innerText || ''`)
console.log('[结果] 页面正文片段 =', JSON.stringify(finalText.slice(-400)))

console.log('[控制台错误] =', consoleErrors.length ? JSON.stringify(consoleErrors) : '无')
console.log('[页面异常] =', pageErrors.length ? JSON.stringify(pageErrors) : '无')

ws.close()
edge.kill()
await sleep(500)
console.log('[完成] 截图目录 =', OUT_DIR)
