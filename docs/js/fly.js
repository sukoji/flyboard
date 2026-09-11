// A male Drosophila melanogaster for three.js, animated by motor-neuron channels (0..1):
//   legs | Lfl Rfl Lml Rml Lhl Rhl, wingL wingR, abdomen, jump, proboscis, neckL neckR, haltere, ear, love
// Units ~ mm, fly faces +X, Y up. Not a physics model: each part moves in proportion to its channel.
// Anatomy: faceted red eyes, orange frons, ocelli, feathery aristae, macro/microchaetae, scutellum,
// segmented abdomen with the male's black tip, veined iridescent wings, halteres, coxa-femur-tibia-5 tarsomeres
// with tibial spurs and claws, and the male-only sex combs on the front legs.
// For fun it wears headphones (a fly actually hears with its antennae) that glow with the sound it hears;
// notes float up with the ear input and hearts with the FLY SCORE ("love").
import * as THREE from "three";

const TAN = 0xc49a5a, THORAX = 0x8a6336, LEG = 0x5e4024, EYE = 0xa3121a;
export const GROUND = -0.3;
const V = (x, y, z) => new THREE.Vector3(x, y, z);

function canvasTex(w, h, draw, opts = {}) {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  if (opts.srgb) t.colorSpace = THREE.SRGBColorSpace;
  if (opts.repeat) { t.wrapS = t.wrapT = THREE.RepeatWrapping; t.repeat.set(opts.repeat, opts.repeat); }
  return t;
}

const facetTexture = () => canvasTex(256, 256, (g, size) => {
  // hexagonal ommatidia as a bump map for the compound eyes
  const cell = 9, h = cell * Math.sqrt(3) / 2;
  g.fillStyle = "#fff";
  g.fillRect(0, 0, size, size);
  for (let row = 0; row * h < size + cell; row++) {
    for (let col = 0; col * cell < size + cell; col++) {
      const x = col * cell + (row % 2 ? cell / 2 : 0), y = row * h;
      const grd = g.createRadialGradient(x, y, 0, x, y, cell * 0.55);
      grd.addColorStop(0, "#fff");
      grd.addColorStop(0.7, "#bbb");
      grd.addColorStop(1, "#333");
      g.fillStyle = grd;
      g.beginPath();
      for (let k = 0; k < 6; k++) {
        const a = Math.PI / 3 * k + Math.PI / 6;
        g.lineTo(x + Math.cos(a) * cell * 0.55, y + Math.sin(a) * cell * 0.55);
      }
      g.fill();
    }
  }
}, { repeat: 3 });

const cuticleTexture = () => canvasTex(256, 256, (g, s) => {
  // fine speckle = bristle sockets / cuticle grain, used as a bump map
  g.fillStyle = "#808080";
  g.fillRect(0, 0, s, s);
  for (let i = 0; i < 2600; i++) {
    const v = 90 + Math.random() * 90;
    g.fillStyle = `rgb(${v},${v},${v})`;
    g.beginPath();
    g.arc(Math.random() * s, Math.random() * s, 0.6 + Math.random() * 1.4, 0, 7);
    g.fill();
  }
}, { repeat: 2 });

const abdomenTexture = () => canvasTex(64, 512, (g) => {
  // dorsal tergite bands; a male's last segments are fused and solid black. Texture top = waist.
  g.fillStyle = "#d4aa6a";
  g.fillRect(0, 0, 64, 512);
  for (const s of [0.1, 0.27, 0.43]) {
    const y = s * 512;
    const grd = g.createLinearGradient(0, y, 0, y + 70);
    grd.addColorStop(0, "rgba(40,22,10,0)");
    grd.addColorStop(0.55, "rgba(40,22,10,0.95)");
    grd.addColorStop(1, "rgba(40,22,10,0.95)");
    g.fillStyle = grd;
    g.fillRect(0, y, 64, 62);
  }
  g.fillStyle = "#1c120a";
  g.fillRect(0, 0.66 * 512, 64, 512);
}, { srgb: true });

