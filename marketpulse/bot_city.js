// ============================================================
// city.js — the neon bot-city renderer (shared by the Etsy agent
// pod AND the Stackz bot city). One file, two skylines.
//
// LEARN: this is a "2.5D" city drawn on a flat <canvas>.
// The trick for depth without a 3D library:
//   * back row of towers drawn smaller + dimmer (far away)
//   * front row drawn bigger + brighter (close up)
//   * paint back-to-front so near towers overlap far ones
// Everything else is glow (shadowBlur), gradients, and motion.
// ============================================================

function initCity(canvasId, config) {
  const canvas = document.getElementById(canvasId);
  if (!canvas || !config) return;
  const ctx = canvas.getContext('2d');
  const stillMode = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let W = 0, H = 0, horizon = 0, towers = [];
  let domeGeom = { cx: 0, r: 80 };
  // LEARN: background city dressing — generated once in layout().
  let skylineFar = [], skylineNear = [], cars = [], arcs = [];
  let lastArc = 0;
  const rnd = (a, b) => a + Math.random() * (b - a);
  const particles = [];

  // LEARN: turn raw metric values into tower heights.
  // Math.max(..., 0.18) guarantees even a zero-value tower
  // still shows as a small "standby" building, never invisible.
  function layout() {
    const dpr = window.devicePixelRatio || 1;
    W = canvas.clientWidth;
    H = canvas.clientHeight;
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    horizon = H * 0.72;

    const vals = config.towers.map(t => t.value);
    const maxV = Math.max(...vals, 1);
    const n = config.towers.length;
    // LEARN: the dome gets its own reserved slot in the middle of
    // the skyline (a "plaza") so it never overlaps a tower.
    const slots = n + 1;
    const domeSlot = Math.floor(slots / 2);
    const slotW = W / slots;
    // stash the plaza geometry for drawDome()
    domeGeom = { cx: slotW * domeSlot + slotW / 2,
                 r: Math.min(slotW * 0.44, 100) };

    towers = config.towers.map((t, i) => {
      const slot = i >= domeSlot ? i + 1 : i;      // skip the plaza slot
      const backRow = i % 2 === 1;                    // alternate rows for depth
      const hgt = (0.18 + 0.82 * (t.value / maxV));    // normalized 0.18..1
      const baseH = H * 0.52;
      const h = baseH * hgt * (backRow ? 0.72 : 1);    // back row shorter
      const w = Math.min(slotW * 0.52, backRow ? 54 : 70);
      const x = slotW * slot + slotW / 2 - w / 2;
      const y = horizon - h;
      // LEARN: each tower gets its own random lit windows so no
      // two buildings look identical.
      const winCols = Math.max(2, Math.floor(w / 14));
      const winRows = Math.max(3, Math.floor(h / 18));
      const windows = [];
      for (let r = 0; r < winRows; r++)
        for (let c = 0; c < winCols; c++)
          if (Math.random() < 0.45) windows.push([c, r]);
      return { ...t, x, y, w, h, backRow, winCols, winRows, windows,
               phase: rnd(0, Math.PI * 2), beacon: Math.random() < 0.7,
               // LEARN: alternate label heights so neighboring
               // name tags never collide on narrow screens.
               labelLift: (i % 2 === 0) ? 18 : 34 };
    });

    // LEARN: ambient particles drift up like heat/data rising.
    particles.length = 0;
    for (let i = 0; i < 40; i++)
      particles.push({ x: rnd(0, W), y: rnd(horizon * 0.3, H),
                       s: rnd(0.6, 2), v: rnd(0.15, 0.5), a: rnd(0.1, 0.4) });

    // LEARN: "more city" = layers. Two rows of dark background
    // silhouettes with a few lit windows sell a whole metropolis
    // behind the hero towers, for almost zero drawing cost.
    skylineFar = []; skylineNear = [];
    let sx = -20;
    while (sx < W + 40) {
      const w = rnd(30, 70);
      skylineFar.push({ x: sx, w, h: rnd(H * 0.08, H * 0.22) });
      sx += w + rnd(2, 10);
    }
    sx = -30;
    while (sx < W + 60) {
      const w = rnd(40, 90), h = rnd(H * 0.05, H * 0.16);
      const cols = Math.max(2, Math.floor(w / 12));
      const rows = Math.max(2, Math.floor(h / 14));
      const wins = [];
      for (let r = 0; r < rows; r++)
        for (let c = 0; c < cols; c++)
          if (Math.random() < 0.22) wins.push([c, r]);
      skylineNear.push({ x: sx, w, h, cols, rows, wins });
      sx += w + rnd(4, 14);
    }
    // LEARN: street traffic — glowing dots cruising two lanes.
    // Warm white one way, red taillights the other, like a real road.
    cars = [];
    for (let i = 0; i < 14; i++) {
      const lane = i % 2;
      cars.push({ lane, x: rnd(0, W),
                  v: rnd(0.6, 2.2) * (lane ? -1 : 1),
                  c: lane ? '#ff6b6b' : '#ffe9a8' });
    }
    arcs = [];
    lastArc = 0;
  }

  function drawSky(t) {
    const g = ctx.createLinearGradient(0, 0, 0, H);
    g.addColorStop(0, '#04060d');
    g.addColorStop(0.7, '#0a1020');
    g.addColorStop(1, '#07080b');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, W, H);
    // stars
    ctx.fillStyle = '#fff';
    for (let i = 0; i < 60; i++) {
      const sx = (i * 197.3) % W, sy = (i * 89.7) % (horizon * 0.5);
      ctx.globalAlpha = 0.25 + 0.25 * Math.sin(t / 900 + i);
      ctx.fillRect(sx, sy, 1.5, 1.5);
    }
    ctx.globalAlpha = 1;
  }

  // LEARN: the moon — a pale disc with a soft halo and two
  // craters. One gradient + three circles, done.
  function drawMoon() {
    const mx = W * 0.86, my = H * 0.13, r = Math.max(14, W * 0.02);
    const halo = ctx.createRadialGradient(mx, my, r * 0.4, mx, my, r * 3);
    halo.addColorStop(0, 'rgba(220,230,255,.45)');
    halo.addColorStop(1, 'rgba(220,230,255,0)');
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(mx, my, r * 3, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = '#dfe7f5';
    ctx.beginPath(); ctx.arc(mx, my, r, 0, Math.PI * 2); ctx.fill();
    ctx.fillStyle = 'rgba(160,175,205,.55)';
    ctx.beginPath(); ctx.arc(mx - r * 0.3, my - r * 0.15, r * 0.2, 0, Math.PI * 2); ctx.fill();
    ctx.beginPath(); ctx.arc(mx + r * 0.25, my + r * 0.3, r * 0.14, 0, Math.PI * 2); ctx.fill();
  }

  // LEARN: paint the two silhouette layers. Far = flat dark,
  // near = dark + a sprinkle of lit windows.
  function drawSkyline() {
    ctx.fillStyle = '#070c16';
    skylineFar.forEach(b => ctx.fillRect(b.x, horizon - b.h, b.w, b.h));
    skylineNear.forEach(b => {
      ctx.fillStyle = '#0b1120';
      ctx.fillRect(b.x, horizon - b.h, b.w, b.h);
      ctx.fillStyle = 'rgba(255,220,150,.25)';
      const cw = b.w / b.cols, ch = b.h / b.rows;
      b.wins.forEach(([c, r]) =>
        ctx.fillRect(b.x + c * cw + cw * 0.3, horizon - b.h + r * ch + ch * 0.3,
                     cw * 0.4, ch * 0.4));
    });
  }

  // LEARN: streets are two glowing lanes on the ground strip;
  // the cars wrap around so traffic never stops.
  function drawStreets() {
    const lanes = [horizon + 16, horizon + 44];
    ctx.save();
    lanes.forEach(y => {
      ctx.globalAlpha = 0.22;
      ctx.strokeStyle = '#2a3350';
      ctx.lineWidth = 3;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    });
    ctx.globalAlpha = 1;
    cars.forEach(car => {
      const y = lanes[car.lane];
      car.x += car.v;
      if (car.x > W + 10) car.x = -10;
      if (car.x < -10) car.x = W + 10;
      ctx.shadowColor = car.c;
      ctx.shadowBlur = 8;
      ctx.fillStyle = car.c;
      ctx.fillRect(car.x, y - 1.5, 7, 3);
    });
    ctx.restore();
  }

  // LEARN: data arcs — every few seconds two towers "talk".
  // An arc is a quadratic curve with a marching dash that fades out.
  function drawArcs(t) {
    arcs = arcs.filter(a => t - a.born < 1400);
    if (t - lastArc > 3800 && towers.length > 3) {
      lastArc = t;
      const a = towers[Math.floor(rnd(0, towers.length))];
      const b = towers[Math.floor(rnd(0, towers.length))];
      if (a !== b) arcs.push({ ax: a.x + a.w / 2, ay: a.y,
                               bx: b.x + b.w / 2, by: b.y, born: t });
    }
    arcs.forEach(a => {
      const age = (t - a.born) / 1400;                 // 0 → 1
      const mx = (a.ax + a.bx) / 2;
      const my = Math.min(a.ay, a.by) - 60;
      ctx.save();
      ctx.globalAlpha = 0.5 * (1 - age);
      ctx.strokeStyle = config.accent || '#4da3ff';
      ctx.setLineDash([6, 6]);
      ctx.lineDashOffset = -t / 40;
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.moveTo(a.ax, a.ay);
      ctx.quadraticCurveTo(mx, my, a.bx, a.by);
      ctx.stroke();
      ctx.restore();
    });
  }

  function drawGround() {    const g = ctx.createLinearGradient(0, horizon, 0, H);
    g.addColorStop(0, '#0b1220');
    g.addColorStop(1, '#04050a');
    ctx.fillStyle = g;
    ctx.fillRect(0, horizon, W, H - horizon);
    // neon horizon line
    ctx.save();
    ctx.shadowColor = config.accent || '#4da3ff';
    ctx.shadowBlur = 12;
    ctx.strokeStyle = config.accent || '#4da3ff';
    ctx.globalAlpha = 0.7;
    ctx.lineWidth = 2;
    ctx.beginPath(); ctx.moveTo(0, horizon); ctx.lineTo(W, horizon); ctx.stroke();
    ctx.restore();
  }

  // LEARN: a tower is 3 rects — dark body, neon left edge,
  // and a lit window grid — plus a blinking beacon on top.
  function drawTower(tw, t) {
    const pulse = 0.85 + 0.15 * Math.sin(t / 1200 + tw.phase);
    ctx.save();
    if (tw.backRow) ctx.globalAlpha = 0.62;

    // body
    const bg = ctx.createLinearGradient(tw.x, 0, tw.x + tw.w, 0);
    bg.addColorStop(0, '#0d1424');
    bg.addColorStop(1, '#131c33');
    ctx.fillStyle = bg;
    ctx.fillRect(tw.x, tw.y, tw.w, tw.h);

    // neon edge
    ctx.shadowColor = tw.color;
    ctx.shadowBlur = 14 * pulse;
    ctx.strokeStyle = tw.color;
    ctx.lineWidth = 2;
    ctx.strokeRect(tw.x, tw.y, tw.w, tw.h);
    ctx.shadowBlur = 0;

    // windows
    const cw = tw.w / tw.winCols, ch = tw.h / tw.winRows;
    tw.windows.forEach(([c, r]) => {
      const flicker = 0.5 + 0.5 * Math.sin(t / 700 + c * 3 + r * 7 + tw.phase);
      ctx.globalAlpha = (tw.backRow ? 0.5 : 0.85) * (0.35 + 0.65 * flicker);
      ctx.fillStyle = tw.color;
      ctx.fillRect(tw.x + c * cw + cw * 0.25, tw.y + r * ch + ch * 0.3,
                   cw * 0.5, ch * 0.4);
    });
    ctx.globalAlpha = tw.backRow ? 0.62 : 1;

    // rooftop mast — a thin antenna above the roofline
    ctx.globalAlpha = tw.backRow ? 0.5 : 0.85;
    ctx.strokeStyle = tw.color;
    ctx.lineWidth = 1.5;
    ctx.beginPath();
    ctx.moveTo(tw.x + tw.w / 2, tw.y);
    ctx.lineTo(tw.x + tw.w / 2, tw.y - 10);
    ctx.stroke();
    ctx.globalAlpha = tw.backRow ? 0.62 : 1;

    // beacon
    if (tw.beacon) {
      const on = Math.sin(t / 400 + tw.phase) > 0;
      ctx.fillStyle = on ? '#ff5f5f' : '#5a2020';
      ctx.shadowColor = '#ff5f5f';
      ctx.shadowBlur = on ? 10 : 0;
      ctx.beginPath();
      ctx.arc(tw.x + tw.w / 2, tw.y - 5, 3, 0, Math.PI * 2);
      ctx.fill();
      ctx.shadowBlur = 0;
    }

    // reflection on the ground
    const rg = ctx.createLinearGradient(0, horizon, 0, H);
    rg.addColorStop(0, tw.color);
    rg.addColorStop(1, 'transparent');
    ctx.globalAlpha = 0.12;
    ctx.fillStyle = rg;
    ctx.fillRect(tw.x, horizon, tw.w, (H - horizon) * 0.8);
    ctx.restore();

    // label (drawn unscaled by row dimming so it stays readable).
    // LEARN: quiet towers (empty name, e.g. standby strategies)
    // get no label at all — in a dense skyline, silence beats clutter.
    // And on phones with 10+ towers, ALL canvas labels are skipped:
    // the page renders an HTML legend below instead (readable text
    // beats overlapping tags).
    if (!tw.name || (W < 500 && towers.length > 10)) { ctx.globalAlpha = 1; return; }
    // On phones the sub-line is dropped and the tag shrinks —
    // the tower color already tells the story.
    const compact = W < 500;
    // LEARN: clamp the label inside the canvas so the first and
    // last towers' name tags never get clipped at the edges.
    const lx = Math.max(34, Math.min(W - 34, tw.x + tw.w / 2));
    const ly = tw.y - tw.labelLift;
    ctx.textAlign = 'center';
    ctx.fillStyle = tw.color;
    ctx.globalAlpha = tw.backRow ? 0.75 : 1;
    ctx.font = `700 ${compact ? 8 : 9}px ui-monospace, monospace`;
    ctx.fillText(tw.name, lx, ly);
    if (!compact) {
      ctx.fillStyle = 'rgba(236,233,223,.8)';
      ctx.font = '9px ui-monospace, monospace';
      ctx.fillText(tw.sub || '', lx, ly + 11);
    }
    ctx.globalAlpha = 1;
  }

  // LEARN: rounded-rect helper (canvas has no built-in one).
  function roundRectPath(x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + w, y, x + w, y + h, r);
    ctx.arcTo(x + w, y + h, x, y + h, r);
    ctx.arcTo(x, y + h, x, y, r);
    ctx.arcTo(x, y, x + w, y, r);
    ctx.closePath();
  }

  // LEARN: the dome is the city's scoreboard — one glowing arc
  // with the headline number floating inside it. It sits in its
  // own plaza slot (see layout), and its text scales with the
  // available radius so it stays legible on phones.
  function drawDome(t) {
    const d = config.dome;
    if (!d) return;
    const pulse = 0.75 + 0.25 * Math.sin(t / 1500);
    const roomy = W > 500;   // desktop: arc in plaza; phone: pill HUD
    ctx.save();
    ctx.textAlign = 'center';

    if (!roomy) {
      // LEARN: on phones the plaza slot is too narrow for the arc,
      // so the scoreboard becomes a glowing pill parked on the
      // ground strip — same info, zero overlap.
      const pw = Math.min(W * 0.72, 280), ph = 46;
      const px = W / 2 - pw / 2, py = horizon + (H - horizon) / 2 - ph / 2;
      ctx.shadowColor = config.accent || '#4da3ff';
      ctx.shadowBlur = 14 * pulse;
      ctx.fillStyle = 'rgba(10,16,32,.92)';
      roundRectPath(px, py, pw, ph, 10);
      ctx.fill();
      ctx.shadowBlur = 0;
      ctx.strokeStyle = config.accent || '#4da3ff';
      ctx.lineWidth = 1.5;
      ctx.stroke();
      ctx.fillStyle = 'rgba(236,233,223,.7)';
      ctx.font = '700 8px ui-monospace, monospace';
      ctx.fillText(d.title, W / 2, py + 16);
      ctx.fillStyle = '#fff';
      ctx.font = '800 16px ui-monospace, monospace';
      ctx.fillText(d.value, W / 2, py + 35);
      ctx.restore();
      return;
    }

    const cx = domeGeom.cx, r = domeGeom.r;
    const cy = horizon + 6;
    // glass
    const g = ctx.createRadialGradient(cx, cy, r * 0.1, cx, cy, r);
    g.addColorStop(0, 'rgba(77,163,255,.28)');
    g.addColorStop(1, 'rgba(77,163,255,.04)');
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, 0); ctx.fill();
    // rim
    ctx.shadowColor = config.accent || '#4da3ff';
    ctx.shadowBlur = 18 * pulse;
    ctx.strokeStyle = config.accent || '#4da3ff';
    ctx.lineWidth = 2.5;
    ctx.beginPath(); ctx.arc(cx, cy, r, Math.PI, 0); ctx.stroke();
    ctx.shadowBlur = 0;
    // numbers — font sized to the dome radius
    const vSize = Math.max(11, Math.min(20, r * 0.24));
    ctx.textAlign = 'center';
    ctx.fillStyle = '#fff';
    ctx.font = `800 ${vSize}px ui-monospace, monospace`;
    ctx.fillText(d.value, cx, cy - r * 0.42);
    ctx.fillStyle = 'rgba(236,233,223,.75)';
    ctx.font = `700 ${Math.max(8, vSize * 0.45)}px ui-monospace, monospace`;
    // LEARN: shortTitle is the compact dome caption for the arc —
    // the full title would spill over the neighboring towers.
    ctx.fillText(d.shortTitle || d.title, cx, cy - r * 0.42 - vSize - 4);
    if (roomy) {
      ctx.font = '9px ui-monospace, monospace';
      ctx.fillText(d.sub || '', cx, cy - r * 0.42 + 15);
    }
    ctx.restore();
  }

  function drawParticles() {
    ctx.fillStyle = config.accent || '#4da3ff';
    particles.forEach(p => {
      ctx.globalAlpha = p.a;
      ctx.fillRect(p.x, p.y, p.s, p.s);
      p.y -= p.v;
      if (p.y < horizon * 0.25) { p.y = H; p.x = rnd(0, W); }
    });
    ctx.globalAlpha = 1;
  }

  function frame(t) {
    if (!document.hidden) {
      drawSky(t);
      drawMoon();
      drawSkyline();
      // LEARN: paint far towers first, near last — the overlap
      // sells the depth.
      towers.filter(tw => tw.backRow).forEach(tw => drawTower(tw, t));
      drawGround();
      drawStreets();
      towers.filter(tw => !tw.backRow).forEach(tw => drawTower(tw, t));
      drawDome(t);
      drawArcs(t);
      drawParticles();
    }
    if (!stillMode) requestAnimationFrame(frame);
  }

  layout();
  frame(0);
  // LEARN: redraw the layout when the window changes size so the
  // skyline always fits — same resize lesson as station.js.
  window.addEventListener('resize', () => { layout(); });
  if (!stillMode) requestAnimationFrame(frame);
}
