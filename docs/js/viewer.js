import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { BrainCloud, Wires, loadData, loadReplay } from "./brain.js";
import { Fly, flyStage } from "./fly.js";

const COLORS = { global: "#f5c542", japan: "#ff4d6d", korea: "#4dabff", control: "#9ecbff" };
const CHART_NAME = { global: "HOT 30", japan: "JAPAN", korea: "KOREA", control: "CONTROL" };
const METERS = [["legs", "walk", "381 leg MNs"], ["wings", "wings", "67 wing MNs"], ["abdomen", "abdomen", "214 abdominal MNs"],
  ["jump", "jump", "giant fiber → TTMn"], ["proboscis", "proboscis", "MN9/11/12"], ["haltere", "halteres", "16 haltere MNs"]];
const $ = (id) => document.getElementById(id);

const [data, replay, cmds] = await Promise.all([loadData(), loadReplay(), loadReplay("data/", "commands")]);
const CMD_COLOR = "#7ee0a1";
const AXES = [["love", "💘", "love"], ["flybuzz", "🪰", "fly buzz"], ["danger", "🐝", "danger"], ["startle", "⚡", "startle"], ["arousal", "🧠", "arousal"]];
const songs = data.meta.songs;
const replayIdx = Object.fromEntries(replay.meta.segments.map((s, i) => [s.id, i]));

// --- brain -----------------------------------------------------------------
const bCanvas = $("brain");
const bRenderer = new THREE.WebGLRenderer({ canvas: bCanvas, antialias: true });
bRenderer.setPixelRatio(Math.min(devicePixelRatio, 2));
const bScene = new THREE.Scene();
bScene.background = new THREE.Color(0x07080d);
const bCam = new THREE.PerspectiveCamera(35, 1, 0.01, 50);
bCam.position.set(2.9, 1.9, 3.1);
const baseDist = bCam.position.length();
const controls = new OrbitControls(bCam, bCanvas);
controls.enableDamping = true;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.6;
const brain = new BrainCloud(data.somata, data.region, data.meta.scale);
bScene.add(brain.points);
// connections: a faint backbone of the strongest synapses + the pathway active for the current song / command
const somaPos = brain.points.geometry.attributes.position.array;
const backbone = new Wires(somaPos, 0x5a6aa0, 0.16, 0);
backbone.set(data.backbone);
const active = new Wires(somaPos, 0x4dabff, 0.32, 1.0);
bScene.add(backbone.lines, active.lines);

// sound: Apple's official 30 s previews are streamed from Apple (never hosted here); controls are our own synth
const player = $("player");
let soundOn = false;

// region label anchors (centroids)
const anchors = {};
{
  const sum = {}, pos = brain.points.geometry.attributes.position.array;
  for (let i = 0; i < data.region.length; i++) {
    let r = String(data.region[i]);
    if (r === "3") continue;
    if (r === "1") r = pos[i * 3 + 2] > 0 ? "1a" : "1b";
    const s = (sum[r] ||= [0, 0, 0, 0]);
    s[0] += pos[i * 3]; s[1] += pos[i * 3 + 1]; s[2] += pos[i * 3 + 2]; s[3]++;
  }
  for (const [r, s] of Object.entries(sum)) anchors[r] = new THREE.Vector3(s[0] / s[3], s[1] / s[3] + (r === "2" ? -0.25 : 0.32), s[2] / s[3]);
}

// --- fly -------------------------------------------------------------------
const fCanvas = $("fly");
const fRenderer = new THREE.WebGLRenderer({ canvas: fCanvas, antialias: true });
fRenderer.setPixelRatio(Math.min(devicePixelRatio, 2));
fRenderer.shadowMap.enabled = true;
fRenderer.shadowMap.type = THREE.PCFSoftShadowMap;
fRenderer.toneMapping = THREE.NoToneMapping;
const { scene: fScene, grid } = flyStage(fRenderer);
fScene.background = new THREE.Color(0x0b0e16);
fScene.fog = new THREE.Fog(0x0b0e16, 5, 11);
const fly = new Fly();
fScene.add(fly.group);
const fCam = new THREE.PerspectiveCamera(32, 1, 0.01, 50);