const glyph = (ch, color) => canvasTex(128, 128, (g) => {
  g.font = "bold 104px 'Segoe UI Symbol', 'Noto Sans Symbols', serif";
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.shadowColor = "rgba(0,0,0,0.6)";
  g.shadowBlur = 8;
  g.fillStyle = color;
  g.fillText(ch, 64, 70);
}, { srgb: true });

function ellipsoid(r, mat, seg = 48) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(1, seg, seg / 2), mat);
  m.scale.set(r[0], r[1], r[2]);
  m.castShadow = true;
  return m;
}

function taper(len, r0, r1, mat, radial = 10) {
  // cylinder along +Y from its base; aim() points it and stretches it to the wanted length
  const g = new THREE.CylinderGeometry(r1, r0, len, radial, 1);
  g.translate(0, len / 2, 0);
  const m = new THREE.Mesh(g, mat);
  m.castShadow = true;
  m.userData.len = len;
  return m;
}

function aim(mesh, from, to) {
  const d = new THREE.Vector3().subVectors(to, from);
  mesh.position.copy(from);
  mesh.quaternion.setFromUnitVectors(V(0, 1, 0), d.clone().normalize());
  mesh.scale.set(1, d.length() / mesh.userData.len, 1);
}

function wingShape() {
  const s = new THREE.Shape();
  const L = 1.6, W = 0.56;
  s.moveTo(0, 0);
  s.bezierCurveTo(0.35, 0.16, 1.0, 0.3, L, 0.1);
  s.bezierCurveTo(L + 0.12, -0.08, 1.35, -W * 0.95, 0.85, -W);
  s.bezierCurveTo(0.45, -W * 0.95, 0.12, -0.3, 0, 0);
  return s;
}

function wingVeins(mat) {
  // longitudinal veins L1-L5 + anterior/posterior crossveins as thin tubes, in wing coordinates
  const v = [
    [[0, 0], [0.6, 0.2], [1.2, 0.2], [1.6, 0.1]],
    [[0.05, -0.02], [0.7, 0.08], [1.25, 0.07], [1.62, 0.02]],
    [[0.05, -0.05], [0.8, -0.08], [1.3, -0.1], [1.63, -0.06]],
    [[0.06, -0.08], [0.75, -0.24], [1.2, -0.32], [1.52, -0.3]],
    [[0.07, -0.12], [0.6, -0.38], [0.95, -0.5], [1.18, -0.52]],
    [[0.78, -0.09], [0.77, -0.165], [0.76, -0.24]],
    [[1.0, -0.3], [0.96, -0.38], [0.92, -0.46]],
  ];
  const g = new THREE.Group();
  v.forEach((line, i) => {
    const curve = new THREE.CatmullRomCurve3(line.map(([x, y]) => V(x, y, 0.002)));
    g.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 28, i === 0 ? 0.007 : 0.0045, 5), mat));
  });
  return g;
}

function hairs(points, dirs, len, radius, mat) {
  // many tiny bristles in one draw call
  const geo = new THREE.ConeGeometry(radius, len, 4);
  geo.translate(0, len / 2, 0);
  const m = new THREE.InstancedMesh(geo, mat, points.length);
  const q = new THREE.Quaternion(), s = new THREE.Vector3(1, 1, 1), M = new THREE.Matrix4();
  points.forEach((p, i) => {
    q.setFromUnitVectors(V(0, 1, 0), dirs[i]);
    M.compose(p, q, s.set(1, 0.6 + 0.8 * Math.random(), 1));
    m.setMatrixAt(i, M);
  });
  return m;
}

