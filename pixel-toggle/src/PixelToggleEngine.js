/* ============================================================
   PixelToggleEngine.js — 框架无关的「像素日夜开关」核心
   原生按钮 + WebGL2 单层绘制 + Canvas 2D 回退 + 弹簧物理
   无远程资源，无第三方依赖。
   ============================================================ */

export const SCENE_W = 720;
export const SCENE_H = 540;
const TRACK_W = 520;
const TRACK_H = 272;
const TRACK_R = 86;
const SHOW_SCALE = 0.83;
const THUMB = 240;
const THUMB_R = 69;
const WALL = 16;
const TRAVEL = 248;
const GRID = 6.85;
const TEX = 256;
const TEX_SCALE = TEX / THUMB;
const PIXEL_BUDGET = 1200000;

const clamp = (v, a, b) => (v < a ? a : v > b ? b : v);
const lerp = (a, b, t) => a + (b - a) * t;
const smoothstep = (t) => { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); };
const easeOutCubic = (t) => 1 - Math.pow(1 - clamp(t, 0, 1), 3);
const logistic = (v) => 1 / (1 + Math.exp(-v));

/* ---------- 像素格点：月亮 ---------- */
function buildMoonCells() {
  const cells = [];
  for (let y = -8; y <= 8; y++) {
    for (let x = -8; x <= 8; x++) {
      if (Math.hypot(x, y) <= 6.6) {
        const outside = Math.hypot(x - 3.3, y + 2.4) > 5.4;
        if (outside) cells.push({ x, y, o: 1 });
        else if ((x + y) % 2 === 0) cells.push({ x, y, o: 0.15 });
      }
    }
  }
  cells.push({ x: 7, y: -7, o: 1 });
  [[6, -7], [8, -7], [7, -8], [7, -6]].forEach(([x, y]) => cells.push({ x, y, o: 0.45 }));
  return cells;
}

/* ---------- 像素格点：太阳 ---------- */
function buildSunCells() {
  const cells = [];
  const seen = new Set();
  const add = (x, y) => {
    const k = x + ',' + y;
    if (!seen.has(k)) { seen.add(k); cells.push({ x, y, o: 1 }); }
  };
  for (let y = -8; y <= 8; y++) {
    for (let x = -8; x <= 8; x++) {
      if (Math.hypot(x, y) <= 3.7) add(x, y);
    }
  }
  for (let i = 0; i < 8; i++) {
    const a = (i * Math.PI) / 4;
    const rs = i % 2 === 0 ? [5.6, 6.6, 7.6] : [5.9, 7.2];
    rs.forEach((r) => add(Math.round(Math.cos(a) * r), Math.round(Math.sin(a) * r)));
  }
  return cells;
}

const MOON_CELLS = buildMoonCells();
const SUN_CELLS = buildSunCells();
const PARTICLE_COUNT = Math.max(MOON_CELLS.length, SUN_CELLS.length) + 20;

/* ---------- WebGL2 着色器 ---------- */
const VERT = `#version 300 es
in vec2 aPos;
void main(){ gl_Position = vec4(aPos, 0.0, 1.0); }`;

