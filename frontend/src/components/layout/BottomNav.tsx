import { NavLink, useLocation } from 'react-router-dom'
import {
  Bot,
  FileText,
  LayoutDashboard,
  Sparkles,
  User,
  type LucideIcon,
} from 'lucide-react'
import clsx from 'clsx'

/**
 * 全局底部导航栏（**仅移动端**）。
 *
 * 桌面端不显示
 * ------------
 * `lg:hidden`。桌面有 240px 常驻侧边栏，五项入口全在里面；底栏是 `fixed`
 * 定位，在桌面会浮在内容之上盖住工作流画布这类满屏区域。它只在宽 < 1024px
 * 时才有存在意义：那时侧边栏收进了抽屉，底栏是唯一随时可达的操作面。
 *
 * 只做导航，不做操作
 * ------------------
 * 这里**只放跳转**（去哪个功能区）。页面内的动作（创建、上传、刷新）留在
 * 各页自己的页头或内容区里 —— 曾经在知识库页试过再加一条「页面级快捷操作栏」
 * 叠在这条之上，结论是两条底栏吃掉 112px 视口、且入口与页面头部重复，已撤掉。
 * 所以现在全站底部**只有这一条**。
 *
 * 层级
 * ----
 *
 * | 层级    | 用途                   |
 * |---------|------------------------|
 * | z-30    | 应用顶栏（仅移动端）   |
 * | z-40    | 侧边栏抽屉遮罩         |
 * | z-50    | 侧边栏 / 落地页顶栏    |
 * | z-[70]  | **本组件**             |
 * | z-[100] | 浮窗 Modal             |
 * | z-[110] | Toast 提示             |
 *
 * 五档位与选中态
 * --------------
 * - 五项**等分**（`flex-1 basis-0`），所以标签文字长短不会让某档变宽变窄，
 *   换语言、换屏幕宽度布局都不跳。
 * - 选中态用三重反馈：图标与文字同时变强调色 + 顶部一条指示条 +
 *   `aria-current`。只用颜色区分对色觉障碍用户不友好，加一条位置指示更稳。
 */

interface NavItem {
  to: string
  icon: LucideIcon
  label: string
  /** 前缀匹配，用于详情页也要点亮对应档位（如 /skills/xyz） */
  prefix?: boolean
}

/**
 * 五个核心入口。
 *
 * 用户指定了三个：AI Agent、Skill 广场、个人信息。另外两个按「功能区是否
 * 独立」来补：
 *
 * - **控制台**：整个产品的落地页，用户登录后第一眼看到的汇总，也是回「首页」
 *   的唯一入口 —— 没有它用户得点 Logo，那是桌面端的习惯，手机上没有。
 * - **知识库**：与 Skill 广场同级的**资源面**（一个管技能、一个管资料），
 *   而 Agent 是消费方。三者构成「资源 → 消费」的主链路。
 *
 * 没放进去的：对话记录、工作流、模板市场、帮助。前三个都是**从某个 Agent
 * 进入**的下游页面（对话记录还要先选 Agent 才有意义），属于二级入口；
 * 帮助与设置同属「我的」，塞进设置页即可。五档位的空间有限，把二级入口
 * 放进来会把一级入口挤小。
 */
const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', icon: LayoutDashboard, label: '控制台' },
  { to: '/agents', icon: Bot, label: 'Agent', prefix: true },
  { to: '/skills', icon: Sparkles, label: 'Skill 广场', prefix: true },
  { to: '/knowledge', icon: FileText, label: '知识库', prefix: true },
  { to: '/settings', icon: User, label: '我的', prefix: true },
]

export function BottomNav() {
  const location = useLocation()

  const isActive = (item: NavItem) =>
    item.prefix
      ? location.pathname === item.to || location.pathname.startsWith(item.to + '/')
      : location.pathname === item.to

  return (
    <nav
      aria-label="主导航"
      className={clsx(
        // **只在移动端（< lg）出现。**
        //
        // 桌面端本来就有 240px 常驻侧边栏，这五项入口全都在里面，再挂一条
        // 底栏是重复入口；更糟的是它 `fixed` 在底部，会浮在内容之上 ——
        // 工作流编辑器那种满屏画布被压住一条，直接没法用。
        // 之前试过在桌面把它收成居中的浮岛，结论是多余，撤掉。
        'lg:hidden fixed inset-x-0 bottom-0 z-[70]',
        // 底部安全区：iPhone 的横条不能压住最后一排图标
        'pb-[env(safe-area-inset-bottom)]',
        // 通栏贴底，上方一条分割线。
        // 透明度只能用刻度内的值（5 的倍数）：`/92` 不在 Tailwind 默认刻度里，
        // 写出来**不会生成任何 CSS**，表现是整条栏没有底色 —— 而且不报错。
        'bg-white/90 dark:bg-slate-950/90 backdrop-blur-xl',
        'border-t border-slate-200 dark:border-slate-800'
      )}
    >
      <div className="flex items-stretch h-14">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon
          const active = isActive(item)
          return (
            <NavLink
              key={item.to}
              to={item.to}
              aria-current={active ? 'page' : undefined}
              className={clsx(
                // 相对定位：给顶部指示条做锚点
                'relative flex-1 basis-0 min-w-0 min-h-[44px]',
                'flex flex-col items-center justify-center gap-0.5',
                // 圆角在桌面浮岛里更明显，手机端几乎看不出，无副作用
                'mx-0.5 my-1 rounded-xl transition-colors',
                active
                  ? 'text-brand-600 dark:text-brand-400'
                  : 'text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200',
                'active:bg-slate-100 dark:active:bg-slate-800'
              )}
            >
              {/*
                顶部指示条。用一条短横而不是整块底色：底色会把五个档位涂成
                一列色块（侧边栏那轮已经踩过这个坑）。`-top-1` 让它贴在档位
                上沿，视觉上像一条「标签页指示线」。
              */}
              <span
                aria-hidden="true"
                className={clsx(
                  'absolute -top-1 h-0.5 w-6 rounded-full transition-opacity',
                  active ? 'bg-brand-600 dark:bg-brand-400 opacity-100' : 'opacity-0'
                )}
              />
              <Icon
                className="w-[19px] h-[19px] shrink-0"
                strokeWidth={active ? 2.2 : 1.8}
              />
              {/*
                标签。`text-[10px]` 起，360px 以上才放大到 11px —— 320px 的窄屏
                上「Skill 广场」按 11px 算约 50px，已经逼近 56px 的档位可用宽度，
                会挤到换行。nowrap + overflow-hidden 兜住极端情况，宁可截断
                也不换行（换行会让五个档位高度不一致，整条栏看起来是歪的）。
              */}
              <span
                className={clsx(
                  'max-w-full px-0.5 text-[10px] min-[360px]:text-[11px] leading-none',
                  'whitespace-nowrap overflow-hidden text-ellipsis transition-[font-weight]',
                  active && 'font-medium'
                )}
              >
                {item.label}
              </span>
            </NavLink>
          )
        })}
      </div>
    </nav>
  )
}
