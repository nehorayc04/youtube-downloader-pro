// רקע אנימטיבי בקוד — מסע תלת-ממדי בחלל )כוכבים + ערפיליות צבעוניות(.
// מעובד מ-StarfieldBackground של Game translator. ללא אינטראקציית עכבר —
// נקודת המגוז נעה בתנודה אוטומטית עדינה בלבד )steering תמיד כבוי(.
(function () {
  const canvas = document.getElementById('bg');
  if (!canvas) return;
  const ctx = canvas.getContext('2d', { alpha: false, desynchronized: true });
  if (!ctx) return;

  const MAX_DPR = 2, FOV = 0.55, FWD = 0.000075, LEAD = 0.85;
  const NICE = [205, 220, 245, 265, 285, 305, 325, 345, 18, 40, 192];
  const HUE_STEP = 7000, HUE_FULL = NICE.length * HUE_STEP;
  let width = 0, height = 0, halfW = 0, halfH = 0, projX = 0, projY = 0, gT = 0;

  function lerpHue(a, b, t) { const d = ((b - a + 540) % 360) - 180; return (a + d * t + 360) % 360; }
  function niceHue(phase) {
    const p = phase / HUE_STEP;
    const i = ((Math.floor(p) % NICE.length) + NICE.length) % NICE.length;
    const j = (i + 1) % NICE.length, f = p - Math.floor(p);
    return lerpHue(NICE[i], NICE[j], f * f * (3 - 2 * f));
  }
  function pickColor() {
    if (Math.random() < 0.74) return [niceHue(gT + Math.random() * HUE_FULL), 92];
    return [210, 14];
  }

  const CLOUDS = (() => {
    const P = [
      [0.20, 0.25, 0.34, 0.10], [0.50, 0.30, 0.40, 0.11], [0.80, 0.22, 0.32, 0.10],
      [0.15, 0.55, 0.30, 0.09], [0.40, 0.55, 0.38, 0.10], [0.66, 0.50, 0.34, 0.10],
      [0.88, 0.58, 0.30, 0.09], [0.28, 0.80, 0.32, 0.09], [0.55, 0.78, 0.36, 0.10],
      [0.78, 0.82, 0.30, 0.09], [0.10, 0.40, 0.24, 0.08], [0.95, 0.42, 0.24, 0.08],
      [0.45, 0.12, 0.26, 0.08], [0.62, 0.92, 0.26, 0.08], [0.34, 0.38, 0.30, 0.09],
      [0.72, 0.66, 0.30, 0.09],
    ];
    return P.map((p, k) => ({
      x: p[0], y: p[1], r: p[2], a: p[3], phase: (k / P.length) * HUE_FULL,
      dx: 0.000004 + 0.0000016 * (k % 5), dy: 0.000004 + 0.0000016 * ((k * 3) % 5),
    }));
  })();

  const SPRITE_N = 24, SPRITE_S = 64, SPRITE_STEP = 360 / SPRITE_N;
  let glowSprites = [], whiteSprite = null;
  function makeGlow(h, s, l0) {
    const c = document.createElement('canvas'); c.width = c.height = SPRITE_S;
    const g = c.getContext('2d');
    const gr = g.createRadialGradient(SPRITE_S / 2, SPRITE_S / 2, 0, SPRITE_S / 2, SPRITE_S / 2, SPRITE_S / 2);
    gr.addColorStop(0, `hsla(${h},${s}%,${l0}%,1)`);
    gr.addColorStop(0.32, `hsla(${h},${s}%,${Math.max(40, l0 - 16)}%,0.5)`);
    gr.addColorStop(1, `hsla(${h},${s}%,${Math.max(40, l0 - 26)}%,0)`);
    g.fillStyle = gr; g.fillRect(0, 0, SPRITE_S, SPRITE_S);
    return c;
  }
  function buildSprites() {
    glowSprites = [];
    for (let i = 0; i < SPRITE_N; i++) glowSprites.push(makeGlow(i * SPRITE_STEP, 92, 86));
    whiteSprite = makeGlow(210, 18, 94);
  }
  function spriteFor(h) { return glowSprites[((Math.round(h / SPRITE_STEP) % SPRITE_N) + SPRITE_N) % SPRITE_N]; }

  let nebCanvas = null, nebCtx = null, nebW = 0, nebH = 0, nebLast = 0, bgGrad = null, vgGrad = null;
  function buildNeb() {
    nebW = Math.max(2, Math.round(width / 2)); nebH = Math.max(2, Math.round(height / 2));
    nebCanvas = document.createElement('canvas'); nebCanvas.width = nebW; nebCanvas.height = nebH;
    nebCtx = nebCanvas.getContext('2d');
  }
  function bakeNeb(t) {
    const g = nebCtx; if (!g) return;
    g.clearRect(0, 0, nebW, nebH); g.globalCompositeOperation = 'lighter';
    for (const c of CLOUDS) {
      const hue = niceHue(gT + c.phase);
      const cx = (c.x + Math.sin(t * c.dx + c.phase) * 0.04) * nebW;
      const cy = (c.y + Math.cos(t * c.dy + c.phase) * 0.04) * nebH;
      const rad = c.r * Math.max(nebW, nebH) * (0.92 + 0.08 * Math.sin(t * c.dx * 1.7));
      const gr = g.createRadialGradient(cx, cy, 0, cx, cy, rad);
      gr.addColorStop(0, `hsla(${hue},85%,58%,${c.a * 1.5})`);
      gr.addColorStop(0.45, `hsla(${hue},82%,48%,${c.a * 0.7})`);
      gr.addColorStop(1, 'hsla(0,0%,0%,0)');
      g.fillStyle = gr; g.fillRect(0, 0, nebW, nebH);
    }
    g.globalCompositeOperation = 'source-over';
  }

  let dust = [], lights = [], bokeh = [], puffs = [];
  function rstar(s) {
    s.x = (Math.random() * 2 - 1) * 1.3; s.y = (Math.random() * 2 - 1) * 1.3; s.z = Math.random() * 0.3 + 0.7;
    const c = pickColor(); s.hue = c[0]; s.sat = c[1]; s.white = (c[1] < 40);
    s.size = Math.random() * 1.3 + 0.5; s.tw = Math.random() * 6.28; s.tws = 0.001 + Math.random() * 0.003;
    s.flare = Math.random() < 0.22 ? (0.6 + Math.random() * 0.4) : (Math.random() < 0.5 ? 0.18 + Math.random() * 0.25 : 0);
  }
  function rdust(d) {
    d.x = (Math.random() * 2 - 1) * 1.3; d.y = (Math.random() * 2 - 1) * 1.3; d.z = Math.random() * 0.3 + 0.7;
    const c = pickColor(); d.hue = c[0]; d.sat = Math.min(60, c[1]); d.col = `hsl(${d.hue},${d.sat}%,90%)`;
    d.tw = Math.random() * 6.28; d.tws = 0.002 + Math.random() * 0.004;
  }
  function rbokeh(b) {
    b.x = (Math.random() * 2 - 1) * 1.3; b.y = (Math.random() * 2 - 1) * 1.3; b.z = Math.random() * 0.4 + 0.6;
    const c = pickColor(); b.hue = c[0]; b.sat = Math.max(60, c[1]); b.size = 18 + Math.random() * 42; b.a = 0.05 + Math.random() * 0.10;
  }
  function rpuff(p) {
    p.x = (Math.random() * 2 - 1) * 1.5; p.y = (Math.random() * 2 - 1) * 1.5; p.z = Math.random() * 0.4 + 0.6;
    p.hue = niceHue(gT + Math.random() * HUE_FULL); p.size = 0.55 + Math.random() * 0.75;
  }
  function build() {
    const area = width * height;
    const nD = Math.max(350, Math.min(900, Math.round(area * 0.00038)));
    const nL = Math.max(180, Math.min(380, Math.round(area * 0.00013)));
    const nB = Math.max(18, Math.min(40, Math.round(area * 0.000016)));
    dust = Array.from({ length: nD }, () => { const d = {}; rdust(d); d.z = Math.random(); return d; });
    lights = Array.from({ length: nL }, () => { const s = {}; rstar(s); s.z = Math.random(); return s; });
    bokeh = Array.from({ length: nB }, () => { const b = {}; rbokeh(b); b.z = Math.random(); return b; });
    puffs = Array.from({ length: 10 }, () => { const p = {}; rpuff(p); p.z = Math.random(); return p; });
  }

  function resize() {
    const dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    width = window.innerWidth; height = window.innerHeight;
    halfW = width / 2; halfH = height / 2; projX = halfW * FOV; projY = halfH * FOV;
    canvas.width = Math.round(width * dpr); canvas.height = Math.round(height * dpr);
    canvas.style.width = width + 'px'; canvas.style.height = height + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    build();
    bgGrad = ctx.createRadialGradient(halfW, halfH * 1.05, 0, halfW, halfH, Math.max(width, height) * 0.75);
    bgGrad.addColorStop(0, '#0a0e24'); bgGrad.addColorStop(0.5, '#060818'); bgGrad.addColorStop(1, '#02030a');
    vgGrad = ctx.createRadialGradient(halfW, halfH, Math.min(width, height) * 0.35, halfW, halfH, Math.max(width, height) * 0.72);
    vgGrad.addColorStop(0, 'rgba(0,0,0,0)'); vgGrad.addColorStop(1, 'rgba(0,1,6,0.55)');
    buildNeb();
  }

  // ללא עכבר: headX/headY נעים בתנודה אוטומטית עדינה בלבד
  let headX = 0, headY = 0, roll = 0;
  let prev = performance.now();
  let raf = 0;
  let dtSmooth = 16.7, quality = 1, fpsAvg = 60;   // החלקה + הסתגלות FPS

  function render(ts) {
    // dt מוחלק וחסום ל-2 פריימים — פריים איטי בודד לא קופץ את כל הסצנה
    const raw = Math.min(ts - prev, 33); prev = ts; gT = ts;
    dtSmooth += (raw - dtSmooth) * 0.2;
    const dt = dtSmooth;
    fpsAvg += (1000 / Math.max(raw, 1) - fpsAvg) * 0.05;
    if (fpsAvg < 45 && quality > 0.35) quality -= 0.01;
    else if (fpsAvg > 57 && quality < 1) quality += 0.005;
    const adv = FWD * dt;

    const tgtX = 0.5 * (Math.sin(ts * 0.000040) + 0.5 * Math.sin(ts * 0.000093 + 1.3));
    const tgtY = 0.5 * (Math.cos(ts * 0.000034) + 0.5 * Math.sin(ts * 0.000077 + 2.1));
    headX += (tgtX - headX) * 0.02;
    headY += (tgtY - headY) * 0.02;
    roll += (headX * 0.05 - roll) * 0.04;

    ctx.fillStyle = bgGrad; ctx.fillRect(0, 0, width, height);

    if (ts - nebLast > 100) { nebLast = ts; bakeNeb(ts); }   // gate לפי זמן, לא מונה פריימים
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = 0.3 * quality;
    if (nebCanvas) ctx.drawImage(nebCanvas, 0, 0, width, height);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';

    ctx.save();
    ctx.translate(halfW, halfH); ctx.rotate(roll); ctx.translate(-halfW, -halfH);
    ctx.globalCompositeOperation = 'lighter';

    for (const p of puffs) {
      p.z -= adv * 0.7; if (p.z <= 0.04) { rpuff(p); continue; }
      const k = 1 / p.z;
      const sx = halfW + p.x * k * projX + headX * LEAD * halfW * p.z;
      const sy = halfH + p.y * k * projY + headY * LEAD * halfH * p.z;
      const depth = 1 - p.z;
      const rad = p.size * Math.max(width, height) * (0.18 + depth * 1.3);
      const near = Math.max(0, (depth - 0.55) / 0.45);
      const af = Math.min(1, depth * 1.8) * (1 - Math.min(1, near));
      if (af <= 0.01) continue;
      ctx.globalAlpha = 0.06 * af;
      ctx.drawImage(spriteFor(p.hue), sx - rad, sy - rad, rad * 2, rad * 2);
    }
    for (const b of bokeh) {
      b.z -= adv * 0.6; if (b.z <= 0.05) { rbokeh(b); continue; }
      const k = 1 / b.z;
      const sx = halfW + b.x * k * projX + headX * LEAD * halfW * b.z;
      const sy = halfH + b.y * k * projY + headY * LEAD * halfH * b.z;
      const rr = b.size * (0.5 + (1 / b.z - 1) * 1.4);
      if (sx < -rr || sx > width + rr || sy < -rr || sy > height + rr) continue;
      ctx.globalAlpha = Math.min(1, b.a * 2.4);
      ctx.drawImage(spriteFor(b.hue), sx - rr, sy - rr, rr * 2, rr * 2);
    }
    for (const d of dust) {
      d.z -= adv; if (d.z <= 0.02) { rdust(d); continue; }
      d.tw += d.tws * dt;
      const k = 1 / d.z;
      const sx = halfW + d.x * k * projX + headX * LEAD * halfW * d.z;
      const sy = halfH + d.y * k * projY + headY * LEAD * halfH * d.z;
      if (sx < 0 || sx > width || sy < 0 || sy > height) continue;
      const depth = 1 - d.z;
      ctx.globalAlpha = (0.25 + depth * 0.6) * (0.7 + 0.3 * Math.sin(d.tw));
      ctx.fillStyle = d.col;
      const ds = 0.8 + depth * 1.4; ctx.fillRect(sx, sy, ds, ds);
    }
    for (const s of lights) {
      s.z -= adv; if (s.z <= 0.02) { rstar(s); continue; }
      s.tw += s.tws * dt;
      const k = 1 / s.z;
      const sx = halfW + s.x * k * projX + headX * LEAD * halfW * s.z;
      const sy = halfH + s.y * k * projY + headY * LEAD * halfH * s.z;
      const depth = 1 - s.z, rr = s.size * (0.5 + depth * depth * 3.2);
      if (sx < -80 || sx > width + 80 || sy < -80 || sy > height + 80) continue;
      const tw = 0.78 + 0.22 * Math.sin(s.tw);
      const a = (0.3 + depth * 0.7) * tw;
      const spr = s.white ? whiteSprite : spriteFor(s.hue);
      const R = rr * 3;
      ctx.globalAlpha = Math.min(1, a);
      ctx.drawImage(spr, sx - R, sy - R, R * 2, R * 2);
      if (quality > 0.55 && s.flare > 0 && depth > 0.15) {
        const fb = s.flare * depth * tw, L = rr * (9 + s.flare * 30);
        ctx.globalAlpha = Math.min(1, 0.5 * fb);
        ctx.drawImage(spr, sx - L, sy - rr * 0.9, L * 2, rr * 1.8);
        ctx.globalAlpha = Math.min(1, 0.28 * fb);
        ctx.drawImage(spr, sx - rr * 0.9, sy - L * 0.5, rr * 1.8, L);
      }
      if (quality > 0.7 && depth > 0.78) {
        const el = R * (1.0 + (depth - 0.78) * 4.0);
        ctx.globalAlpha = Math.min(1, a * 0.4);
        ctx.drawImage(spr, sx - el, sy - R * 0.5, el * 2, R);   // ללא save/rotate — חוסך push/pop מטריצה
      }
    }

    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';
    ctx.restore();
    ctx.fillStyle = vgGrad; ctx.fillRect(0, 0, width, height);
    raf = requestAnimationFrame(render);
  }

  function start() { cancelAnimationFrame(raf); prev = performance.now(); raf = requestAnimationFrame(render); }
  function stop() { cancelAnimationFrame(raf); }

  buildSprites();
  resize();
  window.addEventListener('resize', resize);
  document.addEventListener('visibilitychange', () => (document.hidden ? stop() : start()));
  start();
})();
