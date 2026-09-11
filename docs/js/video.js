// Deterministic frame renderer for the countdown video. The capture script calls renderAt(0), renderAt(1), ...
// in order and screenshots each frame (25 fps).
import * as THREE from "three";
import { BrainCloud, loadData, loadReplay } from "./brain.js";
import { Fly, flyStage } from "./fly.js";

const FPS = 25, CARD = 3 * FPS;
const COLORS = { global: "#f5c542", japan: "#ff4d6d", korea: "#4dabff", control: "#9ecbff" };
const METERS = [["legs", "walk", "leg MNs"], ["wings", "wings", "wing MNs"], ["abdomen", "abdomen", "abdominal MNs"],
  ["jump", "jump", "giant fiber → TTMn"], ["proboscis", "proboscis", "MN9/11/12"], ["ear", "ear", "Johnston's organ"]];
const $ = (id) => document.getElementById(id);

const [data, replay] = await Promise.all([loadData(), loadReplay()]);
const segs = replay.meta.segments;
const segLen = segs[0].frames.length;
const total = CARD + segs.length * segLen + CARD;

const bR = new THREE.WebGLRenderer({ canvas: $("brain"), antialias: true, preserveDrawingBuffer: true });
bR.setSize(820, 960, false);
const bScene = new THREE.Scene();
bScene.background = new THREE.Color(0x07080d);
const bCam = new THREE.PerspectiveCamera(33, 820 / 960, 0.01, 50);
const brain = new BrainCloud(data.somata, data.region, data.meta.scale);
brain.uniforms.uPix.value = 960;
brain.uniforms.uSize.value = 0.011;
bScene.add(brain.points);

const fR = new THREE.WebGLRenderer({ canvas: $("fly"), antialias: true, preserveDrawingBuffer: true });
fR.setSize(560, 520, false);
fR.shadowMap.enabled = true;
fR.shadowMap.type = THREE.PCFSoftShadowMap;
fR.toneMapping = THREE.NoToneMapping;
const { scene: fScene, grid } = flyStage(fR);
fScene.background = new THREE.Color(0x07080d);
fScene.fog = new THREE.Fog(0x07080d, 5, 11);
const fCam = new THREE.PerspectiveCamera(30, 560 / 520, 0.01, 50);
let fly = new Fly();
fScene.add(fly.group);

$("meters").innerHTML = METERS.map(([k, n, s]) => `<div class="meter"><b>${n.toUpperCase()}</b><div class="bar"><i id="m-${k}"></i></div><span>${s}</span></div>`).join("");

function view(t) {
  const yaw = 0.75 + 0.5 * Math.sin(2 * Math.PI * t / 14);
  bCam.position.set(4.4 * Math.cos(yaw), 1.8, 4.4 * Math.sin(yaw));
  bCam.lookAt(0, -0.08, 0);
  const fy = 0.42 + 0.3 * Math.sin(2 * Math.PI * t / 14);   // keep the face toward the camera
  fCam.position.set(0.1 + 7.0 * Math.cos(fy), 2.5, 7.0 * Math.sin(fy));
  fCam.lookAt(0.05, 0.05, 0);
}

function card(html) {
  $("seg").style.display = "none";
  $("fly").style.display = "none";
  $("card").style.display = "flex";
  $("card").innerHTML = html;
  $("brain").style.left = "1040px";
}

let lastSeg = -1;
window.renderAt = (i) => {
  const t = i / FPS;
  brain.uniforms.uTime.value = t;
  view(t);
  if (i < CARD || i >= total - CARD) {
    brain.setColor("#c77dff");
    brain.uniforms.uMode.value = 1;
    brain.clearGlow();
    card(i < CARD
      ? `<h1>🪰 FLYBOARD</h1><p>We played 84 songs to a simulated fruit fly.</p><small>Every neuron of its brain and nerve cord. Every twitch of its body.</small>`
      : `<h1>🪰 FLYBOARD</h1><p>Full charts · HOT 30 · JAPAN · KOREA</p><small class="url">sukoji.github.io/flyboard</small>`);
    bR.render(bScene, bCam);
    return;
  }
  $("seg").style.display = "block";
  $("fly").style.display = "block";
  $("card").style.display = "none";
  $("brain").style.left = "520px";
  const k = Math.floor((i - CARD) / segLen), f = (i - CARD) % segLen;
  const s = segs[k];
  if (k !== lastSeg) {
    lastSeg = k;
    const color = COLORS[s.chart];
    document.documentElement.style.setProperty("--acc", color);
    brain.setColor(color);
    brain.clearGlow();
    fScene.remove(fly.group);
    fly = new Fly();
    fly.setAccent(color);
    fScene.add(fly.group);
    $("kicker").textContent = s.kicker;
    $("title").textContent = s.title;
    $("artist").textContent = s.artist;
    $("cover").src = `covers/${s.id}.png`;
    $("ref").style.left = `${replay.meta.fly_ref * 4.2}px`;
  }
  const spikes = replay.frame(k, f);
  brain.setSpikes(spikes);
  const prog = Math.min(1, f / (0.6 * segLen));
  const shown = s.score * (1 - (1 - prog) ** 3);
  $("score").textContent = shown.toFixed(1);
  $("bar").style.width = `${Math.max(0, shown) * 4.2}px`;
  const tt = s.t0 + f * replay.meta.frame_ms / 1000;
  $("clock").textContent = `listening t = ${tt.toFixed(1)} s` + (s.latch_s && tt >= s.latch_s ? "  ·  motor latch ON" : "");
  $("firing").textContent = `${spikes.length} neurons firing in this 40 ms frame`;

  const ch = {};
  for (const [key, v] of Object.entries(s.body)) ch[key] = v[f];
  ch.legs = ["Lfl", "Rfl", "Lml", "Rml", "Lhl", "Rhl"].reduce((a, x) => a + (ch[x] || 0), 0) / 6;
  ch.wings = ((ch.wingL || 0) + (ch.wingR || 0)) / 2;
  ch.ear = Math.min(1, 1.6 * (ch.ear || 0));
  ch.love = Math.max(0, s.score / 100);
  fly.update(1 / FPS, ch);
  $("mood").textContent = ch.love > 0.8 ? "💘 in love" : (ch.abdomen > 0.35 || ch.wings > 0.35) ? "😖 flinching" : ch.jump > 0.5 ? "⚡ jumpy" : "🎧 listening";
  grid.position.x = -(fly.scroll % (12 / 36));
  for (const [key] of METERS) $("m-" + key).style.width = `${Math.round(100 * (ch[key] || 0))}%`;
  bR.render(bScene, bCam);
  fR.render(fScene, fCam);
};
window.totalFrames = total;
window.ready = true;
