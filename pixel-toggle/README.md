# PixelToggle — 像素日夜开关

可拖动的圆角磨砂玻璃滑块切换日夜：夜间暖白像素月亮 + 钴蓝边光，日间深灰像素太阳 + 琥珀边光；像素在切换中四散重组，细光带沿玻璃外沿绕行。全部图形由 CSS / 内嵌 SVG / Canvas 绘制，不加载远程图片、字体、视频或素材。

## 安装与运行

依赖安装：

```bash
npm install react react-dom
npm install
```

本地运行：

```bash
npm run dev
```

打开 `http://localhost:5173`。生产构建：`npm run build`，预览：`npm run preview`。

> 适配器文件 `PixelToggle.vue` / `PixelToggleSvelte.svelte` / `PixelToggleSolid.tsx` / `PixelTogglePreact.tsx` 需各自安装对应框架（vue / svelte / solid-js / preact），它们与 React 入口共享同一个框架无关核心 `PixelToggleEngine.js`。

## 生成完成后的使用示例

```tsx
import { PixelToggle } from "./PixelToggle";

export default function App() {
  return <PixelToggle />;
}
```

## 文件

| 文件 | 作用 |
| --- | --- |
| `src/PixelToggleEngine.js` | 框架无关核心：原生按钮 DOM、WebGL2 单层绘制、Canvas 2D 回退、像素格点、粒子、弹簧物理、指针/键盘、音频 |
| `src/PixelToggleEngine.d.ts` | 核心的类型声明 |
| `src/motion-runtime.ts` | 实例生命周期：静止停帧、页面隐藏落位、销毁清理 |
| `src/PixelToggle.tsx` | React 入口（重点交付） |
| `src/PixelToggle.vue` | Vue 3 入口 |
| `src/PixelToggleSvelte.svelte` | Svelte 入口 |
| `src/PixelToggleSolid.tsx` | Solid 入口 |
| `src/PixelTogglePreact.tsx` | Preact 入口 |
| `src/vanilla.ts` | 原生生命周期入口 |
| `src/index.ts` | 统一导出 |

## API

```ts
interface PixelToggleProps {
  checked?: boolean;                       // 日间状态，默认 false
  onCheckedChange?: (v: boolean) => void;  // 仅用户导致的变化
  sound?: boolean;                         // 真实点击轻响，默认 true
  height?: number;                         // 场景高度，默认 540
  reducedMotion?: boolean;                 // 覆盖系统偏好
  className?: string;
  style?: CSSProperties;
}
```

原生入口：

```ts
import { mountPixelToggle } from './vanilla';
const instance = mountPixelToggle(document.getElementById('host')!, { checked: false });
instance.destroy();
```

## 实现要点

- 场景逻辑 720×540，开关 520×272 / 圆角 86，以 0.83 比例显示；窄屏按父容器宽度等比缩放，无横向溢出。
- WebGL2 以圆角矩形 SDF 在同一层绘制背景、轨道、玻璃与光晕；像素遮罩写入 256×256 纹理，按内侧距边缘坡度做折射、RGB 错位采样与四向磨砂，叠固定 2% 细粒。上下文丢失或不可用时自动切换 Canvas 2D 回退。
- 月亮 17×17 网格按双圆条件生成并带偶数 ghost 格与十字星；太阳为实心圆 + 八向射线；格距 6.85px 方形像素。
- 粒子复用 `max(月亮格数,太阳格数)+20` 个实例，主题跨 0.5 重分配目标，弹回刚度 340 / 阻尼 27，鼠标 160ms 内 49px 径向排斥。
- 位置弹簧 224/15.5（4 子步），形变弹簧 420/24，按压收缩 5.5%，光带 900ms ease-out cubic；拖动按位移与甩动速度落位。
- 原生 `button[role=switch]` + `aria-checked` + 可见焦点轮廓，Space/Enter 可切换，`touch-action:pan-y` 保留纵向滚动，拖动结束不重复触发点击。
- 静止后停止 RAF；页面隐藏停止并落位；卸载清理指针、计时器、音频和 DOM。同页多实例互不干扰。

## 验收覆盖

鼠标拖动越过中点、反向连点、触屏、键盘、回调、日夜静止帧、粒子聚散、尺寸变化与卸载清理均已在实现中处理；375 / 768 / 1440px 通过等比缩放避免横向溢出。
