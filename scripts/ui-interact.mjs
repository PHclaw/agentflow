// 前端交互诊断：逐个点击页面上的按钮/标签，收集
//   - 点击后新产生的控制台错误 / 未捕获异常 / 失败请求
//   - 「点了没任何变化」的疑似无效按钮
//
// 做法：每次点击前重新加载页面，保证 DOM 状态干净、元素索引稳定。
//
// 用法：node scripts/ui-interact.mjs [--only=settings,knowledge] [--max=8]
// 前置：后端 8001、前端 5173 均在运行
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const EDGE =
  process.env.EDGE_PATH ||
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const CDP_PORT = 9341
const PROFILE = path.join(process.env.TEMP, 'af-interact-profile')
const SHOT_DIR = path.join(process.env.TEMP, 'af-interact-shots')
const FRONTEND = process.env.FRONTEND_URL || 'http://localhost:5173'
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001'

const args = process.argv.slice(2)
const onlyArg = args.find((a) => a.startsWith('--only='))
const maxArg = args.find((a) => a.startsWith('--max='))
const only = onlyArg ? onlyArg.slice(7).split(',').map((s) => s.trim()).filter(Boolean) : null
const MAX_CLICKS = maxArg ? Number(maxArg.slice(6)) : 10

// 会造成数据丢失或退出登录的操作，跳过不点
const DANGEROUS = /退出登录|注销|登出|删除|清空|重置|重新生成|移除/

fs.mkdirSync(SHOT_DIR, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const loginRes = await fetch(`${BACKEND}/api/v1/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'smoke@test.com', password: 'Smoke@12345' }),
})
if (!loginRes.ok) {
  console.error('登录失败:', loginRes.status)
  process.exit(1)
}
const { token } = await loginRes.json()

const authHeaders = { Authorization: `Bearer ${token}` }
const getJson = async (url) => {
  try {
    const r = await fetch(`${BACKEND}${url}`, { headers: authHeaders })
    return r.ok ? await r.json() : null
  } catch {
    return null
  }
}
const agents = await getJson('/api/v1/agents')
const agentList = Array.isArray(agents) ? agents : agents?.items || []
const skills = await getJson('/api/v1/skills/plaza')
const skillList = Array.isArray(skills) ? skills : skills?.items || []
const firstAgent = agentList[0]?.id
const firstSkill = skillList[0]?.id || skillList[0]?.slug

const ROUTES = [
  { name: 'dashboard', path: '/dashboard' },
  { name: 'agent-list', path: '/agents' },
  { name: 'agent-create', path: '/agents/new' },
  { name: 'knowledge', path: '/knowledge' },
  { name: 'skill-plaza', path: '/skills' },
  { name: 'settings', path: '/settings' },
  { name: 'help', path: '/help' },
  { name: 'chat', path: firstAgent ? `/agents/${firstAgent}/chat` : null },
  { name: 'agent-edit', path: firstAgent ? `/agents/${firstAgent}/edit` : null },
  { name: 'skill-chat', path: firstSkill ? `/skills/${firstSkill}` : null },
  { name: 'workflow-editor', path: firstAgent ? `/workflow/${firstAgent}` : null },
].filter((r) => r.path && (!only || only.includes(r.name)))

// ---------------------------------------------------------------- 浏览器

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
    '--window-size=1440,1000',
    'about:blank',
  ],
  { stdio: 'ignore' }
)

let pageTarget = null
for (let i = 0; i < 40; i++) {
  try {
    const list = await (await fetch(`http://127.0.0.1:${CDP_PORT}/json/list`)).json()
    pageTarget = list.find((t) => t.type === 'page')
    if (pageTarget) break
  } catch {
    /* 未就绪 */
  }
  await sleep(250)
}
if (!pageTarget) {
  console.error('Edge devtools 未就绪')
  edge.kill()
  process.exit(1)
}

const ws = new WebSocket(pageTarget.webSocketDebuggerUrl)
let msgId = 0
const pending = new Map()
await new Promise((r) => ws.addEventListener('open', r))

let bucket = { errors: [], exceptions: [], failed: [] }

ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
    return
  }
  if (msg.method === 'Runtime.consoleAPICalled' && msg.params.type === 'error') {
    bucket.errors.push(
      msg.params.args.map((a) => a.value ?? a.description ?? a.type).join(' ').slice(0, 300)
    )
  }
  if (msg.method === 'Runtime.exceptionThrown') {
    const d = msg.params.exceptionDetails
    bucket.exceptions.push((d.exception?.description || d.text || '').split('\n')[0].slice(0, 300))
  }
  if (msg.method === 'Network.responseReceived') {
    const { response } = msg.params
    if (response.status >= 400 && !response.url.startsWith('data:')) {
      bucket.failed.push(`${response.status} ${response.url.replace(BACKEND, '').replace(FRONTEND, '')}`)
    }
  }
})

const send = (method, params = {}) =>
  new Promise((resolve, reject) => {
    const id = ++msgId
    pending.set(id, { resolve, reject })
    ws.send(JSON.stringify({ id, method, params }))
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id)
        reject(new Error('CDP timeout: ' + method))
      }
    }, 60000)
  })

const evaluate = async (expression) => {
  const { result, exceptionDetails } = await send('Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true,
  })
  if (exceptionDetails) throw new Error(exceptionDetails.exception?.description || 'JS error')
  return result.value
}

const shot = async (name) => {
  try {
    const { data } = await send('Page.captureScreenshot', { format: 'png' })
    fs.writeFileSync(path.join(SHOT_DIR, name), Buffer.from(data, 'base64'))
  } catch {
    /* 忽略 */
  }
}

