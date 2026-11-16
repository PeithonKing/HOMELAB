// Grouped bar chart of the benchmark matrix. No dependencies; works from file:// (data comes from data.js).
// window.BENCH_DATA = { datasets: [ { id, label, machine, mode, info, results: [ {L, precision, passes, device,
//                                    iterations, solve_s_mean, solve_s_std, energy, dim, runs} ] } ] }
const DATA = window.BENCH_DATA;
const $ = (id) => document.getElementById(id);

// Same colour pairs as the old page: dark = single-pass, light = two-pass.
const COLORS = {
  "32 cpu 1": "#1f77b4", "32 cpu 2": "#aec7e8", "32 gpu 1": "#2ca02c", "32 gpu 2": "#98df8a",
  "64 cpu 1": "#d62728", "64 cpu 2": "#ff9896", "64 gpu 1": "#9467bd", "64 gpu 2": "#c5b0d5",
};
const PRECISIONS = [32, 64], DEVICES = ["cpu", "gpu"], PASSES = [1, 2];
const key = (p, d, n) => `${p} ${d} ${n}`;
const name = (p, d, n) => `FP${p} ${d.toUpperCase()} ${n === 1 ? "Single" : "Two"}-Pass`;

const state = { enabled: new Set(Object.keys(COLORS)), ds: null, Ls: [], devs: new Set(DEVICES),
  // L range the user chose, kept when switching dataset (not across page reloads). "min"/"max" follow the dataset's ends.
  lrange: { lo: "min", hi: "max" } };

function fmtTime(s) { return s >= 100 ? s.toFixed(1) : s >= 1 ? s.toFixed(3) : s.toFixed(4); }
function fmtVal(v, metric) {
  if (metric === "speedup") return v.toFixed(2) + "×";
  if (metric === "per_iter") return (v >= 100 ? v.toFixed(0) : v.toFixed(2)) + " ms";
  return fmtTime(v) + "s";
}

function value(r, metric, ref) {
  if (r.error) return 0;
  if (metric === "per_iter") return (r.solve_s_mean * 1000) / Math.max(r.iterations, 1);
  if (metric === "speedup") return ref ? (ref.solve_s_mean / Math.max(ref.iterations, 1)) / (r.solve_s_mean / Math.max(r.iterations, 1)) : NaN;
  return r.solve_s_mean;
}

function find(ds, L, p, d, n) {
  return ds.results.find((r) => r.L === L && r.precision === p && r.device === d && r.passes === n);
}

function buildControls() {
  const sel = $("dataset");
  DATA.datasets.forEach((d, i) => sel.add(new Option(d.label, i)));
  sel.onchange = () => { selectDataset(DATA.datasets[sel.value]); };
  $("metric").onchange = $("log").onchange = draw;
  $("lmin").oninput = $("lmax").oninput = (e) => {
    // The knob being dragged pushes the other one along, so the lower limit never passes the upper.
    const lo = $("lmin"), hi = $("lmax");
    if (+lo.value > +hi.value) (e.target === lo ? hi : lo).value = e.target.value;
    const last = state.Ls.length - 1;
    state.lrange = { lo: +lo.value === 0 ? "min" : state.Ls[+lo.value], hi: +hi.value === last ? "max" : state.Ls[+hi.value] };
    draw();
  };

  $("matrix").onchange = (e) => {
    const el = e.target, ds = el.dataset, on = el.checked;
    const set = (k) => (on ? state.enabled.add(k) : state.enabled.delete(k));
    const devs = DEVICES.filter((d) => state.devs.has(d));
    if (ds.k) set(ds.k);
    if (ds.p) for (const d of devs) for (const n of PASSES) set(key(ds.p, d, n));      // whole row (one precision)
    if (ds.c) { const [d, n] = ds.c.split(" "); for (const p of PRECISIONS) set(key(p, d, +n)); } // whole column
    syncChecks();
    draw();
  };
}

