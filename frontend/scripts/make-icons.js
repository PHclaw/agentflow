/**
 * 从站内标识生成 App 图标源图（供 @capacitor/assets 使用）。
 *
 * 几何完全照搬 `src/components/layout/Logo.tsx` 里的 AFMark（viewBox 0 0 68 50），
 * 这样桌面图标和网页里的标识是同一个形状，不会出现「两套 logo」。
 *
 * 用法：npm run icons      # 生成源图 + 产出 Android 各密度图标与启动图
 */
const fs = require('fs')
const path = require('path')
const sharp = require('sharp')

const OUT_DIR = path.join(__dirname, '..', 'assets')
const SIZE = 1024

// 深色底上藏青提亮成近白（对应 Logo.tsx 的 NAVY_ON_DARK），否则深蓝画深蓝看不见
const NAVY = '#E7EBF5'
const CYAN = '#00BFEF'
const BG = '#091B4D'
const PAD_REACH = 5.8

const mark = `
  <g stroke-linecap="round" fill="none">
    <path d="M30 3 L11.9 35.9" stroke="${NAVY}" stroke-width="5.5"/>
    <path d="M30 3 L40 16" stroke="${NAVY}" stroke-width="5.5"/>
    <circle cx="9" cy="41" r="4.6" stroke="${NAVY}" stroke-width="3.2"/>

    <path d="M35 24 L35 ${41 - PAD_REACH}" stroke="${CYAN}" stroke-width="5.5"/>
    <path d="M35 24 L${58 - PAD_REACH} 24" stroke="${CYAN}" stroke-width="5.5"/>
    <circle cx="35" cy="41" r="4.6" stroke="${CYAN}" stroke-width="3.2"/>
    <circle cx="58" cy="24" r="4.6" stroke="${CYAN}" stroke-width="3.2"/>
    <path d="M35 32.5 L50 32.5" stroke="${CYAN}" stroke-width="5.5"/>
  </g>
`

/** 把 68x50 的字标按 occupy 比例居中放进 canvas */
function markGroup(occupy, canvas = SIZE) {
  const w = canvas * occupy
  const h = (w * 50) / 68
  const x = (canvas - w) / 2
  const y = (canvas - h) / 2
  const s = w / 68
  return `<g transform="translate(${x} ${y}) scale(${s})">${mark}</g>`
}

const svg = (body, bg, w = SIZE, h = SIZE) =>
  `<svg xmlns="http://www.w3.org/2000/svg" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}">${bg}${body}</svg>`

// 自适应图标前景：透明底。生成的 adaptive-icon XML 会再套一层 16.7% inset
// （108dp 画布 → 72dp 安全区），所以这里接近铺满，最终视觉大小才和方形图标一致
const foreground = svg(markGroup(0.92), '')

// 传统方形图标（Android 7 及以下 / 部分启动器）
const squareIcon = svg(
  markGroup(0.62),
  `<rect width="${SIZE}" height="${SIZE}" rx="220" fill="${BG}"/>`
)

// 圆形图标
const roundIcon = svg(
  markGroup(0.56),
  `<circle cx="${SIZE / 2}" cy="${SIZE / 2}" r="${SIZE / 2}" fill="${BG}"/>`
)

// 自适应图标背景层
const background = svg('', `<rect width="${SIZE}" height="${SIZE}" fill="${BG}"/>`)

// 启动图：深底 + 居中标识
const splash = (() => {
  const w = 1080 * 0.5
  const h = (w * 50) / 68
  return svg(
    `<g transform="translate(${(1080 - w) / 2} ${(1920 - h) / 2}) scale(${w / 68})">${mark}</g>`,
    `<rect width="1080" height="1920" fill="${BG}"/>`,
    1080,
    1920
  )
})()

async function main() {
  fs.mkdirSync(OUT_DIR, { recursive: true })
  const out = (name, content) =>
    sharp(Buffer.from(content)).png().toFile(path.join(OUT_DIR, name))

  await out('icon-foreground.png', foreground)
  await out('icon-only.png', squareIcon)
  await out('icon-round.png', roundIcon)
  await out('icon-background.png', background)
  await out('splash.png', splash)

  console.log('icons written to', OUT_DIR)
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
