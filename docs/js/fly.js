// A cartoon male fruit fly for three.js (toon shading + ink outlines), animated by motor-neuron channels (0..1):
//   legs | Lfl Rfl Lml Rml Lhl Rhl, wingL wingR, abdomen, jump, proboscis, neckL neckR, haltere, ear, love
// Not a physics model: each body part moves in proportion to the activity of its own motor neurons.
// Still a Drosophila where it counts: aristae, halteres, six legs, striped abdomen with the male's dark tip.
// Eyes are drawn cartoon-style (white with pupils); a real fly's compound eyes are red. Expressions are read off the same channels: it bops to the sound (ear), squints and sweats
// when the abdominal/flight motor latches on (abdomen/wings), and gets heart pupils for a high FLY SCORE (love).
// The headphones are for style: a fly hears with its antennae.
import * as THREE from "three";

export const GROUND = -0.32;
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const INK = 0x2a1a22;

const ramp = (() => {
  const d = new Uint8Array([90, 170, 255]);
  const t = new THREE.DataTexture(d, 3, 1, THREE.RedFormat);
  t.minFilter = t.magFilter = THREE.NearestFilter;
  t.needsUpdate = true;
  return t;
})();
const toon = (color, extra = {}) => new THREE.MeshToonMaterial({ color, gradientMap: ramp, ...extra });
const inkMat = new THREE.MeshBasicMaterial({ color: INK, side: THREE.BackSide });

function outlined(mesh, w = 0.06) {
  // inverted-hull outline: a slightly bigger black back-face copy
  const o = new THREE.Mesh(mesh.geometry, inkMat);
  o.scale.setScalar(1 + w);
  mesh.add(o);
  mesh.castShadow = true;
  return mesh;
}

function blob(r, mat, pos, w = 0.06, seg = 40) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(1, seg, Math.round(seg * 0.75)), mat);
  m.scale.set(...r);
  m.position.set(...pos);
  return outlined(m, w);
}

function capsule(len, r, mat) {
  // along +Y from its base, for limb segments aimed with aim()
  const g = new THREE.CapsuleGeometry(r, len, 6, 12);
  g.translate(0, len / 2, 0);
  const m = outlined(new THREE.Mesh(g, mat), 0.12);
  m.userData.len = len;
  return m;
}

function aim(mesh, from, to) {
  const d = new THREE.Vector3().subVectors(to, from);
  mesh.position.copy(from);
  mesh.quaternion.setFromUnitVectors(V(0, 1, 0), d.clone().normalize());
  mesh.scale.set(1, Math.max(0.2, d.length() / mesh.userData.len), 1);
}

const tex = (w, h, draw) => {
  const c = document.createElement("canvas");
  c.width = w;
  c.height = h;
  draw(c.getContext("2d"), w, h);
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
};

const stripes = () => tex(64, 256, (g) => {
  // texture top = waist; soft brown bands, male tip dark
  g.fillStyle = "#efcf9f";
  g.fillRect(0, 0, 64, 256);
  g.fillStyle = "#9a6a40";
  for (const y of [0.24, 0.44]) g.fillRect(0, y * 256, 64, 0.08 * 256);
  g.fillStyle = "#5b3a22";
  g.fillRect(0, 0.66 * 256, 64, 256);
});

const glyph = (ch, color, size = 104) => tex(128, 128, (g) => {
  g.font = `bold ${size}px 'Segoe UI Symbol', 'Segoe UI Emoji', 'Noto Sans Symbols', serif`;
  g.textAlign = "center";
  g.textBaseline = "middle";
  g.lineWidth = 8;
  g.strokeStyle = "#2a1a22";
  g.strokeText(ch, 64, 70);
  g.fillStyle = color;
  g.fillText(ch, 64, 70);
});

function heartShape(s) {
  const h = new THREE.Shape();
  h.moveTo(0, -0.9 * s);
  h.bezierCurveTo(-1.2 * s, -0.1 * s, -0.8 * s, 0.9 * s, 0, 0.35 * s);
  h.bezierCurveTo(0.8 * s, 0.9 * s, 1.2 * s, -0.1 * s, 0, -0.9 * s);
  return h;
}