// One table: a row per precision, a column per (device, pass) the dataset has data for.
function renderMatrix() {
  const devs = DEVICES.filter((d) => state.devs.has(d));
  const head = devs.length > 1 ? `<tr><th></th>${devs.map((d) => `<th colspan="2">${d.toUpperCase()}</th>`).join("")}</tr>` : "";
  const cols = devs.flatMap((d) => PASSES.map((n) => `<th><input type="checkbox" data-c="${d} ${n}"> ${n === 1 ? "SP" : "TP"}</th>`)).join("");
  const rows = PRECISIONS.map((p) => `<tr><th><input type="checkbox" data-p="${p}"> ${p}-bit</th>` +
    devs.flatMap((d) => PASSES.map((n) => `<td><input type="checkbox" data-k="${key(p, d, n)}">
      <span class="swatch" style="background:${COLORS[key(p, d, n)]}"></span></td>`)).join("") + "</tr>").join("");
  $("matrix").innerHTML = `<table class="m">${head}<tr><th></th>${cols}</tr>${rows}</table>`;
}

function syncChecks() {
  const on = (k) => state.enabled.has(k);
  const DEV = DEVICES.filter((d) => state.devs.has(d));
  document.querySelectorAll("#matrix input").forEach((el) => {
    const d = el.dataset;
    if (d.k) el.checked = on(d.k);
    if (d.p) el.checked = DEV.every((x) => PASSES.every((n) => on(key(d.p, x, n))));
    if (d.c) { const [x, n] = d.c.split(" "); el.checked = PRECISIONS.every((p) => on(key(p, x, +n))); }
  });
}

function selectDataset(ds) {
  state.ds = ds;
  state.Ls = [...new Set(ds.results.map((r) => r.L))].sort((a, b) => a - b);
  for (const id of ["lmin", "lmax"]) {
    const el = $(id);
    el.min = 0; el.max = state.Ls.length - 1; el.step = 1;
  }
  const { lo, hi } = state.lrange, last = state.Ls.length - 1;
  let i = lo === "min" ? 0 : state.Ls.findIndex((L) => L >= lo);          // first size at or above the remembered lower limit
  let j = hi === "max" ? last : state.Ls.map((L) => L <= hi).lastIndexOf(true); // last size at or below the upper limit
  if (i < 0 || j < 0 || i > j) { i = 0; j = last; }                       // remembered range does not overlap this dataset
  $("lmin").value = i; $("lmax").value = j;
  // Only the devices the dataset has data for get columns (e.g. a CPU-only machine).
  const devs = new Set(ds.results.map((r) => r.device));
  state.devs = devs;
  for (const k of Object.keys(COLORS)) {
    const d = k.split(" ")[1];
    if (!devs.has(d)) state.enabled.delete(k); else state.enabled.add(k);
  }
  renderMatrix();
  syncChecks();
  $("meta").textContent = ds.info;
  draw();
}

function niceTicks(max, n = 6) {
  const raw = max / n, mag = 10 ** Math.floor(Math.log10(raw)), f = raw / mag;
  const step = (f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10) * mag;
  const out = [];
  for (let v = 0; v <= max * 1.02 + step; v += step) { out.push(v); if (v > max) break; }
  return out;
}

