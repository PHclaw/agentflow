/* ============================================================
   PixelToggleEngine.d.ts — 框架无关核心的类型声明
   ============================================================ */

export interface PixelToggleOptions {
  /** 指定日间状态（true 为日间），默认 false */
  checked?: boolean;
  /** 仅报告用户导致的状态变化 */
  onCheckedChange?: (checked: boolean) => void;
  /** 真实点击时播放轻响，默认 true */
  sound?: boolean;
  /** 场景高度（逻辑像素），默认 540 */
  height?: number;
  /** 覆盖系统减弱动态偏好 */
  reducedMotion?: boolean;
  /** 引擎请求新一帧时回调，由 motion-runtime 注入 */
  onInvalidate?: (() => void) | null;
}

export interface PixelToggleEngine {
  readonly element: HTMLDivElement;
  readonly button: HTMLButtonElement;
  readonly sceneHeight: number;
  tick(dt: number): void;
  render(): void;
  isSettled(): boolean;
  settle(): void;
  resize(): void;
  getChecked(): boolean;
  setChecked(checked: boolean, fromUser?: boolean): void;
  setHeight(height: number): void;
  setReducedMotion(reduced: boolean): void;
  setSound(enabled: boolean): void;
  setInvalidate(fn: (() => void) | null): void;
  destroy(): void;
}

export declare const SCENE_W: number;
export declare const SCENE_H: number;

export declare function createPixelToggleEngine(
  host: HTMLElement,
  options?: PixelToggleOptions
): PixelToggleEngine;

export default createPixelToggleEngine;