function wingShape() {
  const s = new THREE.Shape();
  s.moveTo(0, 0);
  s.bezierCurveTo(0.2, 0.28, 0.85, 0.34, 1.05, 0.05);
  s.bezierCurveTo(1.15, -0.18, 0.8, -0.42, 0.45, -0.36);
  s.bezierCurveTo(0.2, -0.3, 0.02, -0.14, 0, 0);
  return s;
}

class Particles {
  // sprite pool: ♪ notes from the headphones, ♥ hearts from the head, sweat drops
  constructor(parent, map, n, size, life = 1.6, gravity = 0) {
    this.items = [];
    for (let i = 0; i < n; i++) {
      const s = new THREE.Sprite(new THREE.SpriteMaterial({ map, transparent: true, depthWrite: false }));
      s.visible = false;
      parent.add(s);
      this.items.push({ s, life: 0, v: V(0, 0, 0) });
    }
    Object.assign(this, { acc: 0, size, lifeS: life, gravity });
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
      it.v.set((Math.random() - 0.5) * spread, this.gravity ? -0.2 : 0.7 + Math.random() * 0.4, (Math.random() - 0.5) * spread);
      if (color) it.s.material.color.set(color);
    }
    for (const it of this.items) {
      if (it.life <= 0) continue;
      it.life -= dt / this.lifeS;
      it.v.y -= this.gravity * dt;
      it.s.position.addScaledVector(it.v, dt);
      it.s.material.opacity = Math.min(1, it.life * 2.5);
      it.s.scale.setScalar(this.size * (0.6 + 0.4 * Math.min(1, (1 - it.life) * 4)));
      if (it.life <= 0) it.s.visible = false;
    }
  }
}

