/* ============================================================
   PixelToggleSolid.tsx — Solid 生命周期入口
   ============================================================ */
import { onMount, onCleanup, createSignal } from 'solid-js';
import type { JSX } from 'solid-js';
import { createPixelToggleEngine } from './PixelToggleEngine.js';
import type { PixelToggleEngine } from './PixelToggleEngine.js';
import { createMotionRuntime } from './motion-runtime';
import type { MotionRuntime } from './motion-runtime';

export interface PixelToggleSolidProps {
  checked?: boolean;
  onCheckedChange?: (checked: boolean) => void;
  sound?: boolean;
  height?: number;
  reducedMotion?: boolean;
  class?: string;
  style?: JSX.CSSProperties;
}

export function PixelToggleSolid(props: PixelToggleSolidProps) {
  let host!: HTMLDivElement;
  let engine: PixelToggleEngine | null = null;
  let runtime: MotionRuntime | null = null;
  const [, force] = createSignal(0);

  onMount(() => {
    engine = createPixelToggleEngine(host, {
      checked: !!props.checked,
      sound: props.sound !== false,
      height: props.height ?? 540,
      reducedMotion: props.reducedMotion,
      onCheckedChange: (v) => props.onCheckedChange?.(v)
    });
    runtime = createMotionRuntime(engine, { reducedMotion: props.reducedMotion });
    runtime.start();
  });

  onCleanup(() => {
    runtime?.destroy();
    runtime = null;
    engine = null;
  });

  return <div ref={host} class={props.class} style={props.style} />;
}

export default PixelToggleSolid;
