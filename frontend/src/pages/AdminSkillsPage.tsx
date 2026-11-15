import { useCallback, useEffect, useRef, useState } from 'react'
import {
  AlertTriangle,
  ChevronLeft,
  EyeOff,
  FileCode2,
  Pencil,
  Plus,
  RefreshCw,
  Trash2,
  Upload,
} from 'lucide-react'
import { admin as adminApi } from '../services/api'
import type { AdminSkill, AdminSkillDetail, SkillWritePayload } from '../services/api'
import { Button } from '../components/ui/Button'
import { Card } from '../components/ui/Card'
import { Modal } from '../components/ui/Modal'
import { useToastStore } from '../stores'
import { formatRelative } from '../utils/datetime'

/**
 * 管理后台 · 技能管理
 *
 * 技能广场的技能是**文件**（`skills/<slug>/SKILL.md`）而不是数据库行，
 * 这个页面就是把「手工建目录写文件」这件事搬进界面。增删改最终都落在
 * 磁盘上，后端负责 slug 校验、原子写和缓存失效。
 */

/** 新技能的默认 frontmatter。只放最必要的几项，其余交给后端补默认值。 */
const EMPTY_FRONTMATTER: Record<string, any> = {
  name: '',
  description: '',
  specialty: '',
  routerBlurb: '',
  triggers: [],
  tags: [],
  version: 'v1.0.0',
  systemPrompt: '',
  userPrompt: '请根据以下材料处理：\n\n{{input}}',
  variables: [{ name: 'input', type: 'string' }],
  authorName: '平台预置',
}

const EMPTY_BODY = `# 技能名称

## 目标
一句话说清这个技能做什么。

## 输入变量
- \`input\`

## 调用 Prompt

### System
\`\`\`text
（与上方 systemPrompt 保持一致）
\`\`\`

### User
\`\`\`text
请根据以下材料处理：

{{input}}
\`\`\`
`

