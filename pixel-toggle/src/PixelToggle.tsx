/* ============================================================
   PixelToggle.tsx — React 入口（重点交付）
   DOM 仅在挂载后访问；卸载时停止动画、计时器、监听与 DOM。
   ============================================================ */
import React, { useEffect, useRef } from 'react';
import { createPixelToggleEngine } from './PixelToggleEngine.js';
import type { PixelToggleEngine } from './PixelToggleEngine.js';
import { createMotionRuntime } from './motion-runtime';
import type { MotionRuntime } from './motion-runtime';

export interface PixelToggleProps {
  /** 指定日间状态，默认 false */
  checked?: boolean;
  /** 仅由用户操作触发的状态变化 */
  onCheckedChange?: (checked: boolean) => void;
  /** 真实点击轻响，默认 true */
  sound?: boolean;
  /** 场景高度，默认 540 */
  height?: number;
  /** 覆盖系统减弱动态偏好 */
  reducedMotion?: boolean;
  className?: string;
  style?: React.CSSProperties;
}

export function PixelToggle({
  checked,
  onCheckedChange,
  sound = true,
  height = 540,
  reducedMotion,
  className,
  style
}: PixelToggleProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<PixelToggleEngine | null>(null);
  const runtimeRef = useRef<MotionRuntime | null>(null);
  const onChangeRef = useRef(onCheckedChange);
  const controlledRef = useRef(checked);

  onChangeRef.current = onCheckedChange;
  controlledRef.current = checked;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;

    const engine = createPixelToggleEngine(host, {
      checked: !!checked,
      sound,
      height,
      reducedMotion,
      onCheckedChange: (next) => onChangeRef.current?.(next)
    });
    const runtime = createMotionRuntime(engine, { reducedMotion });
    engineRef.current = engine;
    runtimeRef.current = runtime;
    runtime.start();

    return () => {
      runtime.destroy();
      engineRef.current = null;
      runtimeRef.current = null;
      host.replaceChildren();
    };
    // 挂载后只建立一次实例；后续属性通过独立 effect 同步
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { engineRef.current?.setSound(sound); }, [sound]);
  useEffect(() => { engineRef.current?.setHeight(height); }, [height]);
  useEffect(() => {
    if (reducedMotion !== undefined) engineRef.current?.setReducedMotion(reducedMotion);
  }, [reducedMotion]);
  useEffect(() => {
    if (controlledRef.current !== undefined && engineRef.current) {
      if (engineRef.current.getChecked() !== controlledRef.current) {
        engineRef.current.setChecked(controlledRef.current, false);
      }
    }
  }, [checked]);

  return (
    <div
      ref={hostRef}
      className={className}
      style={{ display: 'inline-block', maxWidth: '100%', ...style }}
    />
  );
}

export default PixelToggle;