function surfaceHairs(center, radii, n, keep, tilt) {
  // sample points on an ellipsoid surface; bristles lean backward (-X) as on a real fly
  const pts = [], dirs = [];
  while (pts.length < n) {
    const u = V(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1);
    if (u.lengthSq() > 1 || u.lengthSq() < 0.05) continue;
    u.normalize();
    if (!keep(u)) continue;
    const p = V(center[0] + u.x * radii[0], center[1] + u.y * radii[1], center[2] + u.z * radii[2]);
    const nrm = V(u.x / radii[0], u.y / radii[1], u.z / radii[2]).normalize();
    pts.push(p);
    dirs.push(nrm.multiplyScalar(0.55).add(V(-tilt, 0.1, 0)).normalize());
  }
  return [pts, dirs];
}

class Particles {
  // sprite pool: ♪ notes from the headphones, ♥ hearts from the head
  constructor(parent, tex, n, size) {
    this.items = [];
    for (let i = 0; i < n; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false }));
      s.visible = false;
      s.scale.setScalar(size);
      parent.add(s);
      this.items.push({ s, life: 0, v: V(0, 0, 0), size });
    }
    this.acc = 0;
  }

  update(dt, rate, origin, spread, color) {
    this.acc += dt * rate;
    while (this.acc >= 1) {
      this.acc -= 1;
      const it = this.items.find((x) => x.life <= 0);
      if (!it) break;
      it.life = 1;
      it.s.visible = true;
      it.s.position.copy(origin(Math.random() < 0.5 ? 1 : -1));
      it.v.set((Math.random() - 0.5) * spread, 0.7 + Math.random() * 0.4, (Math.random() - 0.5) * spread);
      if (color) it.s.material.color.set(color);
    }
    for (const it of this.items) {
      if (it.life <= 0) continue;
      it.life -= dt / 1.6;
      it.s.position.addScaledVector(it.v, dt);
      it.s.material.opacity = Math.min(1, it.life * 2.5);
      it.s.scale.setScalar(it.size * (0.7 + 0.3 * (1 - it.life)));
      if (it.life <= 0) it.s.visible = false;
    }
  }
}

