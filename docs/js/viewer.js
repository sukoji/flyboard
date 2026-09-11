import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { BrainCloud, loadData, loadReplay } from "./brain.js";
import { Fly, flyStage } from "./fly.js";

const COLORS = { global: "#f5c542", japan: "#ff4d6d", korea: "#4dabff", control: "#9ecbff" };
const CHART_NAME = { global: "HOT 30", japan: "JAPAN", korea: "KOREA", control: "CONTROL" };
const METERS = [["legs", "walk", "381 leg MNs"], ["wings", "wings", "67 wing MNs"], ["abdomen", "abdomen", "214 abdominal MNs"],
  ["jump", "jump", "giant fiber → TTMn"], ["proboscis", "proboscis", "MN9/11/12"], ["haltere", "halteres", "16 haltere MNs"]];
const $ = (id) => document.getElementById(id);

const [data, replay] = await Promise.all([loadData(), loadReplay()]);
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
const controls = new OrbitControls(bCam, bCanvas);
controls.enableDamping = true;
controls.autoRotate = true;
controls.autoRotateSpeed = 0.6;
const brain = new BrainCloud(data.somata, data.region, data.meta.scale);
bScene.add(brain.points);

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
fRenderer.toneMapping = THREE.ACESFilmicToneMapping;
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
  brain.uniforms.uPix.value = b.height * bRenderer.getPixelRatio();
  const f = fCanvas.getBoundingClientRect();
  fRenderer.setSize(f.width, f.height, false);
  fCam.aspect = f.width / f.height;
  fCam.updateProjectionMatrix();
}
addEventListener("resize", resize);

// --- UI --------------------------------------------------------------------
let current = null, mode = "avg", rp = null;
const tabs = ["all", "global", "japan", "korea", "control"];
let tab = "all";
function renderTabs() {
  $("tabs").innerHTML = tabs.map((t) => `<button class="${t === tab ? "on" : ""}" data-t="${t}">${t === "all" ? "ALL-TIME" : CHART_NAME[t]}</button>`).join("");
  $("tabs").querySelectorAll("button").forEach((b) => b.onclick = () => { tab = b.dataset.t; renderTabs(); renderList(); });
}
function renderList() {
  let rows = songs.filter((s) => tab === "all" ? s.chart !== "control" : s.chart === tab);
  rows = rows.sort((a, b) => b.score - a.score);
  $("list").innerHTML = rows.map((s, i) => `
    <div class="song ${current && current.id === s.id ? "on" : ""}" data-id="${s.id}">
      <div class="rk">${s.chart === "control" ? "–" : tab === "all" ? s.overall : s.rank}</div>
      <img src="${s.cover}" loading="lazy" alt="">
      <div><div class="t">${esc(s.title)}</div><div class="a">${esc(s.artist)}${tab === "all" ? " · " + CHART_NAME[s.chart] : ""}${s.id in replayIdx ? ' <span class="rp">● replay</span>' : ""}</div></div>
      <div class="s" style="color:${COLORS[s.chart]}">${s.score.toFixed(1)}</div>
    </div>`).join("");
  $("list").querySelectorAll(".song").forEach((el) => el.onclick = () => select(el.dataset.id));
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
  mode = "avg";
  rp = null;
  const fly_ref = songs.find((s) => s.id === "ctrl_flysong").score;
  $("info").innerHTML = `
    <div class="kicker">${current.chart === "control" ? "CONTROL" : `#${current.rank} IN ${CHART_NAME[current.chart]}`}</div>
    <div class="title">${esc(current.title)}</div><div class="artist">${esc(current.artist)}</div>
    <div class="score"><b>${current.score.toFixed(1)}</b><span>FLY SCORE ± ${current.spread.toFixed(1)}<br>0 = white noise · 100 = brain's response to fly love song</span></div>
    <div class="scale"><i style="width:${Math.max(0, current.score)}%"></i><em style="left:${fly_ref}%">fly song</em></div>
    <div class="stats"><div><b>${current.lit}</b>neurons lit</div><div><b>${current.gf} Hz</b>giant fiber</div><div><b>${current.n}</b>active somata</div></div>
    <div class="eq" id="eq">${"<i></i>".repeat(28)}</div>
    ${current.listen ? `<a class="listen" href="${current.listen}" target="_blank" rel="noopener">Listen on Apple Music ↗</a>` : ""}`;
  $("replay").disabled = !(id in replayIdx);
  $("hud").innerHTML = `<b>${esc(current.title)}</b> · ${current.n.toLocaleString()} neurons active<br>each dot = one neuron at its real position · lit = driven by this song`;
  renderList();
  if (startReplay) startReplayMode();
}

function startReplayMode() {
  if (!(current.id in replayIdx)) return;
  rp = { seg: replayIdx[current.id], f: 0, acc: 0 };
  brain.clearGlow();
  mode = "replay";
}
$("replay").onclick = startReplayMode;
$("avg").onclick = () => { mode = "avg"; rp = null; brain.uniforms.uMode.value = 0; };

// --- loop ------------------------------------------------------------------
const clock = new THREE.Clock();
let t = 0;
function bodyChannels() {
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
  const r = ring[Math.floor((t * 4) % ring.length)];
  return { ...b, wingL: b.wings, wingR: b.wings, ear: Math.min(1, 1.6 * (r[0] + r[1]) / 2), love: Math.max(0, current.score / 100) };
}
function tick() {
  const dt = Math.min(0.05, clock.getDelta());
  t += dt;
  brain.uniforms.uTime.value = t;
  if (mode === "replay" && rp) {
    rp.acc += dt;
    const seg = replay.meta.segments[rp.seg];
    while (rp.acc >= replay.meta.frame_ms / 1000) {
      rp.acc -= replay.meta.frame_ms / 1000;
      brain.setSpikes(replay.frame(rp.seg, rp.f));
      const before = seg.t0 + rp.f * replay.meta.frame_ms / 1000;
      if (seg.latch_s && before < seg.latch_s && before + replay.meta.frame_ms / 1000 >= seg.latch_s) toast("⚡ Motor latch ON: the abdomen and flight motor just switched on");
      rp.f = (rp.f + 1) % seg.frames.length;
      if (rp.f === 0) brain.clearGlow();
    }
    const tt = seg.t0 + rp.f * replay.meta.frame_ms / 1000;
    $("clock").textContent = `replay · listen t = ${tt.toFixed(1)} s${seg.latch_s ? ` · motor latch at ${seg.latch_s.toFixed(1)} s` : ""}`;
    $("hud").innerHTML = `<b>${esc(current.title)}</b> · real spikes, one simulated listen<br>${replay.frame(rp.seg, rp.f).length} neurons firing in this 40 ms frame`;
  } else {
    $("clock").textContent = "";
  }
  const ch = bodyChannels();
  fly.update(dt, ch);
  grid.position.x = -(fly.scroll % (12 / 36));
  for (const [k] of METERS) $("m-" + k).style.width = `${Math.round(100 * (ch[k] ?? 0))}%`;
  $("mood").textContent = mood(ch);
  const eq = $("eq");
  if (eq) {
    const ring = current.ring, pos = (t * 4) % ring.length;
    [...eq.children].forEach((bar, i) => {
      const r = ring[Math.floor(pos + i) % ring.length], wob = 0.75 + 0.25 * Math.sin(t * 9 + i * 1.3);
      bar.style.height = `${Math.round(4 + 34 * Math.min(1, 1.3 * (r[0] + r[1]) * wob))}px`;
    });
  }
  const a = 0.6 + 0.5 * Math.sin(t * 0.25);
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
resize();
$("loading").remove();
tick();
