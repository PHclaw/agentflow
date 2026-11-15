/** @type {import('tailwindcss').Config} */

// ---------------------------------------------------------------------------
// AgentFlow 设计系统
//
// 风格取向：ChatGPT / DeepSeek Harness 式的极简 —— 中性灰为底、单一强调色、
// 细描边代替重阴影、小圆角、克制的留白。
//
// 关键手法：把 slate 重映射为真正的「中性灰」（不带蓝调），并让 indigo /
// purple / violet 全部指向同一个强调色。这样即便某个文件里残留着
// `from-indigo-500 to-purple-600` 这类写法，渲染出来也是同一色的平涂，
// 不会再出现彩虹渐变。
// ---------------------------------------------------------------------------

/** 中性灰：ChatGPT 界面的骨架色，刻意不带蓝调 */
const neutral = {
  50: '#fafafa',
  100: '#f5f5f5',
  200: '#e8e8e8',
  300: '#d4d4d4',
  400: '#a3a3a3',
  500: '#737373',
  600: '#525252',
  700: '#404040',
  800: '#262626',
  900: '#171717',
  950: '#0d0d0d',
}

/** 强调色：全站唯一的彩色，只用于选中态 / 链接 / 焦点环 */
/**
 * 「智能体节点」内部四步的时序。一轮 6 秒，和首屏那三个节点的高亮环同周期：
 *
 *   2.1s 规划思考 → 2.6s 技能调用 → 3.1s 工具调用 → 3.5s 生成答案或文件
 *
 * 前后都落在智能体节点自己"亮着"的那两秒里（第 2～4 秒），
 * 所以看到的是：节点一亮，它的内部就在这四步之间走一遍。
 *
 * 为什么是四条 keyframes，而不是「一条 keyframes + 四个延迟」
 * ----------------------------------------------------------
 * 这四步是**累积**的：第 2 步亮起时，第 1 步不能灭。
 * 而周期性动画里，延迟不同的两个元素复位的时间点也不同（延迟 d 的那条
 * 在 d + 6s 处回到起点），于是会看到四行在不同时刻各自闪一下。
 * 把时序直接写进 keyframes、四条都用同一个延迟（0），四行才会在同一刻
 * 一起复位。代价是多三条 keyframes，换来的是"一眼看得出走到哪一步"。
 *
 * 最后 5%（5.7s 之后）一起淡回未激活的样子：硬切回起点会像掉帧。
 *
 * @param at 这一步开始变亮的时刻，写成一轮的百分比
 */
const agentStep = (at) => ({
  // 未激活的亮度压到 0.4：白字压在靛蓝上，0.55 和 1 的差别小到看不出来，
  // "当前走到第几步"这层信息就丢了。0.4 足够暗，又还能读清字。
  [`0%, ${at - 1}%`]: { opacity: '0.4', transform: 'translateX(0)' },
  [`${at + 1}%`]: { opacity: '1', transform: 'translateX(2px)' },
  '95%': { opacity: '1', transform: 'translateX(2px)' },
  '100%': { opacity: '0.4', transform: 'translateX(0)' },
})

const accentScale = {
  DEFAULT: '#4f46e5',
  50: '#eef2ff',
  100: '#e0e7ff',
  200: '#c7d2fe',
  300: '#a5b4fc',
  400: '#818cf8',
  500: '#6366f1',
  600: '#4f46e5',
  700: '#4338ca',
  800: '#3730a3',
  900: '#312e81',
  950: '#1e1b4b',
}