function resize() {
  const b = bCanvas.parentElement.getBoundingClientRect();
  bRenderer.setSize(b.width, b.height, false);
  bCam.aspect = b.width / b.height;
  bCam.updateProjectionMatrix();
  bCam.position.setLength(baseDist * Math.max(1, 1.05 / bCam.aspect ** 0.8));   // portrait screens: step back so the whole CNS fits
  brain.uniforms.uPix.value = b.height * bRenderer.getPixelRatio();
  const f = fCanvas.getBoundingClientRect();
  fRenderer.setSize(f.width, f.height, false);
  fCam.aspect = f.width / f.height;
  fCam.updateProjectionMatrix();
}
addEventListener("resize", resize);

// --- UI --------------------------------------------------------------------
let current = null, mode = "avg", rp = null;
const tabs = ["all", "global", "japan", "korea", "control", "commands"];
let cmd = null;
let tab = "all";
function renderTabs() {
  $("tabs").innerHTML = tabs.map((t) => `<button class="${t === tab ? "on" : ""}" data-t="${t}">${t === "all" ? "ALL-TIME" : t === "commands" ? "🧪 COMMANDS" : CHART_NAME[t]}</button>`).join("");
  $("tabs").querySelectorAll("button").forEach((b) => b.onclick = () => { tab = b.dataset.t; renderTabs(); renderList(); });
}
function renderList() {
  if (tab === "commands") {
    $("list").innerHTML = cmds.meta.segments.map((c, i) => `
      <div class="song ${cmd && cmd.k === i ? "on" : ""}" data-k="${i}">
        <div class="rk" style="font-size:24px">${c.emoji}</div><div></div>
        <div><div class="t">${esc(c.label)}</div><div class="a">${esc(c.what)}</div></div><div></div>
      </div>`).join("");
    $("list").querySelectorAll(".song").forEach((el) => el.onclick = () => {
      startCommand(+el.dataset.k);
      if (innerWidth <= 1100) scrollTo({ top: 0, behavior: "smooth" });
    });
    return;
  }
  let rows = songs.filter((s) => tab === "all" ? s.chart !== "control" : s.chart === tab);
  rows = rows.sort((a, b) => b.score - a.score);
  $("list").innerHTML = rows.map((s, i) => `
    <div class="song ${current && current.id === s.id ? "on" : ""}" data-id="${s.id}">
      <div class="rk">${s.chart === "control" ? "–" : tab === "all" ? s.overall : s.rank}</div>
      <img src="${s.cover}" loading="lazy" alt="">
      <div><div class="t">${esc(s.title)}</div><div class="a">${esc(s.artist)}${tab === "all" ? " · " + CHART_NAME[s.chart] : ""}${s.id in replayIdx ? ' <span class="rp">● replay</span>' : ""}</div></div>
      <div class="s" style="color:${COLORS[s.chart]}">${s.score.toFixed(1)}</div>
    </div>`).join("");
  $("list").querySelectorAll(".song").forEach((el) => el.onclick = () => {
    select(el.dataset.id);
    if (innerWidth <= 1100) scrollTo({ top: 0, behavior: "smooth" });   // phones: jump back up to the brain
  });
}
const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

$("meters").innerHTML = METERS.map(([k, n, src]) => `<div class="meter"><div class="n">${n.toUpperCase()}</div><div class="bar"><i id="m-${k}"></i></div><div class="src">${src}</div></div>`).join("");

