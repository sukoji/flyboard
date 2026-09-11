// The male fly's whole CNS as a point cloud: 140k somata at their real positions (brain in front,
// nerve cord trailing behind and below, same orientation as the fly model).
// Two ways to light it up:
//   setSong(indices, rate, fingerprint)  every active neuron blinks at the mean rate it fired for that song
//   setSpikes(indices)                  exact spikes of one 40 ms frame of a recorded listen (with afterglow)
import * as THREE from "three";

const VERT = /* glsl */ `
  attribute float region;
  attribute float rate;      // 0..1  (log firing rate) for song mode
  attribute float fp;        // -1..1 fingerprint vs the average song
  attribute float glow;      // 0..n  afterglow for replay mode
  attribute float seed;
  uniform float uTime, uSize, uMode, uPix;
  varying vec3 vColor;
  varying float vA;
  uniform vec3 uColor, uHot;
  float hash(float n) { return fract(sin(n) * 43758.5453123); }
  void main() {
    vec4 mv = modelViewMatrix * vec4(position, 1.0);
    gl_Position = projectionMatrix * mv;
    vec3 dust = region < 0.5 ? vec3(0.42, 0.47, 0.62) : region < 1.5 ? vec3(0.38, 0.36, 0.58) : region < 2.5 ? vec3(0.32, 0.5, 0.55) : vec3(0.4);
    float act = 0.0;
    if (uMode < 0.5) {
      // Poisson-looking blink: in each 60 ms bin a neuron flashes with probability ~ its rate
      float bin = floor(uTime * 16.0 + seed * 7.0);
      float p = clamp(rate * rate * 0.9, 0.0, 0.95);
      float flash = step(hash(seed * 91.7 + bin), p);
      float sub = fract(uTime * 16.0 + seed * 7.0);
      act = rate > 0.0 ? (0.35 * rate + flash * (1.0 - sub) * 1.4) : 0.0;
    } else {
      act = min(glow, 4.0) * 0.45;
    }
    vec3 hot = mix(uColor, uHot, clamp(fp, 0.0, 1.0));
    vColor = act > 0.0 ? hot * (0.6 + act) : dust * 0.8;
    vA = act > 0.0 ? clamp(0.35 + act, 0.0, 1.0) : 0.42;
    float s = act > 0.0 ? uSize * (1.4 + 2.6 * act) : uSize * 0.7;
    gl_PointSize = s * uPix / -mv.z;
  }`;

const FRAG = /* glsl */ `
  varying vec3 vColor;
  varying float vA;
  void main() {
    vec2 c = gl_PointCoord - 0.5;
    float d = length(c);
    if (d > 0.5) discard;
    float core = smoothstep(0.5, 0.0, d);
    gl_FragColor = vec4(vColor * (0.6 + 0.8 * core * core), vA * core);
  }`;

export class BrainCloud {
  constructor(somata, region, scale) {
    const n = region.length;
    this.n = n;
    const pos = new Float32Array(n * 3);
    for (let i = 0; i < n * 3; i++) pos[i] = somata[i] / scale;
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    g.setAttribute("region", new THREE.BufferAttribute(Float32Array.from(region), 1));
    this.rate = new THREE.BufferAttribute(new Float32Array(n), 1);
    this.fp = new THREE.BufferAttribute(new Float32Array(n), 1);
    this.glow = new THREE.BufferAttribute(new Float32Array(n), 1);
    const seed = new Float32Array(n);
    for (let i = 0; i < n; i++) seed[i] = Math.random() * 100;
    g.setAttribute("rate", this.rate);
    g.setAttribute("fp", this.fp);
    g.setAttribute("glow", this.glow);
    g.setAttribute("seed", new THREE.BufferAttribute(seed, 1));
    this.uniforms = {
      uTime: { value: 0 }, uSize: { value: 0.012 }, uMode: { value: 0 }, uPix: { value: 800 },
      uColor: { value: new THREE.Color(0x4dabff) }, uHot: { value: new THREE.Color(0xffffff) },
    };
    this.points = new THREE.Points(g, new THREE.ShaderMaterial({
      vertexShader: VERT, fragmentShader: FRAG, uniforms: this.uniforms,
      transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
    }));
  }

  setColor(hex) { this.uniforms.uColor.value.set(hex); }

  setSong(idx, rate, fp) {
    this.uniforms.uMode.value = 0;
    this.rate.array.fill(0);
    this.fp.array.fill(0);
    for (let k = 0; k < idx.length; k++) {
      this.rate.array[idx[k]] = rate[k] / 255 * 1.6;
      this.fp.array[idx[k]] = (fp[k] - 128) / 100;
    }
    this.rate.needsUpdate = this.fp.needsUpdate = true;
  }

  clearGlow() { this.glow.array.fill(0); this.glow.needsUpdate = true; }

  setSpikes(idx, decay = 0.8) {
    this.uniforms.uMode.value = 1;
    const a = this.glow.array;
    for (let i = 0; i < a.length; i++) a[i] *= decay;
    for (let k = 0; k < idx.length; k++) a[idx[k]] += 1;
    this.glow.needsUpdate = true;
  }
}

export async function loadData(base = "data/") {
  const [meta, somata, region, rates] = await Promise.all([
    fetch(base + "songs.json").then((r) => r.json()),
    fetch(base + "somata.bin").then((r) => r.arrayBuffer()),
    fetch(base + "region.bin").then((r) => r.arrayBuffer()),
    fetch(base + "rates.bin").then((r) => r.arrayBuffer()),
  ]);
  const song = (s) => ({
    idx: new Uint32Array(rates, s.offset, s.n),
    rate: new Uint8Array(rates, s.offset + 4 * s.n, s.n),
    fp: new Uint8Array(rates, s.offset + 5 * s.n, s.n),
  });
  return { meta, somata: new Int16Array(somata), region: new Uint8Array(region), song };
}

export async function loadReplay(base = "data/", name = "replay") {
  const [meta, bin] = await Promise.all([
    fetch(base + name + ".json").then((r) => r.json()),
    fetch(base + name + ".bin").then((r) => r.arrayBuffer()),
  ]);
  if (!meta.segments) meta.segments = meta.commands;
  const frame = (seg, f) => {
    const [off, n] = meta.segments[seg].frames[f];
    return new Uint32Array(bin, off, n);
  };
  return { meta, frame };
}
