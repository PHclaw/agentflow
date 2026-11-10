import ReactMarkdown, { type Components, type Options } from 'react-markdown'
import remarkGfm from 'remark-gfm'
import remarkBreaks from 'remark-breaks'
import rehypeRaw from 'rehype-raw'
import rehypeSanitize, { defaultSchema } from 'rehype-sanitize'
import { cn } from '../../lib/utils'

/**
 * 渲染模型回复中的 Markdown 与 HTML。
 *
 * 两条硬约束：
 *
 * 1. 不新增任何全局 CSS。所有样式都通过 `components` 挂到具体元素上，
 *    因此不会与 index.css 里已有的规则产生作用域冲突 —— 该文件里存在
 *    `.dark .bg-slate-100 { ... }` 这类按类名匹配的全局覆盖，且未包在
 *    @layer 中（无层级样式的优先级高于所有 @layer，包括 utilities），
 *    一旦重名就会把 Tailwind 的 dark: 变体压掉。
 *
 * 2. 因此这里的类名刻意避开被全局覆盖的记号：
 *    bg-white / bg-slate-50 / bg-slate-100 / border-slate-200 /
 *    text-slate-400 / text-slate-500 / text-slate-600 / text-slate-700 / text-slate-900
 *    需要同类效果时改用未被覆盖的记号（如 bg-slate-200/60、text-slate-800）。
 *
 * 安全：先 rehype-raw 解析内联 HTML，再 rehype-sanitize 按白名单过滤。
 * 默认 schema 会剥离 style、class 与 on* 事件属性，所以模型即使输出
 * HTML 也不会污染页面样式，更不会执行脚本。
 */

const schema = {
  ...defaultSchema,
  tagNames: [
    ...new Set([...(defaultSchema.tagNames ?? []), 'kbd', 'mark', 'details', 'summary']),
  ],
  // 默认 schema 只「拆标签、留文本」，于是 <style>body{...}</style> 的 CSS
  // 会变成可见正文。这里连子节点一起删掉。
  strip: [...new Set([...(defaultSchema.strip ?? []), 'script', 'style'])],
}

// 显式标注类型：直接写字面量数组时，带参数的插件元组无法被正确推断
const remarkPlugins: Options['remarkPlugins'] = [remarkGfm, remarkBreaks]
const rehypePlugins: Options['rehypePlugins'] = [rehypeRaw, [rehypeSanitize, schema]]

const components: Components = {
  h1: ({ children }) => <h1 className="text-xl font-semibold mt-5 mb-2.5 first:mt-0">{children}</h1>,
  h2: ({ children }) => <h2 className="text-lg font-semibold mt-5 mb-2.5 first:mt-0">{children}</h2>,
  h3: ({ children }) => <h3 className="text-base font-semibold mt-4 mb-2 first:mt-0">{children}</h3>,
  h4: ({ children }) => <h4 className="text-sm font-semibold mt-4 mb-2 first:mt-0">{children}</h4>,
  h5: ({ children }) => <h5 className="text-sm font-semibold mt-3 mb-1.5 first:mt-0">{children}</h5>,
  h6: ({ children }) => <h6 className="text-sm font-semibold mt-3 mb-1.5 first:mt-0">{children}</h6>,

  p: ({ children }) => <p className="my-2.5 first:mt-0 last:mb-0">{children}</p>,

  ul: ({ children }) => (
    <ul className="my-2.5 pl-5 list-disc space-y-1 marker:text-slate-400">{children}</ul>
  ),
  ol: ({ children }) => (
    <ol className="my-2.5 pl-5 list-decimal space-y-1 marker:text-slate-400">{children}</ol>
  ),
  li: ({ children }) => <li className="pl-0.5">{children}</li>,

  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-slate-300 dark:border-slate-600 pl-3.5">
      {children}
    </blockquote>
  ),

  // 行内代码。背景刻意避开被全局覆盖的 bg-slate-100，
  // 否则 dark 模式下 `.dark .bg-slate-100` 会压掉这里的取值。
  code: ({ children, className }) => (
    <code
      className={cn(
        'rounded bg-slate-200/60 dark:bg-slate-800 px-1.5 py-0.5',
        'font-mono text-[13px] text-slate-800 dark:text-slate-200',
        className
      )}
    >
      {children}
    </code>
  ),

  // 代码块。用子选择器把内部 code 的行内样式归零，
  // 这样无论围栏是否带语言标识都能正确显示。
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-200/40 dark:bg-slate-900 p-3.5 [&>code]:bg-transparent [&>code]:p-0 [&>code]:text-[13px] [&>code]:text-slate-800 dark:[&>code]:text-slate-200">
      {children}
    </pre>
  ),

  // 表格外再包一层横向滚动，避免宽表格把消息区撑破
  table: ({ children }) => (
    <div className="my-3 w-full overflow-x-auto">
      <table className="w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  th: ({ children }) => (
    <th className="border border-slate-200 dark:border-slate-700 px-3 py-1.5 text-left font-semibold">
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td className="border border-slate-200 dark:border-slate-700 px-3 py-1.5 align-top">
      {children}
    </td>
  ),

  a: ({ children, href }) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="text-blue-600 dark:text-blue-400 underline underline-offset-2 hover:text-blue-700 dark:hover:text-blue-300 break-all"
    >
      {children}
    </a>
  ),
  img: ({ src, alt }) => (
    <img src={src} alt={alt ?? ''} className="my-3 max-w-full rounded-lg" loading="lazy" />
  ),
  hr: () => <hr className="my-5 border-slate-200 dark:border-slate-700" />,
  strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
  del: ({ children }) => <del className="line-through opacity-70">{children}</del>,
  // 任务列表的复选框
  input: ({ checked, type }) =>
    type === 'checkbox' ? (
      <input
        type="checkbox"
        checked={Boolean(checked)}
        readOnly
        className="mr-1.5 h-3.5 w-3.5 align-middle accent-slate-700"
      />
    ) : null,
}

interface MarkdownProps {
  /** Markdown / HTML 源文本 */
  content: string
  className?: string
}

export function Markdown({ content, className }: MarkdownProps) {
  return (
    <div className={cn('break-words leading-relaxed', className)}>
      <ReactMarkdown
        remarkPlugins={remarkPlugins}
        rehypePlugins={rehypePlugins}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  )
}

export default Markdown