function select(id, startReplay = false) {
  current = songs.find((s) => s.id === id);
  const color = COLORS[current.chart];
  document.documentElement.style.setProperty("--acc", color);
  brain.setColor(color);
  fly.setAccent(color);
  const d = data.song(current);
  brain.setSong(d.idx, d.rate, d.fp);
  active.uniforms.uColor.value.set(color);
  active.uniforms.uReplay.value = 0;
  active.set(data.edges(current));
  mode = "avg";
  rp = null;
  cmd = null;
  const fly_ref = songs.find((s) => s.id === "ctrl_flysong").score;
  $("info").innerHTML = `
    <div class="kicker">${current.chart === "control" ? "CONTROL" : `#${current.rank} IN ${CHART_NAME[current.chart]}`}</div>
    <div class="title">${esc(current.title)}</div><div class="artist">${esc(current.artist)}</div>
    <div class="score"><b>${current.score.toFixed(1)}</b><span>FLY SCORE ± ${current.spread.toFixed(1)}<br>0 = white noise · 100 = brain's response to fly love song</span></div>
    <div class="scale"><i style="width:${Math.max(0, current.score)}%"></i><em style="left:${fly_ref}%">fly song</em></div>
    <div class="stats"><div><b>${current.lit}</b>neurons lit</div><div><b>${current.gf} Hz</b>giant fiber</div><div><b>${current.n}</b>active somata</div></div>
    <div class="eq" id="eq">${"<i></i>".repeat(28)}</div>
    ${current.listen ? `<a class="listen" href="${current.listen}" target="_blank" rel="noopener">Listen on Apple Music ↗</a>
      <div class="credit">Preview courtesy of Apple Music, streamed from Apple.</div>` : ""}
    ${radar(current)}`;
  $("replay").disabled = !(id in replayIdx);
  $("hud").innerHTML = `<b>${esc(current.title)}</b> · ${current.n.toLocaleString()} neurons active<br>each dot = one neuron at its real position · lines = its ${active.pre.length.toLocaleString()} strongest active connections`;
  renderList();
  if (startReplay) startReplayMode();
  else playSound();
}

function playSound() {
  // plays the selected song's preview (from the replay window's start in replay mode); silent in command mode
  if (!soundOn || mode === "command" || !current.preview) { player.pause(); return; }
  if (player.dataset.id !== current.id) {
    player.src = current.preview;
    player.dataset.id = current.id;
  }
  player.loop = mode !== "replay";
  if (mode === "replay") player.currentTime = replay.meta.segments[rp.seg].t0;
  else if (player.currentTime > 29) player.currentTime = 0;
  player.play().catch(() => {});
}

$("sound").onclick = () => {
  soundOn = !soundOn;
  $("sound").textContent = soundOn ? "🔊 Sound on" : "🔇 Sound off";
  if (soundOn && !current.preview) toast("No preview available for this track");
  playSound();
};
$("wire").onclick = () => {
  backbone.lines.visible = active.lines.visible = !active.lines.visible;
  $("wire").textContent = active.lines.visible ? "🕸 Wiring on" : "🕸 Wiring off";
};

function radar(s) {
  // five axes as percentiles among the 84 songs
  if (!s.axes) return "";
  const R = 58, cx = 130, cy = 88, n = AXES.length;
  const pt = (i, r) => [cx + r * Math.sin(2 * Math.PI * i / n), cy - r * Math.cos(2 * Math.PI * i / n)];
  const ring = (f) => AXES.map((_, i) => pt(i, R * f).join(",")).join(" ");
  const poly = AXES.map(([k], i) => pt(i, R * Math.max(0.04, s.axes[k][0] / 100)).join(",")).join(" ");
  const labels = AXES.map(([k, e, name], i) => {
    const [x, y] = pt(i, R + 17);
    return `<text x="${x}" y="${y}" text-anchor="middle" dominant-baseline="middle" font-size="8.5" fill="#aab3cc">${e} ${name} ${Math.round(s.axes[AXES[i][0]][0])}</text>`;
  }).join("");
  return `<div class="radar"><svg viewBox="0 0 260 176" width="100%">
      ${[0.25, 0.5, 0.75, 1].map((f) => `<polygon points="${ring(f)}" fill="none" stroke="#252b3c"/>`).join("")}
      ${AXES.map((_, i) => `<line x1="${cx}" y1="${cy}" x2="${pt(i, R)[0]}" y2="${pt(i, R)[1]}" stroke="#252b3c"/>`).join("")}
      <polygon points="${poly}" fill="var(--acc)" fill-opacity=".35" stroke="var(--acc)" stroke-width="1.5"/>${labels}</svg>
    <div class="rnote">percentile among the 84 songs. 💘 love, 🐝 danger and ⚡ startle move together (ρ ≈ 0.9):
      this simulated fly can barely tell a courting male from a wasp.</div></div>`;
}

function startCommand(k) {
  const c = cmds.meta.segments[k];
  cmd = { k, f: 0, acc: 0, toasted: false };
  mode = "command";
  rp = null;
  document.documentElement.style.setProperty("--acc", CMD_COLOR);
  brain.setColor(CMD_COLOR);
  fly.setAccent(CMD_COLOR);
  brain.clearGlow();
  active.uniforms.uColor.value.set(CMD_COLOR);
  active.uniforms.uReplay.value = 1;
  active.set(data.edges(c));
  player.pause();
  const peaks = Object.entries(c.peak_hz).sort((a, b) => b[1] - a[1]).slice(0, 6)
    .map(([ch, hz]) => `<div><b>${hz} Hz</b>${ch}</div>`).join("");
  $("info").innerHTML = `
    <div class="kicker">COMMAND · optogenetics-style</div>
    <div class="title">${c.emoji} ${esc(c.label)}</div><div class="artist">${esc(c.what)}</div>
    <div class="note" style="margin-top:10px">Switches on ${c.n_neurons} neuron${c.n_neurons > 1 ? "s" : ""} with Poisson input for 2 s
      (t = ${c.on[0]}–${c.on[1]} s) and replays the exact spikes of the whole CNS. Peak motor neuron firing:</div>
    <div class="stats" style="flex-wrap:wrap">${peaks}</div>`;
  $("hud").innerHTML = `<b>${c.emoji} ${esc(c.label)}</b> · command mode<br>real spikes of one simulated run`;
  $("replay").disabled = true;
  renderList();
}

function startReplayMode() {
  if (!(current.id in replayIdx)) return;
  rp = { seg: replayIdx[current.id], f: 0, acc: 0 };
  brain.clearGlow();
  mode = "replay";
  active.uniforms.uReplay.value = 1;
  playSound();
}
$("replay").onclick = startReplayMode;
$("avg").onclick = () => select(current.id);   // back to the average blink of the selected song (also leaves command mode)

// --- loop ------------------------------------------------------------------
const clock = new THREE.Clock();
let t = 0;
function bodyChannels() {
  if (mode === "command" && cmd) {
    const c = cmds.meta.segments[cmd.k];
    const ch = {};
    for (const [k, v] of Object.entries(c.body)) ch[k] = v[cmd.f];
    ch.legs = ["Lfl", "Rfl", "Lml", "Rml", "Lhl", "Rhl"].reduce((a, k) => a + (ch[k] || 0), 0) / 6;
    ch.wings = ((ch.wingL || 0) + (ch.wingR || 0)) / 2;
    ch.ear = 0;
    ch.love = 0;
    return ch;
  }
  if (mode === "replay" && rp) {
    const seg = replay.meta.segments[rp.seg];
    const ch = {};
    for (const [k, v] of Object.entries(seg.body)) ch[k] = v[rp.f];
    ch.legs = ["Lfl", "Rfl", "Lml", "Rml", "Lhl", "Rhl"].reduce((a, k) => a + (ch[k] || 0), 0) / 6;
    ch.wings = ((ch.wingL || 0) + (ch.wingR || 0)) / 2;
    ch.ear = Math.min(1, 1.6 * (ch.ear || 0));
    ch.love = Math.max(0, current.score / 100);
    return ch;
  }
  const b = current.body, ring = current.ring;
  const r = ring[Math.floor(ringPos()) % ring.length];
  return { ...b, wingL: b.wings, wingR: b.wings, ear: Math.min(1, 1.6 * (r[0] + r[1]) / 2), love: Math.max(0, current.score / 100) };
}
const playing = () => soundOn && !player.paused && player.readyState >= 2;
const ringPos = () => (playing() && mode === "avg" ? player.currentTime : t) * 4;   // ear envelope follows the audio when it plays

function stepReplay(seg) {
  brain.setSpikes(replay.frame(rp.seg, rp.f));
  const fs = replay.meta.frame_ms / 1000, before = seg.t0 + rp.f * fs;
  if (seg.latch_s && before < seg.latch_s && before + fs >= seg.latch_s) toast("⚡ Motor latch ON: the abdomen and flight motor just switched on");
  rp.f = (rp.f + 1) % seg.frames.length;
  if (rp.f === 0) brain.clearGlow();
}

function tick() {
  const dt = Math.min(0.05, clock.getDelta());
  t += dt;
  brain.uniforms.uTime.value = t;
  backbone.uniforms.uTime.value = active.uniforms.uTime.value = t;
  if (mode === "replay" && rp) {
    const seg = replay.meta.segments[rp.seg], fs = replay.meta.frame_ms / 1000;
    if (playing()) {
      // lock the spikes to the audio clock: the simulated listen started at t0 of this very preview
      const target = Math.floor((player.currentTime - seg.t0) / fs);
      if (target < 0 || target >= seg.frames.length) {
        player.currentTime = seg.t0;
        rp.f = 0;
        brain.clearGlow();
      } else {
        let guard = 0;
        while (rp.f < target && guard++ < 10) stepReplay(seg);
      }
    } else {
      rp.acc += dt;
      while (rp.acc >= fs) { rp.acc -= fs; stepReplay(seg); }
    }
    active.follow(brain.glow.array);
    const tt = seg.t0 + rp.f * replay.meta.frame_ms / 1000;
    $("clock").textContent = `replay · listen t = ${tt.toFixed(1)} s${seg.latch_s ? ` · motor latch at ${seg.latch_s.toFixed(1)} s` : ""}`;
    $("hud").innerHTML = `<b>${esc(current.title)}</b> · real spikes, one simulated listen<br>${replay.frame(rp.seg, rp.f).length} neurons firing in this 40 ms frame`;
  } else if (mode === "command" && cmd) {
    const c = cmds.meta.segments[cmd.k], fs = cmds.meta.frame_ms / 1000;
    cmd.acc += dt;
    while (cmd.acc >= fs) {
      cmd.acc -= fs;
      brain.setSpikes(cmds.frame(cmd.k, cmd.f));
      cmd.f = (cmd.f + 1) % c.frames.length;
      if (cmd.f === 0) { brain.clearGlow(); cmd.toasted = false; }
    }
    active.follow(brain.glow.array);
    const tt = cmd.f * fs, on = tt >= c.on[0] && tt < c.on[1];
    if (on && !cmd.toasted) { toast(`🧪 ${c.label}: switching ON ${c.n_neurons} neuron${c.n_neurons > 1 ? "s" : ""}`); cmd.toasted = true; }
    $("clock").textContent = `command · t = ${tt.toFixed(1)} s · ${on ? "ON" : "off"}`;
  } else {
    $("clock").textContent = "";
  }
  const ch = bodyChannels();
  fly.update(dt, ch, mode === "command" && cmd ? cmds.meta.segments[cmd.k].style : null);
  grid.position.x = -(fly.scroll % (12 / 36));
  for (const [k] of METERS) $("m-" + k).style.width = `${Math.round(100 * (ch[k] ?? 0))}%`;
  $("mood").textContent = mood(ch);
  const eq = $("eq");
  if (eq) {
    const ring = current.ring, pos = ringPos() % ring.length;
    [...eq.children].forEach((bar, i) => {
      const r = ring[Math.floor(pos + i) % ring.length], wob = 0.75 + 0.25 * Math.sin(t * 9 + i * 1.3);
      bar.style.height = `${Math.round(4 + 34 * Math.min(1, 1.3 * (r[0] + r[1]) * wob))}px`;
    });
  }
  const a = 0.42 + 0.3 * Math.sin(t * 0.25);
  fCam.position.set(0.2 + 5.6 * Math.cos(a), 2.1, 5.6 * Math.sin(a));
  fCam.lookAt(0.1, 0.15, 0);

  controls.update();
  bRenderer.render(bScene, bCam);
  fRenderer.render(fScene, fCam);
  const rect = bCanvas.getBoundingClientRect();
  document.querySelectorAll(".label").forEach((el) => {
    const p = anchors[el.dataset.r].clone().project(bCam);
    el.style.left = `${(p.x + 1) / 2 * rect.width}px`;
    el.style.top = `${(1 - p.y) / 2 * rect.height}px`;
    el.style.opacity = p.z < 1 ? 1 : 0;
  });
  requestAnimationFrame(tick);
}

function mood(ch) {
  // one-line reading of the body channels (and the score) for humans
  if (mode === "command" && cmd) {
    const c = cmds.meta.segments[cmd.k];
    return { hop: "🦘 escape!", backward: "🔙 moonwalking", sing: "🎵 singing (one wing out)", groom: "🧼 grooming its head",
      walk: "🚶 P9 on", feed: "👅 proboscis out" }[c.style] || c.label;
  }
  if ((ch.love || 0) > 0.8) return "💘 in love: this is what fly courtship sounds like";
  if ((ch.abdomen || 0) > 0.35 || (ch.wings || 0) > 0.35) return "😖 flinching: abdomen + flight motor switched on";
  if ((ch.jump || 0) > 0.5) return "⚡ jumpy: giant fiber firing";
  return "🎧 listening";
}

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.add("on");
  clearTimeout(toast.h);
  toast.h = setTimeout(() => el.classList.remove("on"), 2600);
}

renderTabs();
const q = new URLSearchParams(location.search);
select(q.get("song") || [...songs].filter((s) => s.chart !== "control").sort((a, b) => b.score - a.score)[0].id, q.has("replay"));
if (q.has("cmd")) {
  const k = cmds.meta.segments.findIndex((c) => c.id === q.get("cmd"));
  if (k >= 0) { tab = "commands"; renderTabs(); startCommand(k); }
}
resize();
$("loading").remove();
tick();