export class Fly {
  constructor() {
    this.group = new THREE.Group();
    this.body = new THREE.Group();
    this.group.add(this.body);
    this.t = 0;
    this.jump = 0;
    this.scroll = 0;
    const grain = cuticleTexture();
    const tan = new THREE.MeshPhysicalMaterial({ color: TAN, roughness: 0.55, clearcoat: 0.25, bumpMap: grain, bumpScale: 0.35 });
    const thx = new THREE.MeshPhysicalMaterial({ color: THORAX, roughness: 0.5, clearcoat: 0.35, sheen: 0.4, sheenColor: 0x6a5230,
      bumpMap: grain, bumpScale: 0.5 });
    const leg = new THREE.MeshPhysicalMaterial({ color: LEG, roughness: 0.55, clearcoat: 0.2 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x120c08, roughness: 0.4 });
    const eye = new THREE.MeshPhysicalMaterial({ color: EYE, roughness: 0.3, clearcoat: 0.9, clearcoatRoughness: 0.15,
      bumpMap: facetTexture(), bumpScale: 0.6, sheen: 0.5, sheenColor: 0xff5544 });

    // thorax, scutellum, macrochaetae + microchaetae
    const thorax = ellipsoid([0.56, 0.46, 0.42], thx);
    thorax.position.set(0.45, 0.46, 0);
    this.body.add(thorax);
    const scut = ellipsoid([0.2, 0.1, 0.2], thx);
    scut.position.set(0.0, 0.8, 0);
    this.body.add(scut);
    for (const [x, z] of [[0.75, 0.16], [0.75, -0.16], [0.5, 0.26], [0.5, -0.26], [0.25, 0.2], [0.25, -0.2], [0.05, 0.12], [0.05, -0.12]]) {
      const b = taper(0.32, 0.012, 0.003, dark, 6);
      const base = V(x, 0.46 + 0.4 * Math.sqrt(Math.max(0, 1 - ((x - 0.45) / 0.56) ** 2 - (z / 0.42) ** 2)), z);
      aim(b, base, base.clone().add(V(-0.28, 0.12, z * 0.4)));
      this.body.add(b);
    }
    this.body.add(hairs(...surfaceHairs([0.45, 0.46, 0], [0.565, 0.465, 0.425], 150, (u) => u.y > 0.15, 0.9), 0.045, 0.0028, dark));

    // head (yaws with the neck motor neurons)
    this.head = new THREE.Group();
    this.head.position.set(0.95, 0.5, 0);
    this.body.add(this.head);
    const head = ellipsoid([0.26, 0.34, 0.4], tan);
    head.position.set(0.14, 0, 0);
    this.head.add(head);
    for (const s of [1, -1]) {
      const e = ellipsoid([0.24, 0.33, 0.19], eye, 64);
      e.position.set(0.16, 0.02, 0.26 * s);
      this.head.add(e);
    }
    const frons = ellipsoid([0.08, 0.2, 0.12], new THREE.MeshPhysicalMaterial({ color: 0xc4602c, roughness: 0.6, bumpMap: grain, bumpScale: 0.4 }));
    frons.position.set(0.3, 0.1, 0);
    this.head.add(frons);
    for (const [x, z] of [[0.08, 0], [0.02, 0.06], [0.02, -0.06]]) {
      const o = ellipsoid([0.03, 0.03, 0.03], dark, 12);
      o.position.set(x, 0.33, z);
      this.head.add(o);
    }
    this.head.add(hairs(...surfaceHairs([0.14, 0, 0], [0.265, 0.345, 0.3], 50, (u) => u.y > 0.55, 0.6), 0.06, 0.004, dark));
    for (const [x, z] of [[0.05, 0.08], [0.05, -0.08], [0.18, 0.12], [0.18, -0.12]]) {       // vertical + orbital bristles
      const b = taper(0.2, 0.01, 0.003, dark, 6);
      aim(b, V(x, 0.3, z), V(x - 0.14, 0.44, z * 1.6));
      this.head.add(b);
    }
    // antennae: pedicel + funiculus + feathery arista; they vibrate with the ear input
    this.antennae = [];
    const aristaMat = new THREE.LineBasicMaterial({ color: 0xe9d3a8 });
    for (const s of [1, -1]) {
      const a = new THREE.Group();
      a.position.set(0.36, 0.14, 0.07 * s);
      a.add(ellipsoid([0.035, 0.045, 0.035], tan, 16));
      const fun = ellipsoid([0.045, 0.065, 0.04], new THREE.MeshStandardMaterial({ color: 0x8c6a3e, roughness: 0.6 }), 16);
      fun.position.set(0.04, -0.07, 0.015 * s);
      a.add(fun);
      const root = V(0.08, -0.06, 0.04 * s), tip = V(0.3, 0.13, 0.2 * s);
      const pts = [root, tip];
      for (let k = 1; k < 9; k++) {
        const p = root.clone().lerp(tip, k / 9);
        const l = 0.06 * (1 - k / 11);
        pts.push(p, p.clone().add(V(0.02, l, 0)), p, p.clone().add(V(0.015, -0.7 * l, 0)));
      }
      a.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), aristaMat));
      this.head.add(a);
      this.antennae.push(a);
    }
    // proboscis: rostrum + two labellar pads
    this.prob = new THREE.Group();
    this.prob.position.set(0.22, -0.26, 0);
    this.head.add(this.prob);
    const rost = taper(0.22, 0.06, 0.05, tan);
    rost.rotation.z = Math.PI;
    this.prob.add(rost);
    for (const s of [1, -1]) {
      const l = ellipsoid([0.075, 0.055, 0.055], tan, 16);
      l.position.set(0.02, -0.25, 0.04 * s);
      this.prob.add(l);
    }

    // headphones: band over the vertex, cups behind the eyes; cup rims glow with the ear input
    this.phones = new THREE.Group();
    this.head.add(this.phones);
    const plastic = new THREE.MeshPhysicalMaterial({ color: 0x15161c, roughness: 0.35, clearcoat: 1, clearcoatRoughness: 0.2 });
    const chrome = new THREE.MeshStandardMaterial({ color: 0xd8dde8, metalness: 1, roughness: 0.2 });
    this.glowMat = new THREE.MeshStandardMaterial({ color: 0x111111, emissive: 0x4dabff, emissiveIntensity: 1 });
    const band = new THREE.Mesh(new THREE.TorusGeometry(0.42, 0.028, 12, 48, Math.PI), plastic);
    band.rotation.y = Math.PI / 2;                 // arc in the Y-Z plane, over the top of the head
    band.position.set(-0.04, 0.02, 0);
    this.phones.add(band);
    for (const s of [1, -1]) {
      const cup = new THREE.Group();
      cup.position.set(-0.04, 0.0, 0.42 * s);
      const shell = new THREE.Mesh(new THREE.CylinderGeometry(0.15, 0.13, 0.1, 32), plastic);
      shell.rotation.x = Math.PI / 2;
      cup.add(shell);
      const cushion = new THREE.Mesh(new THREE.TorusGeometry(0.12, 0.035, 10, 32), new THREE.MeshStandardMaterial({ color: 0x2a2a30, roughness: 0.9 }));
      cushion.position.z = -0.055 * s;
      cup.add(cushion);
      const rim = new THREE.Mesh(new THREE.TorusGeometry(0.135, 0.012, 8, 40), this.glowMat);
      rim.position.z = 0.052 * s;
      cup.add(rim);
      const slider = new THREE.Mesh(new THREE.BoxGeometry(0.03, 0.12, 0.02), chrome);
      slider.position.set(0, 0.17, 0);
      cup.add(slider);
      this.phones.add(cup);
    }

    // abdomen (grooves between segments; male: black tip), pivots at the waist
    this.abd = new THREE.Group();
    this.abd.position.set(-0.05, 0.44, 0);
    this.body.add(this.abd);
    const abdMat = new THREE.MeshPhysicalMaterial({ map: abdomenTexture(), roughness: 0.6, clearcoat: 0.12, bumpMap: grain, bumpScale: 0.3 });
    const ag = new THREE.SphereGeometry(1, 64, 48);
    const pos = ag.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const y = pos.getY(i), tt = (1 - y) / 2;   // 0 at the waist pole, 1 at the tip
      let k = 1;
      for (const b of [0.14, 0.31, 0.47, 0.63]) k -= 0.045 * Math.exp(-(((tt - b) / 0.018) ** 2));
      pos.setXYZ(i, pos.getX(i) * k, y, pos.getZ(i) * k);
    }
    ag.computeVertexNormals();
    const abd = new THREE.Mesh(ag, abdMat);
    abd.rotation.z = -Math.PI / 2;
    abd.scale.set(0.4, 0.62, 0.4);
    abd.position.set(-0.52, -0.06, 0);
    abd.castShadow = true;
    this.abd.add(abd);
    this.abd.add(hairs(...surfaceHairs([-0.52, -0.06, 0], [0.625, 0.405, 0.405], 80, (u) => u.y > 0.2 && u.x < 0.85, 1.0), 0.035, 0.0025, dark));

    // wings (iridescent membrane + tube veins) + halteres
    const wmat = new THREE.MeshPhysicalMaterial({ color: 0xe6efff, transparent: true, opacity: 0.28, roughness: 0.15,
      metalness: 0, iridescence: 1, iridescenceIOR: 1.35, side: THREE.DoubleSide, depthWrite: false });
    const vmat = new THREE.MeshStandardMaterial({ color: 0x6d5537, roughness: 0.6, transparent: true, opacity: 0.85 });
    this.wings = [];
    for (const s of [1, -1]) {
      const hinge = new THREE.Group();
      hinge.position.set(0.5, 0.8, 0.16 * s);
      this.body.add(hinge);
      const copies = [];
      for (let k = 0; k < 4; k++) {       // extra copies = motion blur while buzzing
        const w = new THREE.Group();       // yaw (fold/spread) then flap about the costa axis
        const inner = new THREE.Group();   // lays the XY-plane wing flat: length +X, costa -Z (mirrored for the right wing)
        inner.rotation.x = -Math.PI / 2;
        if (s < 0) inner.scale.y = -1;
        const m = new THREE.Mesh(new THREE.ShapeGeometry(wingShape(), 24), wmat.clone());
        const veins = wingVeins(k === 0 ? vmat : vmat.clone());
        inner.add(m, veins);
        w.add(inner);
        w.userData.mesh = m;
        w.userData.veins = veins;
        hinge.add(w);
        copies.push(w);
      }
      this.wings.push({ hinge, copies, s });
      const hal = new THREE.Group();
      hal.position.set(0.12, 0.62, 0.3 * s);
      const stalk = taper(0.16, 0.012, 0.01, tan);
      aim(stalk, V(0, 0, 0), V(-0.05, 0.14, 0.03 * s));
      hal.add(stalk);
      const knob = ellipsoid([0.04, 0.05, 0.04], tan, 12);
      knob.position.set(-0.05, 0.16, 0.03 * s);
      hal.add(knob);
      this.body.add(hal);
      (this.halteres ||= []).push(hal);
    }

    // legs: coxa -> femur -> tibia (+ apical spur) -> 5 tarsomeres (+ claws); male sex comb on the front legs
    this.legs = [];
    const defs = { fl: [0.72, 0.5, 0.16], ml: [0.48, 0.02, 0.2], hl: [0.26, -0.5, 0.18] };
    this.FL = 0.62;
    this.TL = 0.58;
    const tl = [0.1, 0.06, 0.05, 0.045, 0.05];
    for (const [seg, [ax, dx, az]] of Object.entries(defs)) {
      for (const s of [1, -1]) {
        const parts = { femur: taper(this.FL, 0.052, 0.034, leg, 12), tibia: taper(this.TL, 0.032, 0.026, leg, 12), tarsus: [], tl };
        const spur = taper(0.05, 0.008, 0.001, dark, 5);
        spur.position.set(0.02 * s, this.TL - 0.02, 0);
        spur.rotation.z = -0.5 * s;
        parts.tibia.add(spur);
        tl.forEach((len, k) => {
          const t = taper(len, 0.021 - 0.002 * k, 0.018 - 0.002 * k, leg, 8);
          parts.tarsus.push(t);
          this.group.add(t);
        });
        for (const c of [1, -1]) {        // tarsal claws
          const claw = taper(0.035, 0.006, 0.001, dark, 5);
          claw.position.set(0, tl[4], 0.008 * c);
          claw.rotation.x = 0.9 * c;
          claw.rotation.z = -0.7;
          parts.tarsus[4].add(claw);
        }
        if (seg === "fl") {               // sex comb: a row of thick black bristles, only in males
          for (let k = 0; k < 10; k++) {
            const tooth = taper(0.028, 0.004, 0.0015, dark, 4);
            tooth.position.set(0.018, 0.012 + k * 0.0085, 0);
            tooth.rotation.z = -1.25;
            parts.tarsus[0].add(tooth);
          }
        }
        const coxa = ellipsoid([0.09, 0.12, 0.08], thx, 16);
        coxa.position.set(ax, 0.22, az * s);
        this.body.add(coxa);
        this.group.add(parts.femur, parts.tibia);
        this.legs.push({ seg, s, ax, dx, az, key: (s > 0 ? "L" : "R") + seg, parts, phase: (seg === "ml") === (s > 0) ? Math.PI : 0 });
      }
    }
    this.group.traverse((o) => { if (o.isMesh) o.castShadow = true; });

    // stage ring on the floor that pulses with the sound
    this.ringMat = new THREE.MeshBasicMaterial({ color: 0x4dabff, transparent: true, opacity: 0.35, blending: THREE.AdditiveBlending, depthWrite: false });
    this.ring = new THREE.Mesh(new THREE.RingGeometry(1.25, 1.35, 96), this.ringMat);
    this.ring.rotation.x = -Math.PI / 2;
    this.ring.position.set(0.1, GROUND + 0.004, 0);
    this.group.add(this.ring);

    this.notes = new Particles(this.group, glyph("♪", "#ffffff"), 28, 0.26);
    this.notes2 = new Particles(this.group, glyph("♫", "#ffffff"), 14, 0.3);
    this.hearts = new Particles(this.group, glyph("♥", "#ff5c8a"), 24, 0.24);
    this.accent = "#4dabff";
  }

  setAccent(hex) {
    this.accent = hex;
    this.glowMat.emissive.set(hex);
    this.ringMat.color.set(hex);
  }

  update(dt, ch) {
    this.t += dt;
    const t = this.t;
    const g = (k) => ch[k] ?? ch.legs ?? 0;
    this.jump += ((ch.jump || 0) - this.jump) * Math.min(1, dt * 6);
    this.body.position.y = 0.5 * this.jump;
    this.body.rotation.z = 0.12 * this.jump;
    const walk = ["Lfl", "Rfl", "Lml", "Rml", "Lhl", "Rhl"].reduce((a, k) => a + g(k), 0) / 6;
    this.scroll += dt * 1.4 * walk;

    this.head.rotation.y = 0.4 * ((ch.neckL || 0) - (ch.neckR || 0));
    this.prob.rotation.z = -0.9 * (ch.proboscis || 0);
    this.prob.scale.y = 0.6 + 0.8 * (ch.proboscis || 0);
    const ear = ch.ear || 0;
    this.antennae.forEach((a, i) => { a.rotation.x = 0.18 * ear * Math.sin(2 * Math.PI * 13 * t + i * 1.7); });
    this.glowMat.emissiveIntensity = 0.4 + 3.2 * ear;
    this.phones.scale.setScalar(1 + 0.03 * ear * Math.sin(2 * Math.PI * 8 * t));
    this.ringMat.opacity = 0.12 + 0.5 * ear;
    this.ring.scale.setScalar(1 + 0.08 * ear * (0.5 + 0.5 * Math.sin(2 * Math.PI * 2 * t)));
    const ab = ch.abdomen || 0;
    this.abd.rotation.z = -(0.55 * ab + 0.08 * ab * Math.sin(2 * Math.PI * 3 * t));
    this.halteres.forEach((h, i) => { h.rotation.x = 0.5 * (ch.haltere || 0) * Math.sin(2 * Math.PI * 9 * t + i * Math.PI); });

    for (const w of this.wings) {
      const buzz = ch[w.s > 0 ? "wingL" : "wingR"] ?? ch.wings ?? 0;
      const spread = 0.2 + 1.05 * buzz;
      w.copies.forEach((c, k) => {
        c.visible = buzz > 0.04 || k === 0;
        const phase = buzz > 0.04 ? [-1, -0.33, 0.33, 1][k] : 0;
        c.rotation.set(0, 0, 0);
        c.rotateY(Math.PI + w.s * spread);   // pi = folded back over the abdomen; spread swings it out sideways
        c.rotateZ(0.06 + 0.6 * buzz * phase); // flap: raises / lowers the wing tip
        c.userData.mesh.material.opacity = buzz > 0.04 ? 0.09 : 0.3;
        c.userData.veins.children.forEach((m) => { m.material.opacity = buzz > 0.04 ? 0.3 : 0.85; });
      });
    }

    const bodyY = this.body.position.y;
    for (const L of this.legs) {
      const amp = g(L.key);
      const ph = 2 * Math.PI * 6.5 * t + L.phase;
      const hip = V(L.ax, 0.2 + bodyY, L.az * L.s);
      const foot = V(L.ax + L.dx + 0.3 * amp * Math.sin(ph), GROUND + 0.15 * amp * Math.max(0, Math.cos(ph)),
        (L.seg === "ml" ? 0.95 : 0.8) * L.s);
      // two-bone IK, knee bent up and out
      const fl = this.FL, tl = this.TL;
      const d = foot.clone().sub(hip);
      const dist = Math.min(d.length(), fl + tl - 1e-3);
      const a = Math.acos(Math.min(1, (fl * fl + dist * dist - tl * tl) / (2 * fl * dist)));
      const dir = d.clone().normalize();
      const up = V(0, 1, 0.35 * L.s).normalize();
      const side = new THREE.Vector3().crossVectors(dir, up).normalize();
      const bend = new THREE.Vector3().crossVectors(side, dir).normalize();
      const knee = hip.clone().add(dir.clone().multiplyScalar(Math.cos(a) * fl)).add(bend.multiplyScalar(Math.sin(a) * fl));
      aim(L.parts.femur, hip, knee);
      const ankle = hip.clone().add(dir.clone().multiplyScalar(dist));
      aim(L.parts.tibia, knee, ankle);
      let p = ankle;
      const tdir = V(L.seg === "hl" ? -1 : 1, 0, 0.35 * L.s).normalize();
      L.parts.tarsus.forEach((ts, k) => {
        const q = p.clone().add(tdir.clone().multiplyScalar(L.parts.tl[k]));
        aim(ts, p, q);
        p = q;
      });
    }

    // ♪ from the headphone cups (world space ~ head position), ♥ from above the head
    const head = new THREE.Vector3();
    this.head.getWorldPosition(head);
    const cup = (s) => head.clone().add(V(0.02, 0.05, 0.5 * s));
    this.notes.update(dt, 5 * ear, cup, 0.6, this.accent);
    this.notes2.update(dt, 2 * ear, cup, 0.8, this.accent);
    this.hearts.update(dt, 6 * Math.max(0, ch.love || 0) ** 1.5, () => head.clone().add(V(0.1, 0.55, 0)), 0.5, null);
  }
}

