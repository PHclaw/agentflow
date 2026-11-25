/* ============================================================
   vanilla.ts — 原生生命周期入口（无框架）
   返回 destroy()，可同页创建多实例互不干扰。
   ============================================================ */
import { createPixelToggleEngine } from './PixelToggleEngine.js';
import type { PixelToggleEngine, PixelToggleOptions } from './PixelToggleEngine.js';
import { createMotionRuntime } from './motion-runtime';
import type { MotionRuntime } from './motion-runtime';

export interface VanillaPixelToggle {
  engine: PixelToggleEngine;
  getChecked(): boolean;
  setChecked(checked: boolean, fromUser?: boolean): void;
  destroy(): void;
}

export function mountPixelToggle(
  host: HTMLElement,
  options: PixelToggleOptions = {}
): VanillaPixelToggle {
  const engine = createPixelToggleEngine(host, options);
  const runtime = createMotionRuntime(engine, { reducedMotion: options.reducedMotion });
  runtime.start();

  return {
    engine,
    getChecked: () => engine.getChecked(),
    setChecked: (checked, fromUser = false) => engine.setChecked(checked, fromUser),
    destroy() {
      runtime.destroy();
      host.replaceChildren();
    }
  };
}

export default mountPixelToggle;
