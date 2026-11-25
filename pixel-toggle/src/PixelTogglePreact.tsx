/* ============================================================
   PixelTogglePreact.tsx — Preact 生命周期入口
   ============================================================ */
import { h } from 'preact';
import { useEffect, useRef } from 'preact/hooks';
import type { JSX } from 'preact';
import { createPixelToggleEngine } from './PixelToggleEngine.js';
import type { PixelToggleEngine } from './PixelToggleEngine.js';
import { createMotionRuntime } from './motion-runtime';
import type { MotionRuntime } from './motion-runtime';

export interface PixelTogglePreactProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  sound?: boolean;
  height?: number;
  reducedMotion?: boolean;
  class?: string;
  style?: JSX.CSSProperties;
}

export function PixelTogglePreact(props: PixelTogglePreactProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const engineRef = useRef<PixelToggleEngine | null>(null);
  const runtimeRef = useRef<MotionRuntime | null>(null);
  const onChangeRef = useRef(props.onCheckedChange);
  onChangeRef.current = props.onCheckedChange;

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return undefined;
    const engine = createPixelToggleEngine(host, {
      checked: !!props.checked,
      sound: props.sound !== false,
      height: props.height ?? 540,
      reducedMotion: props.reducedMotion,
      onCheckedChange: (v) => onChangeRef.current?.(v)
    });
    const runtime = createMotionRuntime(engine, { reducedMotion: props.reducedMotion });
    engineRef.current = engine;
    runtimeRef.current = runtime;
    runtime.start();
    return () => {
      runtime.destroy();
      engineRef.current = null;
      runtimeRef.current = null;
      host.replaceChildren();
    };
  }, []);

  useEffect(() => {
    if (props.checked !== undefined && engineRef.current?.getChecked() !== props.checked) {
      engineRef.current?.setChecked(props.checked, false);
    }
  }, [props.checked]);

  return <div ref={hostRef} class={props.class} style={props.style} />;
}

export default PixelTogglePreact;