export class Fly {
  constructor() {
    this.group = new THREE.Group();
    this.body = new THREE.Group();          // everything above the legs; bobs, squashes, hops
    this.group.add(this.body);
    this.t = 0;
    this.jump = 0;
    this.scroll = 0;
    this.accent = "#4dabff";
    const skin = toon(0xefcf9f), thx = toon(0xcf9a60), dark = toon(0x6a4028), eyeWhite = toon(0xffffff);

    // thorax + abdomen (pivots at the waist so it can curl)
    this.body.add(blob([0.46, 0.44, 0.42], thx, [0.12, 0.52, 0]));
    this.body.add(blob([0.16, 0.08, 0.18], thx, [-0.2, 0.9, 0], 0.1));      // scutellum
    this.abd = new THREE.Group();
    this.abd.position.set(-0.22, 0.5, 0);
    this.body.add(this.abd);
    const am = new THREE.Mesh(new THREE.SphereGeometry(1, 40, 30), toon(0xffffff, { map: stripes() }));
    am.rotation.z = -Math.PI / 2;           // poles along X: texture top at the waist, dark tip at the back
    am.scale.set(0.42, 0.5, 0.42);
    am.position.set(-0.38, -0.04, 0);
    this.abd.add(outlined(am, 0.05));

    // big head: yaws with the neck motor neurons, bops to the sound
    this.head = new THREE.Group();
    this.head.position.set(0.62, 0.78, 0);
    this.body.add(this.head);
    this.head.add(blob([0.5, 0.48, 0.52], skin, [0.2, 0.05, 0], 0.045));
    this.eyes = [];
    for (const s of [1, -1]) {
      const dir = V(0.86, 0.14, 0.5 * s).normalize();
      const eye = new THREE.Group();
      eye.position.copy(V(0.2, 0.08, 0).add(dir.clone().multiplyScalar(0.38)));
      eye.quaternion.setFromUnitVectors(V(0, 0, 1), dir);   // local +Z looks outward
      eye.add(blob([0.25, 0.29, 0.2], eyeWhite, [0, 0, 0], 0.06));
      const pupil = new THREE.Mesh(new THREE.SphereGeometry(1, 24, 16), new THREE.MeshBasicMaterial({ color: 0x1a0f14 }));
      pupil.scale.set(0.15, 0.18, 0.05);
      pupil.position.set(0.02, -0.01, 0.17);
      eye.add(pupil);
      const shine = new THREE.Group();          // two sparkles
      for (const [x, y, r] of [[0.07, 0.07, 0.055], [-0.03, -0.07, 0.025]]) {
        const d = new THREE.Mesh(new THREE.SphereGeometry(1, 16, 12), new THREE.MeshBasicMaterial({ color: 0xffffff }));
        d.scale.set(r, r, 0.02);
        d.position.set(x, y, 0.215);
        shine.add(d);
      }
      eye.add(shine);
      const heart = new THREE.Mesh(new THREE.ShapeGeometry(heartShape(0.13)), new THREE.MeshBasicMaterial({ color: 0xff3d7f }));
      heart.position.set(0.0, 0.0, 0.205);
      heart.visible = false;
      eye.add(heart);
      this.head.add(eye);
      this.eyes.push({ eye, pupil, shine, heart });
    }
    this.blush = [];
    for (const s of [1, -1]) {
      const b = new THREE.Mesh(new THREE.SphereGeometry(1, 20, 14), new THREE.MeshBasicMaterial({ color: 0xff7aa2, transparent: true, opacity: 0.55 }));
      b.scale.set(0.09, 0.06, 0.02);
      const n = V(0.8, -0.12, 0.6 * s).normalize();
      b.position.copy(V(0.2, -0.1, 0).add(n.clone().multiplyScalar(0.47)));
      b.quaternion.setFromUnitVectors(V(0, 0, 1), n);
      this.head.add(b);
      this.blush.push(b);
    }
    const smile = new THREE.Mesh(new THREE.TorusGeometry(0.08, 0.018, 8, 24, Math.PI), new THREE.MeshBasicMaterial({ color: INK }));
    smile.position.set(0.69, -0.16, 0);
    smile.rotation.set(0, Math.PI / 2, Math.PI);
    this.head.add(smile);
    this.smile = smile;
    for (const [x, z] of [[0.12, 0], [0.06, 0.07], [0.06, -0.07]]) {       // ocelli
      const o = new THREE.Mesh(new THREE.SphereGeometry(0.03, 10, 8), toon(0x3b1d12));
      o.position.set(x, 0.52, z);
      this.head.add(o);
    }
    // antennae: stubby stalk + feathery arista, wiggling with the ear input
    this.antennae = [];
    for (const s of [1, -1]) {
      const a = new THREE.Group();
      a.position.set(0.62, 0.22, 0.1 * s);
      const seg = capsule(0.1, 0.04, skin);
      aim(seg, V(0, 0, 0), V(0.06, 0.08, 0.02 * s));
      a.add(seg);
      a.add(blob([0.06, 0.08, 0.05], thx, [0.07, 0.1, 0.02 * s], 0.12, 16));   // funiculus (3rd segment)
      const curve = new THREE.CatmullRomCurve3([V(0.1, 0.14, 0.04 * s), V(0.2, 0.26, 0.1 * s), V(0.24, 0.36, 0.16 * s)]);
      a.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 16, 0.008, 5), toon(0x8a6040)));   // arista
      this.head.add(a);
      this.antennae.push(a);
    }
    // proboscis (retracted = tiny nub under the smile)
    this.prob = new THREE.Group();
    this.prob.position.set(0.55, -0.3, 0);
    this.head.add(this.prob);
    const pr = capsule(0.12, 0.045, skin);
    aim(pr, V(0, 0, 0), V(0.02, -0.12, 0));
    this.prob.add(pr);

    // headphones: band over the top, cups at the sides, rims glowing in the chart colour
    this.phones = new THREE.Group();
    this.head.add(this.phones);
    const plastic = toon(0x2b2d3a);
    this.glowMat = new THREE.MeshBasicMaterial({ color: 0x4dabff });
    const band = outlined(new THREE.Mesh(new THREE.TorusGeometry(0.56, 0.05, 12, 48, Math.PI), plastic), 0.12);
    band.rotation.y = Math.PI / 2;
    band.position.set(0.12, 0.06, 0);
    this.phones.add(band);
    for (const s of [1, -1]) {
      const cup = new THREE.Group();
      cup.position.set(0.1, 0.02, 0.56 * s);
      const shell = outlined(new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.2, 0.14, 32), plastic), 0.06);
      shell.rotation.x = Math.PI / 2;
      cup.add(shell);
      const rim = new THREE.Mesh(new THREE.TorusGeometry(0.16, 0.03, 10, 40), this.glowMat);
      rim.position.z = 0.075 * s;
      cup.add(rim);
      this.phones.add(cup);
    }

    // wings: rounded, pale, with a couple of veins; flutter when the wing motor fires
    const wmat = new THREE.MeshBasicMaterial({ color: 0xdff1ff, transparent: true, opacity: 0.55, side: THREE.DoubleSide, depthWrite: false });
    const edge = new THREE.LineBasicMaterial({ color: 0x9fb6d8 });
    this.wings = [];
    this.halteres = [];
    for (const s of [1, -1]) {
      const hinge = new THREE.Group();
      hinge.position.set(0.05, 0.92, 0.18 * s);
      this.body.add(hinge);
      const copies = [];
      for (let k = 0; k < 3; k++) {
        const w = new THREE.Group();
        const inner = new THREE.Group();
        inner.rotation.x = -Math.PI / 2;
        if (s < 0) inner.scale.y = -1;
        const m = new THREE.Mesh(new THREE.ShapeGeometry(wingShape(), 24), wmat.clone());
        inner.add(m, new THREE.LineLoop(new THREE.BufferGeometry().setFromPoints(wingShape().getPoints(40).map((p) => V(p.x, p.y, 0.003))), edge));
        for (const [a, b] of [[[0.05, 0], [0.9, 0.08]], [[0.06, -0.06], [0.75, -0.22]]]) {
          inner.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints([V(...a, 0.003), V(...b, 0.003)]), edge));
        }
        w.add(inner);
        w.userData.mesh = m;
        hinge.add(w);
        copies.push(w);
      }
      this.wings.push({ copies, s });
      const hal = new THREE.Group();               // haltere: tiny lollipop behind the wing
      hal.position.set(-0.12, 0.72, 0.36 * s);
      const st = capsule(0.12, 0.018, skin);
      aim(st, V(0, 0, 0), V(-0.03, 0.12, 0.02 * s));
      hal.add(st);
      hal.add(blob([0.05, 0.05, 0.05], skin, [-0.03, 0.15, 0.02 * s], 0.15, 12));
      this.body.add(hal);
      this.halteres.push(hal);
    }

    // six stubby legs: thigh + shin capsules and a round foot, tripod gait
    this.legs = [];
    const defs = { fl: [0.34, 0.34, 0.2], ml: [0.12, 0.0, 0.24], hl: [-0.1, -0.34, 0.2] };
    for (const [seg, [ax, dx, az]] of Object.entries(defs)) {
      for (const s of [1, -1]) {
        const thigh = capsule(0.26, 0.062, dark), shin = capsule(0.26, 0.052, dark);
        const foot = blob([0.085, 0.05, 0.07], dark, [0, 0, 0], 0.12, 16);
        this.group.add(thigh, shin, foot);
        this.legs.push({ seg, s, ax, dx, az, key: (s > 0 ? "L" : "R") + seg, thigh, shin, foot,
          phase: (seg === "ml") === (s > 0) ? Math.PI : 0 });
      }
    }

    // stage ring, notes, hearts, sweat
    this.ringMat = new THREE.MeshBasicMaterial({ color: 0x4dabff, transparent: true, opacity: 0.4, blending: THREE.AdditiveBlending, depthWrite: false });
    this.ring = new THREE.Mesh(new THREE.RingGeometry(1.15, 1.25, 96), this.ringMat);
    this.ring.rotation.x = -Math.PI / 2;
    this.ring.position.set(0.1, GROUND + 0.004, 0);
    this.group.add(this.ring);
    this.notes = new Particles(this.group, glyph("♪", "#ffffff"), 28, 0.3);
    this.notes2 = new Particles(this.group, glyph("♫", "#ffffff"), 14, 0.34);
    this.hearts = new Particles(this.group, glyph("♥", "#ff4d88"), 28, 0.28);
    this.sweat = new Particles(this.group, glyph("💧", "#6ec6ff", 90), 6, 0.22, 0.9, 2.5);
  }

  setAccent(hex) {
    this.accent = hex;
    this.glowMat.color.set(hex);
    this.ringMat.color.set(hex);
  }

  // style: optional hint from command mode ("groom", "backward", "sing", "hop"); amplitudes still come from ch
  update(dt, ch, style = null) {
    this.t += dt;
    const t = this.t;
    const g = (k) => ch[k] ?? ch.legs ?? 0;
    const ear = ch.ear || 0, ab = ch.abdomen || 0;
    const love = style === "sing" ? 0.6 : Math.max(0, ch.love || 0);   // a singing male looks pleased
    const wingsOn = Math.max(ch.wingL ?? ch.wings ?? 0, ch.wingR ?? ch.wings ?? 0);
    // wing/abdomen motor activity reads as a flinch, except when a command explains it (singing, grooming, feeding)
    const calm = style === "sing" || style === "groom" || style === "feed";
    const flinch = calm ? 0 : Math.min(1, Math.max(ab, wingsOn) * 1.6);

    // hop (giant fiber), breathing, squash when flinching
    this.jump += ((ch.jump || 0) - this.jump) * Math.min(1, dt * 6);
    const hop = 0.35 * this.jump * Math.abs(Math.sin(2 * Math.PI * 1.5 * t));
    const breathe = 1 + 0.025 * Math.sin(2 * Math.PI * 0.8 * t);
    this.body.position.y = hop + 0.02 * ear * Math.abs(Math.sin(2 * Math.PI * 2 * t));
    this.body.scale.set(1 + 0.04 * flinch, breathe * (1 - 0.06 * flinch), 1 + 0.04 * flinch);
    const walk = ["Lfl", "Rfl", "Lml", "Rml", "Lhl", "Rhl"].reduce((a, k) => a + g(k), 0) / 6;
    this.scroll += dt * 1.4 * walk * (style === "backward" ? -1 : 1);

    // head: bop to the beat, yaw from the neck motor neurons, shiver when flinching
    this.head.rotation.set(0.1 * ear * Math.sin(2 * Math.PI * 2 * t) + 0.03 * flinch * Math.sin(2 * Math.PI * 18 * t),
      0.4 * ((ch.neckL || 0) - (ch.neckR || 0)), 0.1 * ear * Math.sin(2 * Math.PI * 2 * t + 1.2));
    this.antennae.forEach((a, i) => { a.rotation.x = 0.25 * ear * Math.sin(2 * Math.PI * 7 * t + i * 1.7); });
    this.prob.scale.setScalar(0.35 + 0.65 * Math.min(1, 3 * (ch.proboscis || 0)));
    this.prob.visible = (ch.proboscis || 0) > 0.02;

    // expressions: squint when flinching, heart pupils when in love, blink now and then
    const blink = (t % 3.7) < 0.12 ? 0.1 : 1;
    const inLove = love > 0.8;
    for (const e of this.eyes) {
      e.heart.visible = inLove;
      e.pupil.visible = e.shine.visible = !inLove;
      e.heart.scale.setScalar(1 + 0.12 * Math.sin(2 * Math.PI * 2.5 * t));
      e.eye.scale.y = Math.min(blink, 1 - 0.25 * flinch);
      e.pupil.scale.y = 0.18 * (1 - 0.5 * flinch);
    }
    this.blush.forEach((b) => { b.material.opacity = 0.35 + 0.5 * love; });
    this.smile.scale.set(1, 1 - 1.6 * flinch + 0.3 * love, 1);   // grin flattens and flips when flinching

    this.glowMat.color.set(this.accent).multiplyScalar(0.5 + 1.2 * ear);
    this.phones.scale.setScalar(1 + 0.04 * ear * Math.sin(2 * Math.PI * 4 * t));
    this.ringMat.opacity = 0.15 + 0.5 * ear;
    this.ring.scale.setScalar(1 + 0.08 * ear * (0.5 + 0.5 * Math.sin(2 * Math.PI * 2 * t)));
    this.abd.rotation.z = -(0.5 * ab + 0.08 * ab * Math.sin(2 * Math.PI * 3 * t));
    this.halteres.forEach((h, i) => { h.rotation.x = 0.6 * (ch.haltere || 0) * Math.sin(2 * Math.PI * 9 * t + i * Math.PI); });

    for (const w of this.wings) {
      let buzz = ch[w.s > 0 ? "wingL" : "wingR"] ?? ch.wings ?? 0;
      if (style === "sing") {                     // a singing male extends one wing and vibrates it
        const on = w.s > 0 ? Math.max(ch.wingL || 0, ch.wingR || 0) : 0;
        w.copies.forEach((c, k) => {
          c.visible = k === 0;
          c.rotation.set(0, 0, 0);
          c.rotateY(Math.PI + w.s * (0.35 + 1.15 * on));
          c.rotateZ(0.08 + 0.18 * on * Math.sin(2 * Math.PI * 11 * t));
          c.userData.mesh.material.opacity = 0.55;
        });
        continue;
      }
      const spread = 0.35 + 1.0 * buzz;
      w.copies.forEach((c, k) => {
        c.visible = buzz > 0.04 || k === 0;
        const phase = buzz > 0.04 ? [-1, 0, 1][k] : 0;
        c.rotation.set(0, 0, 0);
        c.rotateY(Math.PI + w.s * spread);
        c.rotateZ(0.25 + 0.55 * buzz * phase + 0.08 * Math.sin(2 * Math.PI * 1.2 * t));
        c.userData.mesh.material.opacity = buzz > 0.04 ? 0.3 : 0.55;
      });
    }

    const bodyY = this.body.position.y;
    for (const L of this.legs) {
      const amp = g(L.key);
      const ph = 2 * Math.PI * 5 * t * (style === "backward" ? -1 : 1) + L.phase;
      const hip = V(L.ax, 0.2 + bodyY, L.az * L.s);
      let foot = V(L.ax + L.dx + 0.18 * amp * Math.sin(ph), GROUND + 0.05 + 0.12 * amp * Math.max(0, Math.cos(ph)), 0.7 * L.s);
      if (style === "groom" && L.seg === "fl") {  // front legs come up and rub the head / antennae
        const rub = V(1.02 + 0.06 * Math.sin(2 * Math.PI * 4 * t), 0.72 + 0.08 * Math.sin(2 * Math.PI * 4 * t + L.s), 0.2 * L.s);
        foot = foot.lerp(rub, Math.min(1, 1.6 * amp));
      }
      const knee = hip.clone().lerp(foot, 0.5).add(V(0, 0.2, 0.08 * L.s));
      aim(L.thigh, hip, knee);
      aim(L.shin, knee, foot);
      L.foot.position.copy(foot).add(V(0.03, -0.01, 0));
    }

    const head = new THREE.Vector3();
    this.head.getWorldPosition(head);
    const cup = (s) => head.clone().add(V(0.1, 0.1, 0.72 * s));
    this.notes.update(dt, 5 * ear, cup, 0.6, this.accent);
    this.notes2.update(dt, 2 * ear, cup, 0.8, this.accent);
    this.hearts.update(dt, 7 * love ** 1.5, () => head.clone().add(V(0.2, 0.7, 0)), 0.6, null);
    this.sweat.update(dt, 1.4 * flinch, (s) => head.clone().add(V(0.3, 0.45, 0.42 * s)), 0.3, null);
  }
}

