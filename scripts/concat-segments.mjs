// 把分段录制的四段拼成一条完整宣传片。
//
//   node scripts/concat-segments.mjs                 # 拼 seg-1 ~ seg-4
//   node scripts/concat-segments.mjs promo-final     # 自定义产物名
//
// 四段都是同一套编码参数（1440x900 / 30fps / yuv420p / libx264），
// 所以直接走 concat demuxer + `-c copy`：不重编码，几秒出片，画质零损失。
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'

const HERE = path.dirname(fileURLToPath(import.meta.url))
const REPO = path.resolve(HERE, '..')
const VIDEO_DIR = path.join(REPO, 'assets', 'videos')
const OUT_NAME = process.argv[2] || 'agentflow-promo'
const FFMPEG = process.env.FFMPEG || 'ffmpeg'

// 序号前缀就是成片顺序
const parts = fs
  .readdirSync(VIDEO_DIR)
  .filter((f) => /^seg-\d+-.*\.mp4$/.test(f))
  .sort()

if (parts.length === 0) {
  console.error('没找到 seg-*.mp4，先跑：node scripts/ui-record.mjs seg-landing 等')
  process.exit(1)
}

console.log('[拼接顺序]')
for (const p of parts) {
  const size = (fs.statSync(path.join(VIDEO_DIR, p)).size / 1048576).toFixed(2)
  console.log(`  ${p}  ${size} MB`)
}

const listFile = path.join(HERE, '_concat-list.txt')
fs.writeFileSync(
  listFile,
  parts.map((p) => `file '${path.join(VIDEO_DIR, p).replace(/\\/g, '/')}'`).join('\n'),
  'utf8'
)

const out = path.join(VIDEO_DIR, `${OUT_NAME}.mp4`)
const r = spawnSync(
  FFMPEG,
  [
    '-y', '-hide_banner', '-loglevel', 'error',
    '-f', 'concat', '-safe', '0',
    '-i', listFile.replace(/\\/g, '/'),
    '-c', 'copy',
    '-movflags', '+faststart',
    out,
  ],
  { encoding: 'utf8' }
)

fs.rmSync(listFile, { force: true })

if (r.status !== 0) {
  console.error('[拼接失败] ' + (r.stderr || r.error))
  process.exit(1)
}

const probe = spawnSync(
  FFMPEG === 'ffmpeg' ? 'ffprobe' : 'ffprobe',
  ['-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', out],
  { encoding: 'utf8' }
)
const dur = Number(String(probe.stdout).trim() || 0)
console.log(
  `[完成] ${path.relative(REPO, out)}  ${(fs.statSync(out).size / 1048576).toFixed(2)} MB  ` +
    `${dur ? `时长=${dur.toFixed(1)}s（${Math.floor(dur / 60)}分${Math.round(dur % 60)}秒）` : ''}`
)