export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        // slate 全量替换为中性灰：一处改动即让全站底色脱离蓝调
        slate: neutral,
        // 四个「彩色」家族收敛到同一强调色，消除彩虹渐变。
        // indigo/purple/violet 是历史写法，primary 是早期主色名。
        indigo: accentScale,
        purple: accentScale,
        violet: accentScale,
        primary: accentScale,
        // brand / accent 是本项目自己的主色与点缀色名，代码里有 168 处
        // brand-*、74 处 brand→accent 渐变。它们同样指向强调色：
        // 类名一行不改，渐变就自动收敛成同色平涂。
        //
        // 换回别的品牌色时也只改这一个常量 —— 全站跟着变。
        brand: accentScale,
        accent: accentScale,
        // 语义化别名，新代码优先使用
        surface: {
          DEFAULT: '#ffffff',
          subtle: '#fafafa',
          muted: '#f5f5f5',
          border: '#e8e8e8',
        },
      },

      borderRadius: {
        // 整体收紧：原 12/16/24px 偏「气泡感」，10/12/16px 更接近专业工具
        lg: '0.5rem',
        xl: '0.625rem',
        '2xl': '0.75rem',
        '3xl': '1rem',
      },

      boxShadow: {
        // 只用极淡的黑色阴影表达层级，杜绝彩色光晕
        'xs': '0 1px 2px 0 rgb(0 0 0 / 0.04)',
        'soft': '0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 3px 0 rgb(0 0 0 / 0.03)',
        'medium': '0 2px 4px -1px rgb(0 0 0 / 0.05), 0 4px 12px -2px rgb(0 0 0 / 0.05)',
        'large': '0 4px 8px -2px rgb(0 0 0 / 0.06), 0 12px 32px -8px rgb(0 0 0 / 0.08)',
        'popover': '0 4px 16px -4px rgb(0 0 0 / 0.10), 0 1px 3px 0 rgb(0 0 0 / 0.05)',
      },

      fontFamily: {
        // 中文回退必须留着：Windows 上没有 PingFang/Hiragino，
        // 漏了 Microsoft YaHei 会退到系统默认宋体，观感明显发虚。
        sans: [
          '-apple-system', 'BlinkMacSystemFont', 'Segoe UI Variable Text',
          'Segoe UI', 'Roboto', 'Helvetica Neue', 'PingFang SC',
          'Hiragino Sans GB', 'Microsoft YaHei', 'Arial', 'sans-serif',
        ],
        mono: ['SF Mono', 'Cascadia Code', 'Consolas', 'Monaco', 'Fira Code', 'monospace'],
      },

      fontSize: {
        '2xs': ['0.6875rem', { lineHeight: '1rem' }],
      },

      letterSpacing: {
        tightest: '-0.02em',
      },

      keyframes: {
        fadeIn: {
          from: { opacity: '0' },
          to: { opacity: '1' },
        },
        slideUp: {
          from: { opacity: '0', transform: 'translateY(6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          from: { opacity: '0', transform: 'translateY(-6px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        scaleIn: {
          from: { opacity: '0', transform: 'scale(0.97)' },
          to: { opacity: '1', transform: 'scale(1)' },
        },
        shimmer: {
          '100%': { transform: 'translateX(100%)' },
        },
        /*
         * 落地页 Hero 里「工作流正在跑」的那两个动作。
         *
         * 两条都是 6 秒一轮，各自只在开头 15%~20% 的时间里可见，剩下的时间
         * 一直不透明度为 0 —— 于是只要给不同元素不同的 animation-delay（用
         * 负值把相位往前推），一条 keyframes 就能演出「依次点亮」的时序：
         *
         *   节点1 亮(0s) → 光点1 落下(1.4s) → 节点2 亮(2s)
         *                → 光点2 落下(3.4s) → 节点3 亮(4s) → 静置
         *
         * 只动 opacity 和 transform：走合成层，不在主线程重排，也不妨碍
         * 页面里其它东西（首屏还同时在拉模板和定价数据）。
         */
        flowNode: {
          '0%': { opacity: '0', transform: 'scale(0.97)' },
          '3%': { opacity: '1', transform: 'scale(1)' },
          '9%': { opacity: '0.85', transform: 'scale(1)' },
          '15%': { opacity: '0', transform: 'scale(1.03)' },
          '100%': { opacity: '0', transform: 'scale(1.03)' },
        },
        flowDot: {
          '0%': { opacity: '0', transform: 'translateY(0)' },
          '4%': { opacity: '1', transform: 'translateY(4px)' },
          '16%': { opacity: '1', transform: 'translateY(32px)' },
          '20%': { opacity: '0', transform: 'translateY(38px)' },
          '100%': { opacity: '0', transform: 'translateY(0)' },
        },
        /* 智能体节点内部的四步，时序见文件开头的 agentStep() */
        flowStep1: agentStep(35),
        flowStep2: agentStep(43),
        flowStep3: agentStep(51),
        flowStep4: agentStep(59),
        /*
         * 进场。落地页首屏的分层出现用它，配 `both` 填充 + 递增的 delay，
         * 就有了「从上往下依次落位」的节奏。
         *
         * 位移只给 14px：首屏离视口顶部很近，幅度一大就会在页面还没稳下来时
         * 先晃一下，反而显得不干净。
         */
        rise: {
          '0%': { opacity: '0', transform: 'translateY(14px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        /*
         * 背景氛围：几团模糊光斑极慢地漂移。
         *
         * **只动 transform，不动 filter / background**。blur-3xl 的元素一旦重绘
         * 就是几百万像素的模糊运算，而 transform 会先把它栅格化一次、之后交给
         * 合成层平移缩放，代价差两个数量级。周期也刻意拉长（22s / 32s）：
         * 氛围动画应该"几乎感觉不到在动"。
         */
        drift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0) scale(1)' },
          '50%': { transform: 'translate3d(3%, -4%, 0) scale(1.08)' },
        },
        /*
         * 慢速呼吸。Tailwind 自带的 animate-pulse 是 2 秒一轮的 1↔0.5，
         * 放在大块模糊光斑上更像"在闪"；这里把周期拉到 24 秒。
         *
         * 另外它**只动 opacity**：几处区块光斑是靠 -translate-x/y-1/2 居中的，
         * keyframes 里一旦出现 transform，居中就会被整个盖掉、光斑跳位。
         * 纯 opacity 既绕开这个坑，又正好是合成层最擅长的事。
         */
        breathe: {
          '0%, 100%': { opacity: '0.55' },
          '50%': { opacity: '1' },
        },
      },

      animation: {
        'fade-in': 'fadeIn 0.15s ease-out',
        'slide-up': 'slideUp 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        'slide-down': 'slideDown 0.2s cubic-bezier(0.16, 1, 0.3, 1)',
        'scale-in': 'scaleIn 0.15s cubic-bezier(0.16, 1, 0.3, 1)',
        'flow-node': 'flowNode 6s ease-in-out infinite',
        'flow-dot': 'flowDot 6s ease-in-out infinite',
        'flow-step-1': 'flowStep1 6s ease-in-out infinite',
        'flow-step-2': 'flowStep2 6s ease-in-out infinite',
        'flow-step-3': 'flowStep3 6s ease-in-out infinite',
        'flow-step-4': 'flowStep4 6s ease-in-out infinite',
        rise: 'rise 0.65s cubic-bezier(0.16, 1, 0.3, 1) both',
        drift: 'drift 22s ease-in-out infinite',
        'drift-slow': 'drift 32s ease-in-out infinite',
        breathe: 'breathe 24s ease-in-out infinite',
      },
    },
  },
  plugins: [],
}