export function flyStage(renderer) {
  // scene with lights, soft shadows and a ground grid that scrolls as the fly walks
  const scene = new THREE.Scene();
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironmentLite(), 0.04).texture;
  scene.add(new THREE.HemisphereLight(0xbfd4ff, 0x20160c, 0.9));
  const sun = new THREE.DirectionalLight(0xffffff, 2.4);
  sun.position.set(2, 5, 3);
  sun.castShadow = true;
  sun.shadow.mapSize.set(2048, 2048);
  sun.shadow.camera.left = sun.shadow.camera.bottom = -3;
  sun.shadow.camera.right = sun.shadow.camera.top = 3;
  sun.shadow.radius = 6;
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0x88aaff, 1.2);
  rim.position.set(-3, 2, -3);
  scene.add(rim);
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(12, 12), new THREE.ShadowMaterial({ opacity: 0.45 }));
  ground.rotation.x = -Math.PI / 2;
  ground.position.y = GROUND;
  ground.receiveShadow = true;
  scene.add(ground);
  const grid = new THREE.GridHelper(12, 36, 0x2a3348, 0x1a2030);
  grid.position.y = GROUND + 0.001;
  scene.add(grid);
  return { scene, grid };
}

class RoomEnvironmentLite extends THREE.Scene {
  // tiny stand-in for three's RoomEnvironment: a few emissive panels for reflections
  constructor() {
    super();
    const box = new THREE.Mesh(new THREE.BoxGeometry(10, 10, 10), new THREE.MeshBasicMaterial({ color: 0x202634, side: THREE.BackSide }));
    this.add(box);
    for (const [x, y, z, c] of [[0, 4.9, 0, 0xffffff], [4.9, 1, 1, 0x9fb4ff], [-4.9, 2, -1, 0xffe0c0]]) {
      const p = new THREE.Mesh(new THREE.PlaneGeometry(4, 4), new THREE.MeshBasicMaterial({ color: c }));
      p.position.set(x, y, z);
      p.lookAt(0, 0, 0);
      this.add(p);
    }
  }
}