await send('Page.enable')
await send('Runtime.enable')
await send('Network.enable')

await send('Page.navigate', { url: `${FRONTEND}/login` })
await sleep(2000)
await evaluate(`localStorage.setItem('token', ${JSON.stringify(token)})`)

// 页面「指纹」用于判断点击是否产生了任何变化
const SIGNATURE = `(() => {
  const t = document.body.innerText
  let h = 0
  for (let i = 0; i < t.length; i++) { h = (h * 31 + t.charCodeAt(i)) | 0 }
  return [
    location.pathname + location.search,
    t.length,
    h,
    document.querySelectorAll('[role="dialog"], .fixed.inset-0').length,
  ].join('|')
})()`

const ENUMERATE = `(() => {
  const out = []
  const nodes = [...document.querySelectorAll('button, [role="tab"], a[href^="/"]')]
  nodes.forEach((el, i) => {
    const style = getComputedStyle(el)
    if (style.display === 'none' || style.visibility === 'hidden' || Number(style.opacity) === 0) return
    const rect = el.getBoundingClientRect()
    if (rect.width < 4 || rect.height < 4) return
    if (el.disabled || el.getAttribute('aria-disabled') === 'true') return
    // 跳过确认弹窗内的按钮，避免真的删数据
    if (el.closest('[role="dialog"]')) return
    const label = (el.innerText || el.getAttribute('title') || el.getAttribute('aria-label') || '').trim().slice(0, 24)
    out.push({ i, tag: el.tagName.toLowerCase(), label, disabled: !!el.disabled })
  })
  return out
})()`

console.log('交互诊断开始，每页最多点', MAX_CLICKS, '个元素\n')

const findings = []

for (const route of ROUTES) {
  console.log('='.repeat(70))
  console.log(`页面 [${route.name}] ${route.path}`)
  console.log('='.repeat(70))

  await send('Page.navigate', { url: `${FRONTEND}${route.path}` })
  await sleep(3000)

  const elements = await evaluate(ENUMERATE)
  const clickable = elements.filter((e) => !DANGEROUS.test(e.label))
  const skipped = elements.filter((e) => DANGEROUS.test(e.label))
  console.log(`可点击元素 ${elements.length} 个（跳过危险操作 ${skipped.length} 个）`)
  console.log('  元素:', elements.map((e) => `${e.i}:${e.label || e.tag}`).join(' | ').slice(0, 400))

  const targetsToClick = clickable.slice(0, MAX_CLICKS)
  let pageProblems = 0

  for (const el of targetsToClick) {
    // 每次点击前重载，保证索引稳定、状态干净
    await send('Page.navigate', { url: `${FRONTEND}${route.path}` })
    await sleep(2600)

    bucket = { errors: [], exceptions: [], failed: [] }
    const before = await evaluate(SIGNATURE)

    await evaluate(`(() => {
      const nodes = [...document.querySelectorAll('button, [role="tab"], a[href^="/"]')]
      const el = nodes[${el.i}]
      if (el) el.click()
      return true
    })()`)
    await sleep(1600)

    const after = await evaluate(SIGNATURE)
    const changed = before !== after
    const hasProblem = bucket.errors.length || bucket.exceptions.length || bucket.failed.length

    if (hasProblem) {
      pageProblems++
      const label = el.label || el.tag
      console.log(`  ✗ [${label}]`)
      for (const e of bucket.errors) console.log(`      console.error: ${e}`)
      for (const e of bucket.exceptions) console.log(`      exception: ${e}`)
      for (const f of [...new Set(bucket.failed)]) console.log(`      HTTP ${f}`)
      findings.push({
        page: route.name,
        path: route.path,
        element: label,
        kind: 'error',
        detail: [...bucket.errors, ...bucket.exceptions, ...bucket.failed].slice(0, 3),
      })
      await shot(`${route.name}-${label.replace(/[^\w\u4e00-\u9fa5-]/g, '_').slice(0, 20)}.png`)
    } else if (!changed) {
      // 点击后 DOM 与 URL 完全没有变化，可能是无效按钮
      findings.push({
        page: route.name,
        path: route.path,
        element: el.label || el.tag,
        kind: 'no-effect',
        detail: ['点击后页面无任何变化'],
      })
      console.log(`  ? [${el.label || el.tag}] 点击后无任何变化（疑似无效）`)
    }
  }

  if (pageProblems === 0) console.log('  （本页交互未产生报错）')
}

// ---------------------------------------------------------------- 汇总

const outFile = path.join(SHOT_DIR, 'report.json')
fs.writeFileSync(outFile, JSON.stringify(findings, null, 2), 'utf-8')

console.log('\n' + '='.repeat(70))
console.log('汇总')
console.log('='.repeat(70))

const errors = findings.filter((f) => f.kind === 'error')
const noEffect = findings.filter((f) => f.kind === 'no-effect')

console.log(`\n交互报错 ${errors.length} 处：`)
if (!errors.length) console.log('  无')
for (const f of errors) {
  console.log(`  [${f.page}] ${f.element}`)
  for (const d of f.detail) console.log(`      ${d}`)
}

console.log(`\n疑似无效按钮 ${noEffect.length} 处：`)
if (!noEffect.length) console.log('  无')
const byPage = {}
for (const f of noEffect) {
  byPage[f.page] = byPage[f.page] || []
  byPage[f.page].push(f.element)
}
for (const [page, items] of Object.entries(byPage)) {
  console.log(`  [${page}] ${[...new Set(items)].join(' / ')}`)
}

console.log('\n报告:', outFile)
console.log('截图:', SHOT_DIR)

ws.close()
edge.kill()
await sleep(400)
process.exit(0)