function draw() {
  const ds = state.ds, metric = $("metric").value, logy = $("log").checked;
  const lo = +$("lmin").value, hi = +$("lmax").value;
  const Ls = state.Ls.slice(lo, hi + 1);
  $("lrange-label").textContent = Ls[0] === Ls[Ls.length - 1] ? `${Ls[0]}` : `${Ls[0]} – ${Ls[Ls.length - 1]}`;
  const span = Math.max(state.Ls.length - 1, 1);
  $("lmin").style.zIndex = lo > span / 2 ? 3 : 1; // when both knobs coincide, the one that can still move stays on top
  $("lfill").style.left = `${(lo / span) * 100}%`;
  $("lfill").style.right = `${100 - (hi / span) * 100}%`;
  const unit = { time: "Execution Time (s)", per_iter: "Time per iteration (ms)", speedup: "Speed-up (×)" }[metric];
  $("title").textContent = `QKrylov Benchmark (${ds.label})`;

  const series = Object.keys(COLORS).filter((k) => state.enabled.has(k));
  const rows = [];
  for (const L of Ls) {
    const ref = find(ds, L, 64, "cpu", 1) || find(ds, L, 64, "gpu", 1);
    for (const k of series) {
      const [p, d, n] = k.split(" ");
      const r = find(ds, L, +p, d, +n);
      if (r) rows.push({ L, k, r, v: value(r, metric, ref) });
    }
  }
  const W = 1200, H = 620, M = { l: 70, r: 190, t: 20, b: 70 };
  const pw = W - M.l - M.r, ph = H - M.t - M.b;
  const vals = rows.filter((x) => !x.r.error).map((x) => x.v).filter((v) => v > 0 && isFinite(v));
  let svg = `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" font-size="12">`;
  if (!vals.length) { $("chart").innerHTML = svg + `<text x="${W / 2}" y="${H / 2}" text-anchor="middle">no data selected</text></svg>`; $("table").innerHTML = ""; return; }

  const vmax = Math.max(...vals), vmin = Math.min(...vals);
  let y, ticks;
  if (logy) {
    const a = Math.floor(Math.log10(vmin)), b = Math.ceil(Math.log10(vmax));
    ticks = []; for (let e = a; e <= b; e++) ticks.push(10 ** e);
    y = (v) => M.t + ph - ((Math.log10(Math.max(v, 10 ** a)) - a) / Math.max(b - a, 1)) * ph;
  } else {
    ticks = niceTicks(vmax);
    const top = ticks[ticks.length - 1];
    y = (v) => M.t + ph - (v / top) * ph;
  }
  for (const t of ticks) {
    svg += `<line class="grid" x1="${M.l}" x2="${M.l + pw}" y1="${y(t)}" y2="${y(t)}"/>
      <text class="dim" x="${M.l - 8}" y="${y(t) + 4}" text-anchor="end">${t >= 1000 || (t < 0.01 && t > 0) ? t.toExponential(0) : +t.toPrecision(3)}</text>`;
  }
  svg += `<text transform="translate(18 ${M.t + ph / 2}) rotate(-90)" text-anchor="middle">${unit}</text>`;
  svg += `<text x="${M.l + pw / 2}" y="${H - 12}" text-anchor="middle">Lattice Size (L)</text>`;

  const gw = pw / Ls.length, inner = gw * 0.86, bw = Math.min(inner / Math.max(series.length, 1), 60);
  const base = y(logy ? ticks[0] : 0);
  Ls.forEach((L, gi) => {
    const gx = M.l + gi * gw + gw / 2;
    svg += `<text x="${gx}" y="${M.t + ph + 22}" text-anchor="middle">L=${L}</text>`;
    const here = rows.filter((x) => x.L === L);
    here.forEach((x) => {
      const si = series.indexOf(x.k), bx = gx - (series.length * bw) / 2 + si * bw;
      if (x.r.error) {
        svg += `<text transform="translate(${bx + bw / 2 + 4} ${base - 6}) rotate(-90)" font-size="11" fill="${COLORS[x.k]}" style="fill:${COLORS[x.k]}">out of memory</text>`;
        svg += `<rect class="bar" x="${bx}" y="${base - 2}" width="${bw}" height="2" fill="${COLORS[x.k]}" data-i="${rows.indexOf(x)}"/>`;
        return;
      }
      const top = y(x.v), h = Math.max(base - top, 0);
      svg += `<rect class="bar" x="${bx}" y="${top}" width="${bw}" height="${h}" fill="${COLORS[x.k]}" data-i="${rows.indexOf(x)}"/>`;
      if (bw >= 42) // narrower bars would let neighbouring labels overlap; the table below has every value
        svg += `<text x="${bx + bw / 2}" y="${top - 4}" text-anchor="middle" font-size="${bw > 50 ? 11 : 9}">${fmtVal(x.v, metric).replace(" ms", "")}</text>`;
    });
  });
  svg += `<line x1="${M.l}" x2="${M.l + pw}" y1="${base}" y2="${base}" stroke="#777"/>`;
  series.forEach((k, i) => {
    const [p, d, n] = k.split(" ");
    svg += `<rect x="${W - M.r + 24}" y="${M.t + 6 + i * 20}" width="11" height="11" fill="${COLORS[k]}"/>
      <text x="${W - M.r + 42}" y="${M.t + 16 + i * 20}">${name(+p, d, +n)}</text>`;
  });
  svg += "</svg>";
  $("chart").innerHTML = svg;

  const tip = $("tip");
  $("chart").querySelectorAll("rect.bar").forEach((el) => {
    el.onmousemove = (e) => {
      const x = rows[+el.dataset.i], r = x.r, [p, d, n] = x.k.split(" ");
      tip.hidden = false;
      if (r.error) { tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 14 + "px"; tip.textContent = `${name(+p, d, +n)}   L=${x.L}\n${r.error} (single pass keeps every Krylov vector)`; return; }
      tip.style.left = e.clientX + 14 + "px"; tip.style.top = e.clientY + 14 + "px";
      tip.textContent = `${name(+p, d, +n)}   L=${x.L}\ndimension ${r.dim.toLocaleString()}\n` +
        `time ${fmtTime(r.solve_s_mean)} s ± ${fmtTime(r.solve_s_std)} (${r.runs} run${r.runs > 1 ? "s" : ""})\n` +
        `iterations ${r.iterations}   ${((r.solve_s_mean * 1000) / Math.max(r.iterations, 1)).toFixed(2)} ms/iter\nE0 ${r.energy.toFixed(8)}`;
    };
    el.onmouseleave = () => (tip.hidden = true);
  });

  // Table of exactly what is plotted.
  let t = `<tr><th>L</th><th>dim</th>${series.map((k) => { const [p, d, n] = k.split(" "); return `<th>${name(+p, d, +n)}</th>`; }).join("")}</tr>`;
  for (const L of Ls) {
    const dim = (ds.results.find((r) => r.L === L && r.dim) || {}).dim;
    t += `<tr><th>${L}</th><td>${dim ? dim.toLocaleString() : ""}</td>` +
      series.map((k) => { const x = rows.find((q) => q.L === L && q.k === k); return `<td>${x ? x.r.error ? "OOM" : fmtVal(x.v, metric) + (metric === "time" ? ` (${x.r.iterations} it)` : "") : "–"}</td>`; }).join("") + "</tr>";
  }
  $("table").innerHTML = t;
  state.rows = rows;
}

