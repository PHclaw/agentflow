<!-- ============================================================
     PixelToggleSvelte.svelte — Svelte 生命周期入口
     共享同一框架无关核心，销毁时清理全部任务
     ============================================================ -->
<script lang="ts">
  import { onMount, onDestroy, createEventDispatcher } from 'svelte';
  import { createPixelToggleEngine } from './PixelToggleEngine.js';
  import type { PixelToggleEngine } from './PixelToggleEngine.js';
  import { createMotionRuntime } from './motion-runtime';
  import type { MotionRuntime } from './motion-runtime';

  export let checked = false;
  export let sound = true;
  export let height = 540;
  export let reducedMotion: boolean | undefined = undefined;

  const dispatch = createEventDispatcher<{ checkedChange: boolean }>();
  let host: HTMLDivElement;
  let engine: PixelToggleEngine | null = null;
  let runtime: MotionRuntime | null = null;

  onMount(() => {
    engine = createPixelToggleEngine(host, {
      checked,
      sound,
      height,
      reducedMotion,
      onCheckedChange: (v) => {
        checked = v;
        dispatch('checkedChange', v);
      }
    });
    runtime = createMotionRuntime(engine, { reducedMotion });
    runtime.start();
  });

  $: if (engine && engine.getChecked() !== checked) engine.setChecked(checked, false);
  $: engine?.setSound(sound);
  $: if (height) engine?.setHeight(height);
  $: if (reducedMotion !== undefined) engine?.setReducedMotion(reducedMotion);

  onDestroy(() => {
    runtime?.destroy();
    runtime = null;
    engine = null;
  });
</script>

<div bind:this={host} class="pt-svelte-host"></div>

<style>
  .pt-svelte-host { display: inline-block; max-width: 100%; }
</style>