export default function AdminSkillsPage() {
  const { addToast } = useToastStore()

  const [items, setItems] = useState<AdminSkill[]>([])
  const [loading, setLoading] = useState(false)
  const [detail, setDetail] = useState<AdminSkillDetail | null>(null)
  const [detailLoading, setDetailLoading] = useState(false)

  // 编辑器状态。editing 为 null 表示「新建」
  const [editorOpen, setEditorOpen] = useState(false)
  const [editingSlug, setEditingSlug] = useState<string | null>(null)
  const [formSlug, setFormSlug] = useState('')
  const [formMeta, setFormMeta] = useState(EMPTY_FRONTMATTER)
  const [formBody, setFormBody] = useState(EMPTY_BODY)
  const [saving, setSaving] = useState(false)

  const [deleting, setDeleting] = useState<AdminSkill | null>(null)
  const [deleteBusy, setDeleteBusy] = useState(false)

  // 技能包导入。zip 是第三方整包下载来的，所以走「先预览再确认导入」两步 ——
  // 直接导的话，slug 撞了或包缺字段要到写完了才发现。
  const [importOpen, setImportOpen] = useState(false)
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importPreview, setImportPreview] = useState<any>(null)
  const [importSlug, setImportSlug] = useState('')
  const [importOverwrite, setImportOverwrite] = useState(false)
  const [importBusy, setImportBusy] = useState(false)
  const [importError, setImportError] = useState('')
  // 覆盖值。第三方包的字段往往不符合 AgentFlow 的约定（尤其 description
  // 常是一整段英文说明），预览后预填，管理员改了就覆盖包里的。
  const [importSkillPath, setImportSkillPath] = useState('')
  const [importName, setImportName] = useState('')
  const [importDescription, setImportDescription] = useState('')
  const [importSystemPrompt, setImportSystemPrompt] = useState('')
  const pkgInputRef = useRef<HTMLInputElement>(null)

  const load = useCallback(async () => {
    setLoading(true)
    try {
      const res: any = await adminApi.skills()
      setItems(res?.items ?? res ?? [])
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '加载技能列表失败' })
    } finally {
      setLoading(false)
    }
  }, [addToast])

  useEffect(() => {
    load()
  }, [load])

  const openDetail = async (slug: string) => {
    setDetailLoading(true)
    setDetail(null)
    try {
      const res: any = await adminApi.skillDetail(slug)
      setDetail(res)
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '加载技能详情失败' })
    } finally {
      setDetailLoading(false)
    }
  }

  const openCreate = () => {
    setEditingSlug(null)
    setFormSlug('')
    setFormMeta({ ...EMPTY_FRONTMATTER, triggers: [], tags: [], variables: [{ name: 'input', type: 'string' }] })
    setFormBody(EMPTY_BODY)
    setEditorOpen(true)
  }

  // ---- 技能包导入 ----
  const onPickPackage = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''   // 清空，否则同一个文件第二次选不到 change 事件
    if (!file) return

    setImportFile(file)
    setImportOpen(true)
    setImportSkillPath('')
    setImportOverwrite(false)
    await runPreview(file, '')
  }

  /**
   * 跑一次预览。
   *
   * 单独接受 skillPath 是因为仓库整包里可能有多个技能：自动识别失败
   * （同深度多个候选）时后端会在错误里列出候选，管理员填进来点「重新检查」
   * 即可。没有这条路，那个错误就是个死胡同 —— 确认按钮依赖 preview。
   */
  const runPreview = async (file: File, skillPath: string) => {
    setImportPreview(null)
    setImportError('')
    setImportSlug('')
    setImportName('')
    setImportDescription('')
    setImportSystemPrompt('')
    setImportBusy(true)
    try {
      const res: any = await adminApi.previewSkillPackage(file, {
        skillPath: skillPath.trim() || undefined,
      })
      setImportPreview(res)
      setImportSlug(res.slug)
      setImportSkillPath(res.skill_path || '')
      // 预填包里的值：管理员不动就是沿用，动哪项就覆盖哪项
      setImportName(res.name || '')
      setImportDescription(res.description || '')
      if (res.exists) setImportOverwrite(false)
    } catch (err: any) {
      setImportError(err?.message || '解析技能包失败')
    } finally {
      setImportBusy(false)
    }
  }

  const confirmImport = async () => {
    if (!importFile) return
    setImportBusy(true)
    setImportError('')
    try {
      const res: any = await adminApi.importSkillPackage(importFile, {
        slug: importSlug.trim() || undefined,
        overwrite: importOverwrite,
        skillPath: importSkillPath.trim() || undefined,
        name: importName.trim() || undefined,
        description: importDescription.trim() || undefined,
        systemPrompt: importSystemPrompt.trim() || undefined,
      })
      addToast({
        type: 'success',
        message: `技能包「${res.name}」已导入（${res.file_count} 个文件）`,
      })
      setImportOpen(false)
      await load()
    } catch (err: any) {
      // 409 是「已存在」，把覆盖选项直接推到用户面前，而不是让他再走一遍
      if (err?.status === 409 || /已存在/.test(err?.message || '')) {
        setImportError('该技能已存在。确认要覆盖请勾选下方「覆盖已存在的技能」。')
        setImportOverwrite(false)
      } else {
        setImportError(err?.message || '导入失败')
      }
    } finally {
      setImportBusy(false)
    }
  }

  const openEdit = (skill: AdminSkill) => {
    setEditingSlug(skill.slug)
    setFormSlug(skill.slug)
    setDetailLoading(true)
    setEditorOpen(true)
    // 详情里才有 frontmatter 与正文，编辑前必须先拉一次
    adminApi
      .skillDetail(skill.slug)
      .then((res: any) => {
        setFormMeta(res.frontmatter || {})
        setFormBody(res.body || '')
      })
      .catch((e: any) => {
        addToast({ type: 'error', message: e?.message || '加载技能内容失败' })
        setEditorOpen(false)
      })
      .finally(() => setDetailLoading(false))
  }

  const submit = async () => {
    const payload: SkillWritePayload = {
      slug: formSlug.trim(),
      frontmatter: formMeta,
      body: formBody,
    }
    if (!payload.slug) {
      addToast({ type: 'error', message: '请填写 slug（目录名）' })
      return
    }
    if (!String(formMeta.name || '').trim()) {
      addToast({ type: 'error', message: '请填写技能名称（name）' })
      return
    }
    if (!String(formMeta.systemPrompt || '').trim()) {
      addToast({ type: 'error', message: '请填写 systemPrompt，否则技能能加载但产出空内容' })
      return
    }

    setSaving(true)
    try {
      if (editingSlug) {
        await adminApi.updateSkill(editingSlug, payload)
        addToast({ type: 'success', message: `技能 ${payload.slug} 已更新` })
      } else {
        await adminApi.createSkill(payload)
        addToast({ type: 'success', message: `技能 ${payload.slug} 已创建` })
      }
      setEditorOpen(false)
      await load()
      if (detail?.slug === payload.slug) await openDetail(payload.slug)
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '保存失败' })
    } finally {
      setSaving(false)
    }
  }

  const confirmDelete = async () => {
    if (!deleting) return
    setDeleteBusy(true)
    try {
      await adminApi.deleteSkill(deleting.slug)
      addToast({ type: 'success', message: `技能 ${deleting.slug} 已删除` })
      setDeleting(null)
      if (detail?.slug === deleting.slug) setDetail(null)
      await load()
    } catch (e: any) {
      addToast({ type: 'error', message: e?.message || '删除失败' })
    } finally {
      setDeleteBusy(false)
    }
  }

  const visible = items.filter((s) => !s.hidden).length

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="sm" onClick={() => history.back()}>
            <ChevronLeft className="w-4 h-4" />
          </Button>
          <div>
            <h1 className="text-xl font-semibold text-slate-900 dark:text-white">技能管理</h1>
            <p className="text-sm text-slate-500 dark:text-slate-400">
              共 {items.length} 个技能，其中 {visible} 个在广场可见
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={load} disabled={loading}>
            <RefreshCw className={`w-4 h-4 mr-1.5 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </Button>
          {/* 导入第三方技能包。input 用 ref 持有，Button 显式触发 ——
              button 放在 label 里不会把点击转发给 input。 */}
          <input
            ref={pkgInputRef}
            type="file"
            accept=".zip,application/zip"
            className="hidden"
            onChange={onPickPackage}
            disabled={importBusy}
          />
          <Button
            variant="outline"
            size="sm"
            disabled={importBusy}
            onClick={() => pkgInputRef.current?.click()}
          >
            <Upload className="w-4 h-4 mr-1.5" />
            导入技能包
          </Button>
          <Button size="sm" onClick={openCreate}>
            <Plus className="w-4 h-4 mr-1.5" />
            新建技能
          </Button>
        </div>
      </div>

      {/* 技能以文件形式存在，改完即生效 —— 这点值得显式说明，
          否则管理员会以为是数据库记录、去找「发布」按钮 */}
      <div className="flex items-start gap-2 p-3 rounded-xl bg-brand-50 dark:bg-brand-900/20 text-sm text-slate-600 dark:text-slate-300">
        <FileCode2 className="w-4 h-4 mt-0.5 shrink-0 text-brand-600 dark:text-brand-400" />
        <p>
          技能以 <code className="px-1 rounded bg-white dark:bg-slate-800">skills/&lt;slug&gt;/SKILL.md</code> 的形式
          存放在服务端磁盘上，保存后立即生效，无需重启。
        </p>
      </div>

      {loading && items.length === 0 && (
        <Card className="p-8 text-center text-sm text-slate-500">正在加载…</Card>
      )}

      {!loading && items.length === 0 && (
        <Card className="p-8 text-center text-sm text-slate-500">还没有技能</Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {items.map((skill) => (
          <Card key={skill.slug} className="p-5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <h3 className="font-medium text-slate-900 dark:text-white truncate">
                    {skill.name}
                  </h3>
                  {skill.hidden && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 dark:bg-slate-800 text-slate-500 text-xs">
                      <EyeOff className="w-3 h-3" />
                      广场不可见
                    </span>
                  )}
                  {skill.broken && (
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400 text-xs">
                      <AlertTriangle className="w-3 h-3" />
                      配置损坏
                    </span>
                  )}
                </div>
                <p className="mt-0.5 text-xs text-slate-400 font-mono">{skill.slug}</p>
              </div>
              <div className="flex items-center gap-1 shrink-0">
                <Button variant="ghost" size="sm" onClick={() => openDetail(skill.slug)}>
                  详情
                </Button>
                <Button variant="ghost" size="sm" onClick={() => openEdit(skill)}>
                  <Pencil className="w-4 h-4" />
                </Button>
                <Button variant="ghost" size="sm" onClick={() => setDeleting(skill)}>
                  <Trash2 className="w-4 h-4 text-red-500" />
                </Button>
              </div>
            </div>

            {skill.broken ? (
              // 解析失败的技能在广场里是直接消失的，必须把原因摆到明面上
              <p className="mt-3 text-sm text-red-600 dark:text-red-400">
                {skill.broken}
              </p>
            ) : (
              <p className="mt-3 text-sm text-slate-600 dark:text-slate-400 line-clamp-2">
                {skill.description || '（无描述）'}
              </p>
            )}

            <div className="mt-3 flex items-center gap-3 text-xs text-slate-400">
              {skill.version && <span>{skill.version}</span>}
              <span>调用 {skill.total_calls} 次</span>
              {skill.has_scripts && <span>含脚本</span>}
              {skill.updated_at && <span>改于 {formatRelative(skill.updated_at)}</span>}
            </div>
          </Card>
        ))}
      </div>

      {/* ---- 详情 ---- */}
      <Modal
        isOpen={!!detail}
        onClose={() => setDetail(null)}
        title={detail ? `技能详情 · ${detail.name}` : ''}
        size="xl"
      >
        {detailLoading && <p className="text-sm text-slate-500">正在加载…</p>}
        {detail && !detailLoading && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 text-sm">
              <Field label="slug" value={detail.slug} mono />
              <Field label="id" value={detail.id} mono />
              <Field label="专业方向" value={detail.specialty || '—'} />
              <Field label="作者" value={detail.author_name || '—'} />
              <Field label="可见性" value={`${detail.visibility} / ${detail.status}`} />
              <Field label="调用次数" value={String(detail.total_calls)} />
            </div>
            {detail.description && (
              <div>
                <p className="text-xs font-medium text-slate-500 mb-1">描述</p>
                <p className="text-sm text-slate-700 dark:text-slate-300 whitespace-pre-wrap">
                  {detail.description}
                </p>
              </div>
            )}
            <div>
              <p className="text-xs font-medium text-slate-500 mb-1">frontmatter</p>
              <pre className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 text-xs overflow-auto max-h-64">
                {JSON.stringify(detail.frontmatter, null, 2)}
              </pre>
            </div>
            <div>
              <p className="text-xs font-medium text-slate-500 mb-1">正文</p>
              <pre className="p-3 rounded-xl bg-slate-50 dark:bg-slate-800/60 text-xs overflow-auto max-h-64 whitespace-pre-wrap">
                {detail.body || '（空）'}
              </pre>
            </div>
          </div>
        )}
      </Modal>

      {/* ---- 编辑器 ---- */}
      <Modal
        isOpen={editorOpen}
        onClose={() => setEditorOpen(false)}
        title={editingSlug ? `编辑技能 · ${editingSlug}` : '新建技能'}
        size="xl"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              slug（目录名）
            </label>
            <input
              value={formSlug}
              onChange={(e) => setFormSlug(e.target.value)}
              disabled={!!editingSlug}
              placeholder="weekly-report"
              className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm font-mono disabled:bg-slate-50 dark:disabled:bg-slate-800"
            />
            <p className="mt-1 text-xs text-slate-400">
              {editingSlug
                ? 'slug 不可修改 —— 改名请删除后重建'
                : '只能包含小写字母、数字和连字符，首字符必须是字母或数字'}
            </p>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              frontmatter（JSON）
            </label>
            <textarea
              value={JSON.stringify(formMeta, null, 2)}
              onChange={(e) => {
                try {
                  setFormMeta(JSON.parse(e.target.value))
                } catch {
                  // 输入中途的 JSON 必然不合法，不能因此打断用户输入。
                  // 真正校验放在提交时。
                }
              }}
              rows={16}
              className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-xs font-mono"
              spellCheck={false}
            />
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">正文（Markdown）</label>
            <textarea
              value={formBody}
              onChange={(e) => setFormBody(e.target.value)}
              rows={12}
              className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm font-mono"
              spellCheck={false}
            />
          </div>

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setEditorOpen(false)}>
              取消
            </Button>
            <Button onClick={submit} disabled={saving}>
              {saving ? '保存中…' : editingSlug ? '保存修改' : '创建技能'}
            </Button>
          </div>
        </div>
      </Modal>

      {/* ---- 删除确认 ---- */}
      <Modal
        isOpen={!!deleting}
        onClose={() => setDeleting(null)}
        title="删除技能"
        size="sm"
      >
        {deleting && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600 dark:text-slate-300">
              即将删除 <code className="px-1 rounded bg-slate-100 dark:bg-slate-800">{deleting.slug}</code>
              ，这会移除整个技能目录{deleting.has_scripts ? '（含 scripts/ 脚本）' : ''}，且无法恢复。
            </p>
            <div className="flex items-center justify-end gap-2">
              <Button variant="outline" onClick={() => setDeleting(null)}>
                取消
              </Button>
              <Button onClick={confirmDelete} disabled={deleteBusy}>
                {deleteBusy ? '删除中…' : '确认删除'}
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ---- 导入技能包 ---- */}
      <Modal
        isOpen={importOpen}
        onClose={() => setImportOpen(false)}
        title="导入技能包"
        size="lg"
      >
        <div className="space-y-4">
          <p className="text-[13px] text-slate-500 dark:text-slate-400">
            上传第三方技能包的 zip（含 <code className="px-1 rounded bg-slate-100 dark:bg-slate-800">SKILL.md</code>，
            可带 <code className="px-1 rounded bg-slate-100 dark:bg-slate-800">scripts/</code>）。
            自己打的扁平包和 GitHub 仓库整包都收 —— 整包会自动下钻到{' '}
            <code className="px-1 rounded bg-slate-100 dark:bg-slate-800">skills/&lt;名字&gt;/</code>，
            仓库里的 README、CI 配置、docs 截图不会被导进来。导入后立即生效，无需重启。
          </p>

          {importBusy && !importPreview && (
            <p className="text-[13px] text-slate-500">正在解析技能包…</p>
          )}

          {importError && (
            <p className="text-[13px] text-red-600 dark:text-red-400 whitespace-pre-wrap">
              {importError}
            </p>
          )}

          {/* 技能目录。刻意放在 importPreview 之外 —— 包里同深度有多个技能
              导致自动识别失败时，正是需要在这里指定的场合。 */}
          <div>
            <label className="block text-xs font-medium text-slate-500 mb-1">
              技能目录（包内路径，留空自动识别）
            </label>
            <div className="flex gap-2">
              <input
                value={importSkillPath}
                onChange={(e) => setImportSkillPath(e.target.value)}
                placeholder="例如 repo-main/skills/ppt-master"
                className="flex-1 px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm font-mono"
              />
              <Button
                variant="outline"
                onClick={() => importFile && runPreview(importFile, importSkillPath)}
                disabled={importBusy || !importFile}
              >
                重新检查
              </Button>
            </div>
          </div>

          {importPreview && (
            <>
              <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 space-y-2">
                <div className="flex items-center justify-between text-[13px]">
                  <span className="text-slate-500">名称</span>
                  <span className="font-medium text-slate-900 dark:text-white">
                    {importPreview.name}
                  </span>
                </div>
                <div className="flex items-center justify-between text-[13px]">
                  <span className="text-slate-500">slug</span>
                  <code className="text-slate-700 dark:text-slate-300">
                    {importPreview.slug}
                  </code>
                </div>
                <div className="flex items-center justify-between text-[13px]">
                  <span className="text-slate-500">文件</span>
                  <span className="text-slate-700 dark:text-slate-300">
                    {importPreview.file_count} 个 ·{' '}
                    {(importPreview.total_bytes / 1024).toFixed(1)} KB
                    {importPreview.has_scripts ? ' · 含脚本' : ''}
                  </span>
                </div>
                {importPreview.ignored_files > 0 && (
                  <div className="flex items-center justify-between text-[13px]">
                    <span className="text-slate-500">技能目录外的文件</span>
                    <span className="text-slate-500">
                      跳过 {importPreview.ignored_files} 个（README / CI / docs 等）
                    </span>
                  </div>
                )}
                {importPreview.exists && (
                  <p className="text-[13px] text-amber-600 dark:text-amber-400">
                    该技能已存在，导入将覆盖它（含其 scripts/）。
                  </p>
                )}
              </div>

              {importPreview.warnings.length > 0 && (
                <div className="space-y-1">
                  {importPreview.warnings.map((w: string, i: number) => (
                    <p key={i} className="flex items-start gap-1.5 text-[13px] text-amber-600 dark:text-amber-400">
                      <AlertTriangle className="w-3.5 h-3.5 mt-0.5 shrink-0" />
                      {w}
                    </p>
                  ))}
                </div>
              )}

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  slug（目录名，可修改）
                </label>
                <input
                  value={importSlug}
                  onChange={(e) => setImportSlug(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm font-mono"
                />
              </div>

              {/* 覆盖值。第三方包的字段常不符合 AgentFlow 的约定 ——
                  description 尤其典型，往往是一整段英文说明，直接进广场
                  没人看得懂。留空即沿用包里的值。 */}
              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  技能名称
                </label>
                <input
                  value={importName}
                  onChange={(e) => setImportName(e.target.value)}
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  广场描述
                </label>
                <textarea
                  value={importDescription}
                  onChange={(e) => setImportDescription(e.target.value)}
                  rows={2}
                  placeholder="用户在技能广场上会看到这句话"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm resize-y"
                />
              </div>

              <div>
                <label className="block text-xs font-medium text-slate-500 mb-1">
                  系统提示词（留空则沿用包里的，或由 SKILL.md 正文兜底）
                </label>
                <textarea
                  value={importSystemPrompt}
                  onChange={(e) => setImportSystemPrompt(e.target.value)}
                  rows={3}
                  placeholder="留空不改动"
                  className="w-full px-3 py-2 rounded-xl border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 text-sm font-mono resize-y"
                />
              </div>

              <label className="flex items-center gap-2 text-[13px] text-slate-600 dark:text-slate-300">
                <input
                  type="checkbox"
                  checked={importOverwrite}
                  onChange={(e) => setImportOverwrite(e.target.checked)}
                  className="rounded border-slate-300"
                />
                覆盖已存在的技能
              </label>
            </>
          )}

          <div className="flex items-center justify-end gap-2 pt-2">
            <Button variant="outline" onClick={() => setImportOpen(false)}>
              取消
            </Button>
            <Button
              onClick={confirmImport}
              disabled={importBusy || !importPreview}
            >
              {importBusy ? '导入中…' : '确认导入'}
            </Button>
          </div>
        </div>
      </Modal>
    </div>
  )
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return (
    <div>
      <p className="text-xs text-slate-400">{label}</p>
      <p className={`text-slate-700 dark:text-slate-300 ${mono ? 'font-mono text-xs' : ''}`}>
        {value}
      </p>
    </div>
  )
}