function download(filename, blob) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = filename; a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

$("csv") && ($("csv").onclick = () => {
  const ds = state.ds;
  const head = "machine,mode,L,dim,precision,device,passes,iterations,solve_s_mean,solve_s_std,runs,energy";
  const body = ds.results.map((r) => [ds.machine, ds.mode, r.L, r.dim, r.precision, r.device, r.passes, r.iterations,
    r.solve_s_mean ?? "", r.solve_s_std ?? "", r.runs ?? "", r.energy ?? r.error].join(","));
  download(`qkrylov_${ds.id}.csv`, new Blob([[head, ...body].join("\n")], { type: "text/csv" }));
});

$("png") && ($("png").onclick = () => {
  const svg = $("chart").querySelector("svg");
  const xml = new XMLSerializer().serializeToString(svg).replace(/<svg /, '<svg style="background:#181818;font-family:sans-serif" ')
    .replace(/<text /g, '<text fill="#e6e6e6" ').replace(/class="grid"/g, 'stroke="#333"');
  const img = new Image();
  img.onload = () => {
    const c = document.createElement("canvas"); c.width = 2400; c.height = 1240;
    const g = c.getContext("2d"); g.fillStyle = "#181818"; g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
    c.toBlob((b) => download("qkrylov_benchmark.png", b));
  };
  img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(xml);
});

buildControls();
selectDataset(DATA.datasets[0]);
