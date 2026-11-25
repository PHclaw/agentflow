<!-- ============================================================
     PixelToggle.vue — Vue 3 生命周期入口，共享同一框架无关核心
     ============================================================ -->
<template>
  <div ref="host" :class="$attrs.class" :style="$attrs.style" class="pt-vue-host"></div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch } from 'vue';
import { createPixelToggleEngine } from './PixelToggleEngine.js';
import type { PixelToggleEngine } from './PixelToggleEngine.js';
import { createMotionRuntime } from './motion-runtime';
import type { MotionRuntime } from './motion-runtime';

const props = withDefaults(defineProps<{
  checked?: boolean;
  sound?: boolean;
  height?: number;
  reducedMotion?: boolean;
}>(), {
  checked: false,
  sound: true,
  height: 540,
  reducedMotion: undefined
});

const emit = defineEmits<{ (e: 'checkedChange', value: boolean): void }>();

const host = ref<HTMLDivElement | null>(null);
let engine: PixelToggleEngine | null = null;
let runtime: MotionRuntime | null = null;

onMounted(() => {
  if (!host.value) return;
  engine = createPixelToggleEngine(host.value, {
    checked: props.checked,
    sound: props.sound,
    height: props.height,
    reducedMotion: props.reducedMotion,
    onCheckedChange: (v) => emit('checkedChange', v)
  });
  runtime = createMotionRuntime(engine, { reducedMotion: props.reducedMotion });
  runtime.start();
});

watch(() => props.checked, (v) => {
  if (engine && engine.getChecked() !== v) engine.setChecked(v, false);
});
watch(() => props.sound, (v) => engine?.setSound(v));
watch(() => props.height, (v) => engine?.setHeight(v));
watch(() => props.reducedMotion, (v) => { if (v !== undefined) engine?.setReducedMotion(v); });

onBeforeUnmount(() => {
  runtime?.destroy();
  runtime = null;
  engine = null;
  if (host.value) host.value.replaceChildren();
});
</script>

<style scoped>
.pt-vue-host { display: inline-block; max-width: 100%; }
</style>