export function flyStage(renderer) {
  // bright cartoon stage: warm key light, cool rim, soft shadow, a round platform and a floor grid
  const scene = new THREE.Scene();
  scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x3a2a40, 1.4));
  const sun = new THREE.DirectionalLight(0xfff4e0, 2.2);
  sun.position.set(2, 5, 3);
  sun.castShadow = true;
  sun.shadow.mapSize.set(1024, 1024);
  sun.shadow.camera.left = sun.shadow.camera.bottom = -3;
  sun.shadow.camera.right = sun.shadow.camera.top = 3;
  sun.shadow.radius = 4;
  scene.add(sun);
  const rim = new THREE.DirectionalLight(0x9fc0ff, 1.2);
  rim.position.set(-3, 2, -3);
  scene.add(rim);
  const stage = new THREE.Mesh(new THREE.CylinderGeometry(1.5, 1.6, 0.12, 64), toon(0x1c2233));
  stage.position.y = GROUND - 0.06;
  stage.receiveShadow = true;
  scene.add(stage);
  const shadow = new THREE.Mesh(new THREE.PlaneGeometry(6, 6), new THREE.ShadowMaterial({ opacity: 0.35 }));
  shadow.rotation.x = -Math.PI / 2;
  shadow.position.y = GROUND + 0.001;
  shadow.receiveShadow = true;
  scene.add(shadow);
  const grid = new THREE.GridHelper(12, 36, 0x252c40, 0x171c2a);
  grid.position.y = GROUND - 0.12;
  scene.add(grid);
  return { scene, grid };
}