const FRAG = `#version 300 es
precision highp float;
uniform vec2 uRes;
uniform vec2 uScene;
uniform float uTheme;
uniform float uThumbX;
uniform float uPress;
uniform float uSx;
uniform float uSy;
uniform float uPhase;
uniform sampler2D uMask;
out vec4 outC;

float hash(vec2 p){ return fract(sin(dot(p, vec2(127.1,311.7))) * 43758.5453123); }

float sdRoundBox(vec2 p, vec2 b, float r){
  vec2 q = abs(p) - b + r;
  return min(max(q.x,q.y),0.0) + length(max(q,0.0)) - r;
}

vec2 boxNormal(vec2 p, vec2 b, float r){
  vec2 e = vec2(1.0, 0.0);
  float dx = sdRoundBox(p+e.xy,b,r) - sdRoundBox(p-e.xy,b,r);
  float dy = sdRoundBox(p+e.yx,b,r) - sdRoundBox(p-e.yx,b,r);
  vec2 g = vec2(dx,dy);
  return length(g) < 0.0001 ? vec2(0.0,-1.0) : normalize(g);
}

void main(){
  vec2 p = vec2(gl_FragCoord.x / uRes.x * uScene.x,
                uScene.y - gl_FragCoord.y / uRes.y * uScene.y);

  /* 场景底：140%×155% 椭圆渐变，中心 92% / -8% */
  vec2 ec = vec2(uScene.x*0.92, -uScene.y*0.08);
  vec2 er = vec2(uScene.x*0.70, uScene.y*0.775);
  float eg = clamp(length((p-ec)/er), 0.0, 1.0);
  vec3 nightBg = mix(vec3(0.1294,0.1294,0.1373), vec3(0.0510,0.0510,0.0549), smoothstep(eg));
  vec3 dayBg   = mix(vec3(0.9255,0.9255,0.9176), vec3(0.8039,0.8039,0.8000), smoothstep(eg));
  vec3 col = mix(nightBg, dayBg, uTheme);

  /* 轨道：520×272 圆角矩形，0.83 显示比例，向下 17px 柔投影 */
  vec2 center = vec2(uScene.x*0.5, uScene.y*0.5);
  vec2 tHalf = vec2(520.0*0.83*0.5, 272.0*0.83*0.5);
  float tRad = 86.0*0.83;
  float shadow = 1.0 - smoothstep(0.0, 34.0, sdRoundBox(p - center - vec2(0.0,17.0), tHalf, tRad));
  col *= 1.0 - shadow * 0.30;

  float dTrack = sdRoundBox(p - center, tHalf, tRad);
  float trackMask = 1.0 - smoothstep(-0.8, 0.8, dTrack);
  vec3 trackNight = vec3(0.028 + 0.02*smoothstep((center.y-p.y)/tHalf.y));
  vec3 trackDay   = mix(vec3(0.925), vec3(0.885), smoothstep((center.y-p.y)/tHalf.y));
  vec3 trackCol = mix(trackNight, trackDay, uTheme);
  col = mix(col, trackCol, trackMask);
  /* 轨道 1px 边：上暗下亮 */
  vec2 tn = boxNormal(p-center, tHalf, tRad);
  float edge = 1.0 - smoothstep(0.0, 1.4, abs(dTrack));
  float edgeLight = smoothstep(-1.0, 1.0, tn.y);
  vec3 edgeCol = mix(vec3(0.02), vec3(0.98), edgeLight);
  col = mix(col, edgeCol, edge*0.55*trackMask);

  /* 拇指：240×240 圆角矩形，按压收缩，形变拉伸 */
  vec2 tc = vec2(uThumbX, center.y);
  vec2 th = vec2(120.0*0.83*uSx*(1.0-0.055*uPress), 120.0*0.83*uSy*(1.0-0.055*uPress));
  float trad = 69.0*0.83*min(uSx,uSy)*(1.0-0.055*uPress);
  float d = sdRoundBox(p-tc, th, trad);
  vec2 n = boxNormal(p-tc, th, trad);

  /* 拇指外光晕：两段指数衰减 */
  float dOut = max(d, 0.0);
  float halo = 0.43*exp(-dOut/21.0) + 0.33*exp(-dOut/85.0);
  vec3 haloCol = mix(vec3(0.435,0.525,1.0), vec3(1.0,0.659,0.18), uTheme);
  col += haloCol * halo * 0.20;

  /* 光带：中心角 π/2-2π×相位，左右 ±0.92 弧度 */
  float ang = atan(p.y-tc.y, p.x-tc.x);
  float bandCenter = 1.5707963 - 6.2831853*uPhase;
  float da = atan(sin(ang-bandCenter), cos(ang-bandCenter));
  float bandMask = 1.0 - smoothstep(0.72, 0.92, abs(da));
  float bandLine = exp(-pow((dOut-8.0)/7.0, 2.0));
  col += haloCol * bandMask * bandLine * 0.55;
  col += mix(vec3(0.86,0.90,1.0), vec3(1.0,0.93,0.80), uTheme) * bandMask * exp(-pow((dOut-8.0)/2.0,2.0)) * 0.45;

  /* 拇指玻璃体 */
  float thumbMask = 1.0 - smoothstep(-1.0, 1.0, d);
  float gy = clamp((p.y-(tc.y-th.y))/(2.0*th.y), 0.0, 1.0);
  vec3 glassNight = mix(vec3(0.42,0.42,0.44), vec3(0.16,0.16,0.18), gy);
  vec3 glassDay = mix(vec3(0.995,0.995,0.99), vec3(0.93,0.93,0.92), gy);
  vec3 glass = mix(glassNight, glassDay, uTheme);
  /* 左上玻璃高光 */
  float hi = pow(max(dot(n, normalize(vec2(-0.8,-0.6))), 0.0), 2.2);
  glass += hi * mix(0.16, 0.10, uTheme);
  col = mix(col, glass, thumbMask);

  /* 像素遮罩：内侧距边缘 d，外法线 n，坡度pow(1-d/31,2.6) */
  float dIn = max(-d, 0.0);
  float slope = pow(1.0 - clamp(dIn/31.0, 0.0, 1.0), 2.6);
  vec2 rel = (p-tc)/(120.0*0.83);
  float pull = 47.0 * (TEX_SCALE_VALUE) * slope;
  vec2 basePx = rel*128.0 - n*pull;

  vec2 uvR = clamp((basePx + n*0.8)/256.0 + 0.5, 0.001, 0.999);
  vec2 uvG = clamp(basePx/256.0 + 0.5, 0.001, 0.999);
  vec2 uvB = clamp((basePx - n*0.8)/256.0 + 0.5, 0.001, 0.999);
  float mR = texture(uMask, uvR).a;
  float mG = texture(uMask, uvG).a;
  float mB = texture(uMask, uvB).a;
  /* 磨砂：四方向各偏移4px 与清晰遮罩混合 */
  vec2 f = vec2(4.0/256.0, 0.0);
  float fr = (texture(uMask,uvG+f).a+texture(uMask,uvG-f).a+texture(uMask,uvG+vec2(0.0,f.x)).a+texture(uMask,uvG-vec2(0.0,f.x)).a)*0.25;
  float frost = clamp(slope*0.75, 0.0, 0.85);
  mR = mix(mR, fr, frost); mG = mix(mG, fr, frost); mB = mix(mB, fr, frost);
  vec3 pixNight = vec3(0.965,0.973,1.0);
  vec3 pixDay = vec3(0.169,0.180,0.200);
  vec3 pix = vec3(mR*mix(pixNight.r,pixDay.r,uTheme), mG*mix(pixNight.g,pixDay.g,uTheme), mB*mix(pixNight.b,pixDay.b,uTheme));
  float pm = max(max(mR,mG),mB) * thumbMask * 0.96;
  /* 夜间暖白像素加法发光；日间深灰像素直接覆盖，避免白底被加亮 */
  col = mix(mix(col, pix, pm), col + pix * pm, 1.0 - uTheme);

  /* 内晕：28px / 73px 衰减；沿玻璃深度 2.8px 亮边表现折射 */
  float inner = 0.5*exp(-dIn/28.0) + 0.3*exp(-dIn/73.0);
  col += haloCol * inner * 0.10 * thumbMask;
  col += mix(vec3(0.85,0.90,1.0),vec3(1.0,0.94,0.82),uTheme) * exp(-abs(d)/2.8) * 0.30;

  /* 固定 2% 细粒，静止不刷新 */
  col += (hash(floor(p))-0.5)*0.02;

  outC = vec4(clamp(col, 0.0, 1.0), 1.0);
}`.replace('TEX_SCALE_VALUE', String(TEX_SCALE));

