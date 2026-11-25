// 前端全路由诊断：用 Edge headless + CDP 逐个页面收集
//   - 控制台 error / warning
//   - 未捕获异常
//   - 失败的网络请求（HTTP >= 400）与请求失败原因
//   - 异常跳转（如受保护页面被踢回 /login）
//
// 用法：node scripts/ui-diagnose.mjs [--headed] [--only=/settings,/agents]
// 前置：后端 8001、前端 5173 均在运行
import { spawn } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'

const EDGE =
  process.env.EDGE_PATH ||
  'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'
const CDP_PORT = 9340
const PROFILE = path.join(process.env.TEMP, 'af-diag-profile')
const SHOT_DIR = path.join(process.env.TEMP, 'af-diag-shots')
const FRONTEND = process.env.FRONTEND_URL || 'http://localhost:5173'
const BACKEND = process.env.BACKEND_URL || 'http://127.0.0.1:8001'

const args = process.argv.slice(2)
const onlyArg = args.find((a) => a.startsWith('--only='))
const only = onlyArg ? onlyArg.slice(7).split(',').map((s) => s.trim()).filter(Boolean) : null

fs.mkdirSync(SHOT_DIR, { recursive: true })
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

// ---------------------------------------------------------------- 准备数据

const loginRes = await fetch(`${BACKEND}/api/v1/auth/login`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ email: 'smoke@test.com', password: 'Smoke@12345' }),
})
if (!loginRes.ok) {
  console.error('登录失败，无法继续:', loginRes.status, await loginRes.text())
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
const agentList = Array.isArray(agents) ? agents : agents?.items || agents?.agents || []
const skills = await getJson('/api/v1/skills/plaza')
const skillList = Array.isArray(skills) ? skills : skills?.items || skills?.skills || []
const templates = await getJson('/api/v1/templates')
const templateList = Array.isArray(templates) ? templates : templates?.items || templates?.templates || []

const firstAgent = agentList[0]?.id
const firstSkill = skillList[0]?.id || skillList[0]?.slug
const firstTemplate = templateList[0]?.id

console.log('准备数据:')
console.log('  agents   =', agentList.length, firstAgent ? `(首个 ${String(firstAgent).slice(0, 8)}…)` : '')
console.log('  skills   =', skillList.length, firstSkill ? `(首个 ${String(firstSkill).slice(0, 12)}…)` : '')
console.log('  templates=', templateList.length, firstTemplate ? `(首个 ${String(firstTemplate).slice(0, 8)}…)` : '')

// ---------------------------------------------------------------- 路由清单

const ROUTES = [
  { path: '/', name: 'landing', auth: false },
  { path: '/templates', name: 'template-market', auth: false },
  { path: '/login', name: 'login', auth: false },
  { path: '/register', name: 'register', auth: false },
  { path: '/dashboard', name: 'dashboard', auth: true },
  { path: '/agents', name: 'agent-list', auth: true },
  { path: '/agents/new', name: 'agent-create', auth: true },
  { path: '/conversations', name: 'conversations', auth: true },
  { path: '/knowledge', name: 'knowledge', auth: true },
  { path: '/skills', name: 'skill-plaza', auth: true },
  { path: '/settings', name: 'settings', auth: true },
  { path: '/help', name: 'help', auth: true },
]
if (firstAgent) ROUTES.push({ path: `/agents/${firstAgent}/chat`, name: 'chat', auth: true })
if (firstAgent) ROUTES.push({ path: `/agents/${firstAgent}/edit`, name: 'agent-edit', auth: true })
if (firstSkill) ROUTES.push({ path: `/skills/${firstSkill}`, name: 'skill-chat', auth: true })
// 注意：/workflow/:id 接的是 **agent id**（AgentListPage 用 /workflow/${agent.id} 跳转），
// 传模板 id 会 404 —— 那是测试数据用错，不是应用缺陷
if (firstAgent) ROUTES.push({ path: `/workflow/${firstAgent}`, name: 'workflow-editor', auth: true })

const targets = only ? ROUTES.filter((r) => only.includes(r.name) || only.includes(r.path)) : ROUTES

// ---------------------------------------------------------------- 启动浏览器

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
    /* 还没起来 */
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

// 当前页面的事件桶
let bucket = { console: [], exceptions: [], failedRequests: [], requestFailures: [] }

ws.addEventListener('message', (ev) => {
  const msg = JSON.parse(ev.data)
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id)
    pending.delete(msg.id)
    msg.error ? reject(new Error(JSON.stringify(msg.error))) : resolve(msg.result)
    return
  }

  if (msg.method === 'Runtime.consoleAPICalled' && ['error', 'warning', 'assert'].includes(msg.params.type)) {
    bucket.console.push({
      level: msg.params.type,
      text: msg.params.args
        .map((a) => a.value ?? a.description ?? a.unserializableValue ?? a.type)
        .join(' ')
        .slice(0, 400),
    })
  }

  if (msg.method === 'Runtime.exceptionThrown') {
    const d = msg.params.exceptionDetails
    bucket.exceptions.push({
      text: (d.exception?.description || d.text || '').slice(0, 600),
      url: d.url,
      line: d.lineNumber,
    })
  }

  if (msg.method === 'Network.responseReceived') {
    const { response, type } = msg.params
    if (response.status >= 400 && !response.url.startsWith('data:')) {
      bucket.failedRequests.push({
        status: response.status,
        url: response.url.replace(BACKEND, '').replace(FRONTEND, ''),
        resourceType: type,
      })
    }
  }

  if (msg.method === 'Network.loadingFailed') {
    bucket.requestFailures.push({
      url: (msg.params.requestId || '').slice(0, 12),
      errorText: msg.params.errorText,
      type: msg.params.type,
    })
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

await send('Page.enable')
await send('Runtime.enable')
await send('Network.enable')
await send('Log.enable')

// 注入 token
await send('Page.navigate', { url: `${FRONTEND}/login` })
await sleep(2000)
await evaluate(`localStorage.setItem('token', ${JSON.stringify(token)})`)

// ---------------------------------------------------------------- 逐页巡检

const report = []

for (const route of targets) {
  bucket = { console: [], exceptions: [], failedRequests: [], requestFailures: [] }

  await send('Page.navigate', { url: `${FRONTEND}${route.path}` })
  await sleep(route.name === 'workflow-editor' ? 4500 : 3000)

  const finalUrl = await evaluate(`location.pathname`)
  const bodyText = await evaluate(`document.body.innerText.slice(0, 300)`)

  const shotName = `${route.name.replace(/[^\w-]/g, '_')}.png`
  try {
    const { data } = await send('Page.captureScreenshot', { format: 'png' })
    fs.writeFileSync(path.join(SHOT_DIR, shotName), Buffer.from(data, 'base64'))
  } catch {
    /* 截图失败不影响诊断 */
  }

  const entry = {
    ...route,
    finalUrl,
    redirected: finalUrl !== route.path,
    bodyPreview: bodyText,
    shot: shotName,
    ...bucket,
  }
  report.push(entry)

  const problems =
    bucket.console.filter((c) => c.level === 'error').length +
    bucket.exceptions.length +
    bucket.failedRequests.length
  const flag = entry.redirected ? '↪ 跳转' : problems ? `⚠ ${problems} 个问题` : '✓'
  console.log(`\n[${route.name}] ${route.path} -> ${finalUrl}  ${flag}`)

  for (const c of bucket.console) {
    if (c.level === 'error') console.log(`    ✗ console.error: ${c.text}`)
  }
  for (const e of bucket.exceptions) console.log(`    ✗ exception: ${e.text.split('\n')[0]}`)
  for (const f of bucket.failedRequests) console.log(`    ✗ HTTP ${f.status} ${f.resourceType} ${f.url}`)
}

// ---------------------------------------------------------------- 汇总

const outFile = path.join(SHOT_DIR, 'report.json')
fs.writeFileSync(outFile, JSON.stringify(report, null, 2), 'utf-8')

const allWarnings = report.flatMap((r) => r.console.filter((c) => c.level === 'warning').map((c) => c.text))
const warningKinds = {}
for (const w of allWarnings) {
  const key = w.slice(0, 90)
  warningKinds[key] = (warningKinds[key] || 0) + 1
}

console.log('\n================ 汇总 ================')
console.log('巡检页面数:', report.length)
console.log('错误页数:', report.filter((r) => r.console.some((c) => c.level === 'error') || r.exceptions.length || r.failedRequests.length).length)
console.log('异常跳转:', report.filter((r) => r.redirected).map((r) => `${r.name} -> ${r.finalUrl}`).join(', ') || '无')
console.log('\n失败请求汇总:')
const failedMap = {}
for (const r of report) {
  for (const f of r.failedRequests) {
    const key = `HTTP ${f.status} ${f.url}`
    if (!failedMap[key]) failedMap[key] = []
    failedMap[key].push(r.name)
  }
}
if (Object.keys(failedMap).length === 0) console.log('  无')
for (const [key, pages] of Object.entries(failedMap)) console.log(`  ${key}  ← ${pages.join(', ')}`)

console.log('\n异常汇总:')
const excMap = {}
for (const r of report) {
  for (const e of r.exceptions) {
    const key = e.text.split('\n')[0].slice(0, 160)
    if (!excMap[key]) excMap[key] = []
    excMap[key].push(r.name)
  }
}
if (Object.keys(excMap).length === 0) console.log('  无')
for (const [key, pages] of Object.entries(excMap)) console.log(`  ${key}  ← ${pages.join(', ')}`)

console.log('\n警告汇总（去重）:')
if (Object.keys(warningKinds).length === 0) console.log('  无')
for (const [key, count] of Object.entries(warningKinds).sort((a, b) => b[1] - a[1])) {
  console.log(`  x${count}  ${key}`)
}

console.log('\n报告文件:', outFile)
console.log('截图目录:', SHOT_DIR)

ws.close()
edge.kill()
await sleep(400)
process.exit(0)
