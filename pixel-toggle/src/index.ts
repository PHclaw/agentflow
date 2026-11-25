/* ============================================================
   index.ts — 统一导出
   ============================================================ */
export { PixelToggle } from './PixelToggle';
export type { PixelToggleProps } from './PixelToggle';
export { mountPixelToggle } from './vanilla';
export type { VanillaPixelToggle } from './vanilla';
export { createMotionRuntime } from './motion-runtime';
export type { MotionRuntime, MotionRuntimeOptions } from './motion-runtime';
export { createPixelToggleEngine, SCENE_W, SCENE_H } from './PixelToggleEngine.js';
export type { PixelToggleEngine, PixelToggleOptions } from './PixelToggleEngine.js';