/* ---------- 音频：真实点击三角波轻响 ---------- */
function createAudio() {
  let ctx = null;
  return {
    play(day) {
      try {
        const AC = window.AudioContext || window.webkitAudioContext;
        if (!AC) return;
        if (!ctx) ctx = new AC();
        if (ctx.state === 'suspended') ctx.resume();
        const t = ctx.currentTime;
        const osc = ctx.createOscillator();
        const gain = ctx.createGain();
        osc.type = 'triangle';
        osc.frequency.setValueAtTime(day ? 1500 : 900, t);
        osc.frequency.exponentialRampToValueAtTime(day ? 2300 : 480, t + 0.1);
        gain.gain.setValueAtTime(0.0001, t);
        gain.gain.exponentialRampToValueAtTime(0.09, t + 0.012);
        gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.1);
        osc.connect(gain).connect(ctx.destination);
        osc.start(t);
        osc.stop(t + 0.11);
      } catch (e) { /* 音频不可用时静默 */ }
    },
    destroy() { if (ctx) { try { ctx.close(); } catch (e) {} ctx = null; } }
  };
}

/* ---------- 主工厂 ---------- */
export function createPixelToggleEngine(host, options = {}) {
  if (!host) throw new Error('PixelToggleEngine: host element is required');

  const sceneH = Math.max(240, Number(options.height) || SCENE_H);
  const state = {
    checked: !!options.checked,
    theme: options.checked ? 1 : 0,
    themeFrom: options.checked ? 1 : 0,
    themeTo: options.checked ? 1 : 0,
    themeElapsed: 1,
    themeDur: 1,
    pos: options.checked ? 1 : 0,
    posV: 0,
    posTarget: options.checked ? 1 : 0,
    press: 0,
    pressTarget: 0,
    minPress: 0,
    deform: 0,
    deformV: 0,
    wallC: 0,
    phase: options.checked ? 0.5 : 0,
    phaseFrom: options.checked ? 0.5 : 0,
    phaseTo: options.checked ? 0.5 : 0,
    phaseElapsed: 1,
    excite: 0,
    dragging: false,
    dragStartX: 0,
    dragStartPos: 0,
    moved: false,
    suppressClick: false,
    pointer: { x: 0, y: 0, t: -1e9 },
    reduced: !!options.reducedMotion || (typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches),
    sound: options.sound !== false,
    onCheckedChange: typeof options.onCheckedChange === 'function' ? options.onCheckedChange : null,
    onInvalidate: null,
    destroyed: false
  };

  const audio = createAudio();

  /* ---------- DOM ---------- */
  const frame = document.createElement('div');
  frame.className = 'pt-frame';
  Object.assign(frame.style, { position: 'relative', width: '720px', height: sceneH + 'px' });

  const stage = document.createElement('div');
  stage.className = 'pt-stage';
  Object.assign(stage.style, {
    position: 'absolute', left: '0', top: '0',
    width: SCENE_W + 'px', height: sceneH + 'px',
    transformOrigin: 'top left'
  });

  const button = document.createElement('button');
  button.type = 'button';
  button.className = 'pt-hit';
  button.setAttribute('role', 'switch');
  button.setAttribute('aria-checked', state.checked ? 'true' : 'false');
  button.setAttribute('aria-label', '像素日夜开关');
  Object.assign(button.style, {
    position: 'absolute', inset: '0', width: '100%', height: '100%',
    border: '0', padding: '0', margin: '0', background: 'transparent',
    cursor: 'pointer', touchAction: 'pan-y', display: 'block',
    WebkitTapHighlightColor: 'transparent', outline: 'none'
  });

  const focusRing = document.createElement('span');
  focusRing.className = 'pt-focus';
  Object.assign(focusRing.style, {
    position: 'absolute', inset: '0', borderRadius: '30px',
    pointerEvents: 'none', boxShadow: 'none', transition: 'box-shadow .12s'
  });
  button.addEventListener('focus', () => {
    if (button.matches(':focus-visible')) focusRing.style.boxShadow = '0 0 0 3px #6f86ff';
  });
  button.addEventListener('blur', () => { focusRing.style.boxShadow = 'none'; });

  const glCanvas = document.createElement('canvas');
  glCanvas.className = 'pt-gl';
  const c2dCanvas = document.createElement('canvas');
  c2dCanvas.className = 'pt-c2d';
  [glCanvas, c2dCanvas].forEach((c) => Object.assign(c.style, {
    position: 'absolute', inset: '0', width: '100%', height: '100%', display: 'block'
  }));
  c2dCanvas.style.display = 'none';

  button.appendChild(glCanvas);
  button.appendChild(c2dCanvas);
  button.appendChild(focusRing);
  stage.appendChild(button);
  frame.appendChild(stage);
  host.appendChild(frame);

  /* ---------- 像素遮罩画布 ---------- */
  const maskCanvas = document.createElement('canvas');
  maskCanvas.width = TEX;
  maskCanvas.height = TEX;
  const maskCtx = maskCanvas.getContext('2d');


  function makeParticle(i) {
    const a = Math.random() * Math.PI * 2;
    const r = Math.sqrt(Math.random());
    return {
      x: (Math.random() - 0.5) * GRID * 6,
      y: (Math.random() - 0.5) * GRID * 6,
      vx: 0, vy: 0,
      alpha: 0,
      anchorX: Math.cos(a) * 74 * r,
      anchorY: Math.sin(a) * 63 * r,
      seed: Math.random() * 100,
      cell: null,
      targetAlpha: 0
    };
  }
  const particles = Array.from({ length: PARTICLE_COUNT }, (_, i) => makeParticle(i));

  function assignTargets(day) {
    const cells = day ? SUN_CELLS : MOON_CELLS;
    const copy = cells.slice();
    for (let i = copy.length - 1; i > 0; i--) {
      const j = (Math.floor(Math.random() * (i + 1)));
      [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    particles.forEach((p, i) => {
      if (i < copy.length) {
        p.cell = copy[i];
        p.targetAlpha = copy[i].o;
      } else {
        p.cell = null;
        p.targetAlpha = 0;
      }
    });
  }
  assignTargets(!!state.checked);
  particles.forEach((p) => { p.alpha = p.targetAlpha; if (p.cell) { p.x = p.cell.x * GRID; p.y = p.cell.y * GRID; } });

  /* ---------- WebGL2 / Canvas2D ---------- */
  let gl = null;
  let glProgram = null;
  let glTex = null;
  let glLoc = {};
  let use2D = false;
  let c2d = null;

  function compile(type, src) {
    const s = gl.createShader(type);
    gl.shaderSource(s, src);
    gl.compileShader(s);
    if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
      throw new Error(gl.getShaderInfoLog(s) || 'shader error');
    }
    return s;
  }

  function initGL() {
    try {
      gl = glCanvas.getContext('webgl2', { alpha: false, antialias: false, preserveDrawingBuffer: false });
      if (!gl) throw new Error('no webgl2');
      glProgram = gl.createProgram();
      gl.attachShader(glProgram, compile(gl.VERTEX_SHADER, VERT));
      gl.attachShader(glProgram, compile(gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(glProgram);
      if (!gl.getProgramParameter(glProgram, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(glProgram));
      gl.useProgram(glProgram);

      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);
      const aPos = gl.getAttribLocation(glProgram, 'aPos');
      gl.enableVertexAttribArray(aPos);
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

      glTex = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, glTex);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.pixelStorei(gl.UNPACK_FLIP_Y_WEBGL, false);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, TEX, TEX, 0, gl.RGBA, gl.UNSIGNED_BYTE, maskCanvas);
      gl.uniform1i(gl.getUniformLocation(glProgram, 'uMask'), 0);

      ['uRes','uScene','uTheme','uThumbX','uPress','uSx','uSy','uPhase'].forEach((k) => {
        glLoc[k] = gl.getUniformLocation(glProgram, k);
      });
      glCanvas.addEventListener('webglcontextlost', onContextLost, false);
      use2D = false;
    } catch (e) {
      use2D = true;
      gl = null;
    }
  }

  function onContextLost(e) {
    e.preventDefault();
    use2D = true;
    gl = null;
    glCanvas.style.display = 'none';
    c2dCanvas.style.display = 'block';
    resize();
  }

  function resize() {
    const parentW = host.clientWidth || SCENE_W;
    const fit = Math.min(1, parentW / SCENE_W);
    stage.style.transform = 'scale(' + fit + ')';
    frame.style.width = (SCENE_W * fit) + 'px';
    frame.style.height = (sceneH * fit) + 'px';

    let scale = Math.min(window.devicePixelRatio || 1, 2);
    if (SCENE_W * sceneH * scale * scale > PIXEL_BUDGET) {
      scale = Math.sqrt(PIXEL_BUDGET / (SCENE_W * sceneH));
    }
    const w = Math.max(1, Math.round(SCENE_W * scale));
    const h = Math.max(1, Math.round(sceneH * scale));
    [glCanvas, c2dCanvas].forEach((c) => { c.width = w; c.height = h; });
    if (!use2D && gl) gl.viewport(0, 0, w, h);
    requestRender();
  }

  initGL();
  if (use2D) {
    glCanvas.style.display = 'none';
    c2dCanvas.style.display = 'block';
    c2d = c2dCanvas.getContext('2d');
  }
  resize();

  /* ---------- 粒子更新 ---------- */
  let lastThemeForAssign = state.theme;

  function updateParticles(dt, now) {
    const scatter = clamp(Math.max(state.excite, 1 - Math.abs(2 * state.theme - 1) * 1.6), 0, 1);
    const speedMax = 40;
    for (const p of particles) {
      let tx = p.cell ? p.cell.x * GRID : 0;
      let ty = p.cell ? p.cell.y * GRID : 0;
      tx = lerp(tx, p.anchorX, scatter) + Math.sin(now * 0.003 + p.seed) * 6 * scatter;
      ty = lerp(ty, p.anchorY, scatter) + Math.cos(now * 0.0027 + p.seed) * 6 * scatter;
      const ax = (tx - p.x) * 340 - p.vx * 27;
      const ay = (ty - p.y) * 340 - p.vy * 27;
      p.vx += ax * dt;
      p.vy += ay * dt;
      /* 鼠标 160ms 内 49px 半径排斥 */
      if (now - state.pointer.t < 160) {
        const px = state.pointer.x, py = state.pointer.y;
        const dx = p.x - px, dy = p.y - py;
        const dist = Math.hypot(dx, dy);
        if (dist > 0.001 && dist < 49) {
          const f = 2800 * (1 - Math.pow(dist / 49, 2)) * dt / dist;
          p.vx += dx * f;
          p.vy += dy * f;
        }
      }
      p.x += p.vx * dt;
      p.y += p.vy * dt;
      const rate = p.targetAlpha >= p.alpha ? 9 : 12;
      p.alpha += (p.targetAlpha - p.alpha) * (1 - Math.exp(-rate * dt));
    }
    drawMask(speedMax, scatter);
  }

  function drawMask(speedMax, scatter) {
    maskCtx.clearRect(0, 0, TEX, TEX);
    const size = 0.82 * GRID * TEX_SCALE;
    for (const p of particles) {
      if (p.alpha <= 0.002) continue;
      const speed = Math.hypot(p.vx, p.vy);
      const shrink = 1 - 0.35 * clamp(speed / speedMax, 0, 1) - 0.35 * scatter * 0.35;
      const s = Math.max(0.6, size * Math.max(0.35, shrink));
      const cx = TEX / 2 + p.x * TEX_SCALE;
      const cy = TEX / 2 + p.y * TEX_SCALE;
      maskCtx.fillStyle = 'rgba(255,255,255,' + clamp(p.alpha, 0, 1).toFixed(3) + ')';
      maskCtx.fillRect(cx - s / 2, cy - s / 2, s, s);
    }
    if (!use2D && gl) {
      gl.bindTexture(gl.TEXTURE_2D, glTex);
      gl.texSubImage2D(gl.TEXTURE_2D, 0, 0, 0, gl.RGBA, gl.UNSIGNED_BYTE, maskCanvas);
    }
  }

  /* ---------- 物理推进 ---------- */
  function step(dt, now) {
    if (state.destroyed) return;
    dt = Math.min(dt, 0.033);

    if (state.dragging) {
      const targetTheme = logistic((state.pos - 0.5) / 0.07);
      state.theme += (targetTheme - state.theme) * (1 - Math.exp(-14 * dt));
      state.phase += (state.pos * 0.5 - state.phase) * (1 - Math.exp(-18 * dt));
    } else {
      if (state.themeElapsed < state.themeDur) {
        state.themeElapsed += dt * 1000;
        state.theme = lerp(state.themeFrom, state.themeTo, smoothstep(state.themeElapsed / state.themeDur));
      } else {
        state.theme = state.themeTo;
      }
      if (state.phaseElapsed < 900 + 10) {
        state.phaseElapsed += dt * 1000;
        state.phase = lerp(state.phaseFrom, state.phaseTo, easeOutCubic((state.phaseElapsed - 10) / 900));
      }
      const sub = dt / 4;
      for (let i = 0; i < 4; i++) {
        const a = (state.posTarget - state.pos) * 224 - state.posV * 15.5;
        state.posV += a * sub;
        state.pos += state.posV * sub;
      }
    }

    if (state.theme >= 0.5 !== lastThemeForAssign) {
      lastThemeForAssign = state.theme >= 0.5;
      assignTargets(lastThemeForAssign);
    }

    /* 按压 */
    const pr = state.pressTarget > state.press ? 30 : 21;
    state.press += (state.pressTarget - state.press) * (1 - Math.exp(-pr * dt));
    if (state.press < state.minPress) state.press = state.minPress;

    /* 形变弹簧 */
    const stretchTarget = Math.min(0.18, Math.abs(state.posV) * 0.024);
    state.deformV += ((stretchTarget - state.deform) * 420 - state.deformV * 24) * dt;
    state.deform += state.deformV * dt;

    /* 到轨道内壁的压缩 */
    const over = state.pos < 0 ? -state.pos : state.pos > 1 ? state.pos - 1 : 0;
    state.wallC += (Math.min(0.16, over * 1.12) - state.wallC) * (1 - Math.exp(-24 * dt));

    /* 激扰衰减 */
    state.excite *= Math.exp(-7 * dt);

    updateParticles(dt, now);
    render();
  }

  /* ---------- 渲染 ---------- */
  let thumbX = SCENE_W / 2;
  let sx = 1, sy = 1;

  function render() {
    const travelPos = clamp(state.pos, -0.02, 1.02);
    thumbX = SCENE_W / 2 + (travelPos - 0.5) * (TRAVEL * SHOW_SCALE) + (SCENE_W / 2 - TRACK_W * SHOW_SCALE / 2) * 0;
    /* 轨道左内壁 16 逻辑px：拇指中心 = 16+120 = 136 逻辑；行程 248 逻辑 */
    thumbX = (SCENE_W - TRACK_W * SHOW_SCALE) / 2 + (WALL + THUMB / 2 + travelPos * TRAVEL) * SHOW_SCALE;
    const wall = state.wallC;
    sx = (1 + state.deform) * (1 - wall) * (1 - 0.055 * state.press);
    sy = (1 - 0.45 * state.deform) * (1 + 0.42 * wall) * (1 - 0.055 * state.press);

    if (!use2D && gl) {
      gl.useProgram(glProgram);
      gl.uniform2f(glLoc.uRes, glCanvas.width, glCanvas.height);
      gl.uniform2f(glLoc.uScene, SCENE_W, sceneH);
      gl.uniform1f(glLoc.uTheme, state.theme);
      gl.uniform1f(glLoc.uThumbX, thumbX);
      gl.uniform1f(glLoc.uPress, state.press);
      gl.uniform1f(glLoc.uSx, sx);
      gl.uniform1f(glLoc.uSy, sy);
      gl.uniform1f(glLoc.uPhase, state.phase);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, glTex);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
    } else if (c2d) {
      render2D();
    }
  }

  function roundRectPath(ctx, x, y, w, h, r) {
    r = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  function render2D() {
    const W = c2dCanvas.width, H = c2dCanvas.height;
    const kx = W / SCENE_W, ky = H / sceneH;
    c2d.setTransform(kx, 0, 0, ky, 0, 0);
    /* 场景底 */
    const grad = c2d.createRadialGradient(SCENE_W * 0.92, -sceneH * 0.08, 10, SCENE_W * 0.92, -sceneH * 0.08, SCENE_W * 0.8);
    const nightA = state.theme < 0.5 ? '#212123' : '#ececea';
    const nightB = state.theme < 0.5 ? '#0d0d0e' : '#cdcdcc';
    grad.addColorStop(0, nightA);
    grad.addColorStop(1, nightB);
    c2d.fillStyle = grad;
    c2d.fillRect(0, 0, SCENE_W, sceneH);
    /* 轨道 */
    const tx = (SCENE_W - TRACK_W * SHOW_SCALE) / 2;
    const ty = (sceneH - TRACK_H * SHOW_SCALE) / 2;
    c2d.save();
    c2d.shadowColor = 'rgba(0,0,0,.45)';
    c2d.shadowBlur = 34;
    c2d.shadowOffsetY = 17;
    roundRectPath(c2d, tx, ty, TRACK_W * SHOW_SCALE, TRACK_H * SHOW_SCALE, TRACK_R * SHOW_SCALE);
    c2d.fillStyle = state.theme > 0.5 ? '#e6e6e6' : '#08080b';
    c2d.fill();
    c2d.restore();
    /* 拇指 */
    const tw = THUMB * SHOW_SCALE * sx;
    const th = THUMB * SHOW_SCALE * sy;
    const thumbLeft = thumbX - tw / 2;
    c2d.save();
    c2d.shadowColor = 'rgba(0,0,0,.5)';
    c2d.shadowBlur = 26;
    c2d.shadowOffsetY = 16;
    roundRectPath(c2d, thumbLeft, sceneH / 2 - th / 2, tw, th, THUMB_R * SHOW_SCALE);
    const g2 = c2d.createLinearGradient(0, sceneH / 2 - th / 2, 0, sceneH / 2 + th / 2);
    if (state.theme > 0.5) { g2.addColorStop(0, '#fdfdfc'); g2.addColorStop(1, '#edecea'); }
    else { g2.addColorStop(0, '#6b6b70'); g2.addColorStop(1, '#29292e'); }
    c2d.fillStyle = g2;
    c2d.fill();
    c2d.restore();
    /* 像素：夜间暖白加法发光；日间深灰覆盖，避免白像素画在白玻璃上不可见 */
    c2d.save();
    roundRectPath(c2d, thumbLeft, sceneH / 2 - th / 2, tw, th, THUMB_R * SHOW_SCALE);
    c2d.clip();
    if (state.theme > 0.5) {
      c2d.globalCompositeOperation = 'source-over';
      const tint = document.createElement('canvas');
      tint.width = TEX; tint.height = TEX;
      const tc = tint.getContext('2d');
      tc.drawImage(maskCanvas, 0, 0);
      tc.globalCompositeOperation = 'source-in';
      tc.fillStyle = '#2b2e33';
      tc.fillRect(0, 0, TEX, TEX);
      c2d.globalAlpha = 0.96;
      c2d.drawImage(tint, thumbLeft, sceneH / 2 - th / 2, tw, th);
    } else {
      c2d.globalCompositeOperation = 'lighter';
      c2d.globalAlpha = 0.96;
      c2d.drawImage(maskCanvas, thumbLeft, sceneH / 2 - th / 2, tw, th);
    }
    c2d.restore();
    /* 光带：多层路径描边 */
    const bandCenter = Math.PI / 2 - 2 * Math.PI * state.phase;
    const layers = [[64,0.05],[18,0.12],[9,0.28],[3.5,0.7]];
    c2d.save();
    c2d.globalCompositeOperation = 'lighter';
    layers.forEach(([w, a]) => {
      c2d.beginPath();
      let drawing = false;
      const steps = 120;
      for (let i = 0; i <= steps; i++) {
        const ang = (i / steps) * Math.PI * 2;
        const da = Math.atan2(Math.sin(ang - bandCenter), Math.cos(ang - bandCenter));
        if (Math.abs(da) <= 0.92) {
          const px = thumbX + Math.cos(ang) * (tw / 2 + 8);
          const py = sceneH / 2 + Math.sin(ang) * (th / 2 + 8);
          if (!drawing) { c2d.moveTo(px, py); drawing = true; } else c2d.lineTo(px, py);
        } else drawing = false;
      }
      c2d.lineWidth = w;
      c2d.globalAlpha = a;
      c2d.strokeStyle = state.theme > 0.5 ? '#ffa82e' : '#6f86ff';
      c2d.stroke();
    });
    c2d.restore();
  }

  /* ---------- 帧调度 ---------- */
  let frameHandle = 0;
  function requestRender() {
    if (state.onInvalidate) state.onInvalidate();
  }
  function tick(dt) { step(dt, performance.now()); }
  function isSettled() {
    if (state.dragging || state.press > 0.001 || state.pressTarget > 0) return false;
    if (state.phaseElapsed < 910) return false;
    if (state.themeElapsed < state.themeDur) return false;
    if (Math.abs(state.pos - state.posTarget) > 0.0005 || Math.abs(state.posV) > 0.0005) return false;
    if (Math.abs(state.deform) > 0.0005 || Math.abs(state.wallC) > 0.0005) return false;
    if (state.excite > 0.001) return false;
    return particles.every((p) => Math.abs(p.vx) + Math.abs(p.vy) < 0.02);
  }
  function settle() {
    state.theme = state.themeTo = state.checked ? 1 : 0;
    state.themeFrom = state.theme;
    state.themeElapsed = state.themeDur + 1;
    state.pos = state.posTarget = state.checked ? 1 : 0;
    state.posV = 0;
    state.phase = state.phaseTo = state.checked ? 0.5 : 0;
    state.phaseFrom = state.phase;
    state.phaseElapsed = 9999;
    state.press = state.pressTarget = 0;
    state.minPress = 0;
    state.deform = state.deformV = state.wallC = 0;
    state.excite = 0;
    state.dragging = false;
    assignTargets(state.checked);
    particles.forEach((p) => {
      p.alpha = p.targetAlpha;
      if (p.cell) { p.x = p.cell.x * GRID; p.y = p.cell.y * GRID; }
      p.vx = p.vy = 0;
    });
    render();
  }

  /* ---------- 交互 ---------- */
  function injectExcite(v) { state.excite = Math.min(1, state.excite + v); }

  function beginThemeTween(to) {
    state.themeFrom = state.theme;
    state.themeTo = to;
    state.themeElapsed = 0;
    state.themeDur = to > 0.5 ? 100 : 70;
  }

  function nextPhase(current, day) {
    const base = day ? 0.5 : 0;
    let t = base + Math.ceil(current - base + 0.1 + 1e-6);
    while (t - current < 0.1) t += 1;
    return t;
  }

  function beginPhase(day) {
    state.phaseFrom = state.phase;
    state.phaseTo = nextPhase(state.phase, day);
    state.phaseElapsed = 0;
  }

  function commit(checked, fromUser) {
    if (checked === state.checked && fromUser) return;
    state.checked = checked;
    button.setAttribute('aria-checked', checked ? 'true' : 'false');
    state.posTarget = checked ? 1 : 0;
    beginThemeTween(checked ? 1 : 0);
    beginPhase(checked);
    injectExcite(0.55);
    requestRender();
    if (fromUser) {
      if (state.sound) audio.play(checked);
      if (state.onCheckedChange) state.onCheckedChange(checked);
    }
  }

  function onDown(e) {
    if (state.destroyed || e.button > 0) return;
    try { button.setPointerCapture(e.pointerId); } catch (err) {}
    state.dragging = false;
    state.moved = false;
    state.dragStartX = e.clientX;
    state.dragStartPos = state.pos;
    state.pressTarget = 1;
    state.minPress = 0;
    injectExcite(0.25);
    const rect = stage.getBoundingClientRect();
    const fit = rect.width / SCENE_W || 1;
    state.pointer.x = (e.clientX - rect.left) / fit - (SCENE_W - TRACK_W * SHOW_SCALE) / 2;
    state.pointer.y = (e.clientY - rect.top) / fit - (sceneH / 2 - THUMB * SHOW_SCALE / 2);
    state.pointer.t = performance.now();
    requestRender();
  }

  function onMove(e) {
    if (state.destroyed) return;
    const rect = stage.getBoundingClientRect();
    const fit = rect.width / SCENE_W || 1;
    state.pointer.x = (e.clientX - rect.left) / fit - (SCENE_W - TRACK_W * SHOW_SCALE) / 2;
    state.pointer.y = (e.clientY - rect.top) / fit - (sceneH / 2 - THUMB * SHOW_SCALE / 2);
    state.pointer.t = performance.now();
    if (state.pressTarget < 0.5) return;
    const dx = (e.clientX - state.dragStartX) / fit;
    if (!state.moved && Math.abs(dx) <= 3) return;
    state.moved = true;
    state.dragging = true;
    const raw = state.dragStartPos + dx / TRAVEL;
    let pos;
    if (raw < 0) pos = -0.05 * Math.pow(-raw, 0.6);
    else if (raw > 1) pos = 1 + 0.05 * Math.pow(raw - 1, 0.6);
    else pos = raw;
    state.pos = pos;
    state.posV = 0;
    injectExcite(0.08);
    requestRender();
  }

  let lastFlick = { v: 0, t: 0 };

  function onUp(e) {
    if (state.destroyed) return;
    try { button.releasePointerCapture(e.pointerId); } catch (err) {}
    state.pointer.t = -1e9;
    if (state.moved) {
      const now = performance.now();
      const dt = Math.max(1, now - lastFlick.t);
      const vel = (state.pos - (lastFlick.pos ?? state.pos)) / dt;
      lastFlick = { v: vel, t: now, pos: state.pos };
      let target;
      if (Math.abs(lastFlick.v) > 0.6) target = lastFlick.v > 0 ? 1 : 0;
      else target = state.pos >= 0.5 ? 1 : 0;
      state.dragging = false;
      commit(!!target, true);
      state.suppressClick = true;
      setTimeout(() => { state.suppressClick = false; }, 0);
    } else {
      state.dragging = false;
      state.minPress = 0.65;
      state.pressTarget = 0;
      commit(!state.checked, true);
    }
    requestRender();
  }

  function onCancel() {
    state.dragging = false;
    state.pressTarget = 0;
    state.pos = state.checked ? 1 : 0;
    state.posTarget = state.checked ? 1 : 0;
    state.posV = 0;
    requestRender();
  }

  function onClick(e) {
    if (state.suppressClick) { state.suppressClick = false; return; }
    if (e.detail === 0) {
      state.minPress = 0.65;
      state.pressTarget = 0;
      commit(!state.checked, true);
      requestRender();
    }
  }

  button.addEventListener('pointerdown', onDown);
  button.addEventListener('pointermove', onMove);
  button.addEventListener('pointerup', onUp);
  button.addEventListener('pointercancel', onCancel);
  button.addEventListener('click', onClick);

  const ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(resize) : null;
  if (ro) ro.observe(host);
  else window.addEventListener('resize', resize);

  /* ---------- 对外 API ---------- */
  state.onInvalidate = typeof options.onInvalidate === 'function' ? options.onInvalidate : null;

  return {
    element: frame,
    button,
    tick,
    render,
    isSettled,
    settle,
    resize,
    getChecked: () => state.checked,
    setChecked(v, fromUser = false) {
      const next = !!v;
      state.checked = next;
      button.setAttribute('aria-checked', next ? 'true' : 'false');
      state.posTarget = next ? 1 : 0;
      beginThemeTween(next ? 1 : 0);
      beginPhase(next);
      requestRender();
      if (fromUser && state.onCheckedChange) state.onCheckedChange(next);
    },
    setHeight(h) {
      const nh = Math.max(240, Number(h) || SCENE_H);
      frame.style.height = nh + 'px';
      stage.style.height = nh + 'px';
      /* 场景高度属于几何配置，更新后重绘 */
      resize();
    },
    setReducedMotion(v) {
      state.reduced = !!v;
      if (state.reduced) settle();
    },
    setSound(v) { state.sound = !!v; },
    setInvalidate(fn) { state.onInvalidate = typeof fn === 'function' ? fn : null; },
    get sceneHeight() { return sceneH; },
    destroy() {
      if (state.destroyed) return;
      state.destroyed = true;
      button.removeEventListener('pointerdown', onDown);
      button.removeEventListener('pointermove', onMove);
      button.removeEventListener('pointerup', onUp);
      button.removeEventListener('pointercancel', onCancel);
      button.removeEventListener('click', onClick);
      glCanvas.removeEventListener('webglcontextlost', onContextLost);
      if (ro) ro.disconnect(); else window.removeEventListener('resize', resize);
      audio.destroy();
      if (gl) { try { gl.getExtension('WEBGL_lose_context')?.loseContext(); } catch (e) {} }
      if (frame.parentNode) frame.parentNode.removeChild(frame);
    }
  };
}

export default createPixelToggleEngine;
