/* ============================================================
   motion-runtime.ts — 实例生命周期与帧调度
   静止后停止 RAF；页面隐藏时停止并落位；销毁时清理全部监听。
   ============================================================ */

export interface EngineLike {
  tick(dt: number): void;
  isSettled(): boolean;
  settle(): void;
  setInvalidate(fn: (() => void) | null): void;
  destroy(): void;
}

export interface MotionRuntimeOptions {
  reducedMotion?: boolean;
}

export interface MotionRuntime {
  requestFrame(): void;
  start(): void;
  stop(): void;
  destroy(): void;
  readonly running: boolean;
}

/**
 * 创建一个帧调度器。引擎通过 setInvalidate 注入的回调唤醒调度器。
 */
export function createMotionRuntime(
  engine: EngineLike,
  options: MotionRuntimeOptions = {}
): MotionRuntime {
  let handle = 0;
  let running = false;
  let last = 0;
  let destroyed = false;
  const reduced = !!options.reducedMotion;

  function frame(now: number) {
    handle = 0;
    if (!running || destroyed) return;
    const dt = last ? Math.min((now - last) / 1000, 0.033) : 0.016;
    last = now;

    if (reduced) {
      engine.settle();
      running = false;
      return;
    }

    engine.tick(dt);
    if (engine.isSettled()) {
      running = false;
      last = 0;
      return;
    }
    handle = requestAnimationFrame(frame);
  }

  function requestFrame() {
    if (destroyed) return;
    if (!running) {
      running = true;
      last = 0;
    }
    if (!handle) handle = requestAnimationFrame(frame);
  }

  function start() {
    requestFrame();
  }

  function stop() {
    running = false;
    last = 0;
    if (handle) { cancelAnimationFrame(handle); handle = 0; }
  }

  function onVisibility() {
    if (typeof document === 'undefined') return;
    if (document.hidden) {
      stop();
      engine.settle();
    } else {
      requestFrame();
    }
  }

  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', onVisibility);
  }

  engine.setInvalidate(requestFrame);

  return {
    requestFrame,
    start,
    stop,
    destroy() {
      if (destroyed) return;
      destroyed = true;
      stop();
      if (typeof document !== 'undefined') {
        document.removeEventListener('visibilitychange', onVisibility);
      }
      engine.setInvalidate(null);
      engine.destroy();
    },
    get running() { return running; }
  };
}

export default createMotionRuntime;
