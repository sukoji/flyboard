// A male Drosophila melanogaster for three.js, animated by motor-neuron channels (0..1):
//   legs | Lfl Rfl Lml Rml Lhl Rhl, wingL wingR, abdomen, jump, proboscis, neckL neckR, haltere, ear
// Units ~ mm, fly faces +X, Y up. Not a physics model: each part moves in proportion to its channel.
import * as THREE from "three";

const TAN = 0xc49a5a, THORAX = 0x8a6336, LEG = 0x5e4024, EYE = 0xa3121a;
export const GROUND = -0.3;

function facetTexture(size = 256, cell = 9) {
  // hexagonal ommatidia as a bump map for the compound eyes
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  g.fillStyle = "#fff";
  g.fillRect(0, 0, size, size);
  const h = cell * Math.sqrt(3) / 2;
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
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(3, 3);
  return t;
}

function abdomenTexture() {
  // dorsal tergite bands; a male's last segments are solid black
  const c = document.createElement("canvas");
  c.width = 64;
  c.height = 512;
  const g = c.getContext("2d");
  g.fillStyle = "#d4aa6a";
  g.fillRect(0, 0, 64, 512);
  const seg = [0.1, 0.27, 0.43];
  for (const s of seg) {
    const y = s * 512;
    const grd = g.createLinearGradient(0, y, 0, y + 70);
    grd.addColorStop(0, "rgba(40,22,10,0)");
    grd.addColorStop(0.55, "rgba(40,22,10,0.95)");
    grd.addColorStop(1, "rgba(40,22,10,0.95)");
    g.fillStyle = grd;
    g.fillRect(0, y, 64, 62);
  }
  g.fillStyle = "#1c120a";
  g.fillRect(0, 0.6 * 512, 64, 512);   // male: the last abdominal segments are fused and black
  const t = new THREE.CanvasTexture(c);
  t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function ellipsoid(r, mat, seg = 48) {
  const m = new THREE.Mesh(new THREE.SphereGeometry(1, seg, seg / 2), mat);
  m.scale.set(r[0], r[1], r[2]);
  m.castShadow = true;
  return m;
}

function taper(len, r0, r1, mat) {
  // cylinder along +Y from its base, so a segment can be aimed with lookAt-style quaternions
  const g = new THREE.CylinderGeometry(r1, r0, len, 10, 1);
  g.translate(0, len / 2, 0);
  const m = new THREE.Mesh(g, mat);
  m.castShadow = true;
  return m;
}

function aim(mesh, from, to) {
  const d = new THREE.Vector3().subVectors(to, from);
  mesh.position.copy(from);
  mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), d.clone().normalize());
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
  // longitudinal veins L1-L5 + anterior/posterior crossveins, in wing coordinates
  const v = [
    [[0, 0], [0.6, 0.2], [1.2, 0.2], [1.6, 0.1]],            // costa / L1
    [[0.05, -0.02], [0.7, 0.08], [1.25, 0.07], [1.62, 0.02]], // L2
    [[0.05, -0.05], [0.8, -0.08], [1.3, -0.1], [1.63, -0.06]],// L3
    [[0.06, -0.08], [0.75, -0.24], [1.2, -0.32], [1.52, -0.3]],// L4
    [[0.07, -0.12], [0.6, -0.38], [0.95, -0.5], [1.18, -0.52]],// L5
    [[0.78, -0.09], [0.76, -0.24]],                           // anterior crossvein
    [[1.0, -0.3], [0.92, -0.46]],                             // posterior crossvein
  ];
  const g = new THREE.Group();
  for (const line of v) {
    const pts = line.map(([x, y]) => new THREE.Vector3(x, y, 0.002));
    const curve = pts.length > 2 ? new THREE.CatmullRomCurve3(pts).getPoints(24) : pts;
    g.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve), mat));
  }
  return g;
}

export class Fly {
  constructor() {
    this.group = new THREE.Group();
    this.body = new THREE.Group();
    this.group.add(this.body);
    this.t = 0;
    this.jump = 0;
    this.scroll = 0;
    const tan = new THREE.MeshPhysicalMaterial({ color: TAN, roughness: 0.55, clearcoat: 0.25 });
    const thx = new THREE.MeshPhysicalMaterial({ color: THORAX, roughness: 0.5, clearcoat: 0.35, sheen: 0.4, sheenColor: 0x6a5230 });
    const leg = new THREE.MeshStandardMaterial({ color: LEG, roughness: 0.6 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x1a120c, roughness: 0.4 });
    const eye = new THREE.MeshPhysicalMaterial({ color: EYE, roughness: 0.3, clearcoat: 0.9, clearcoatRoughness: 0.15,
      bumpMap: facetTexture(), bumpScale: 0.6, sheen: 0.5, sheenColor: 0xff5544 });

    // thorax, scutellum, bristles
    const thorax = ellipsoid([0.56, 0.46, 0.42], thx);
    thorax.position.set(0.45, 0.46, 0);
    this.body.add(thorax);
    const scut = ellipsoid([0.2, 0.1, 0.2], thx);
    scut.position.set(0.0, 0.8, 0);
    this.body.add(scut);
    const bristle = new THREE.MeshStandardMaterial({ color: 0x0d0906, roughness: 0.4 });
    for (const [x, z] of [[0.75, 0.16], [0.75, -0.16], [0.5, 0.26], [0.5, -0.26], [0.25, 0.2], [0.25, -0.2], [0.05, 0.12], [0.05, -0.12]]) {
      const b = taper(0.32, 0.012, 0.003, bristle);
      b.userData.len = 0.32;
      const base = new THREE.Vector3(x, 0.46 + 0.4 * Math.sqrt(Math.max(0, 1 - ((x - 0.45) / 0.56) ** 2 - (z / 0.42) ** 2)), z);
      aim(b, base, base.clone().add(new THREE.Vector3(-0.28, 0.12, z * 0.4)));
      this.body.add(b);
    }

    // head (yaws with the neck motor neurons)
    this.head = new THREE.Group();
    this.head.position.set(0.95, 0.5, 0);
    this.body.add(this.head);
    const head = ellipsoid([0.26, 0.34, 0.4], tan);
    head.position.set(0.14, 0, 0);
    this.head.add(head);
    for (const s of [1, -1]) {
      const e = ellipsoid([0.23, 0.32, 0.18], eye, 64);
      e.position.set(0.16, 0.02, 0.26 * s);
      this.head.add(e);
    }
    for (const [x, z] of [[0.08, 0], [0.02, 0.06], [0.02, -0.06]]) {
      const o = ellipsoid([0.03, 0.03, 0.03], dark, 12);
      o.position.set(x, 0.33, z);
      this.head.add(o);
    }
    // antennae: pedicel + funiculus + feathery arista; they vibrate with the ear input
    this.antennae = [];
    const aristaMat = new THREE.LineBasicMaterial({ color: 0xe9d3a8 });
    for (const s of [1, -1]) {
      const a = new THREE.Group();
      a.position.set(0.34, 0.14, 0.07 * s);
      const ped = ellipsoid([0.035, 0.045, 0.035], tan, 16);
      a.add(ped);
      const fun = ellipsoid([0.045, 0.065, 0.04], new THREE.MeshStandardMaterial({ color: 0x8c6a3e, roughness: 0.6 }), 16);
      fun.position.set(0.04, -0.07, 0.015 * s);
      a.add(fun);
      const pts = [];
      const root = new THREE.Vector3(0.1, -0.08, 0.05 * s), tip = new THREE.Vector3(0.28, 0.12, 0.2 * s);
      pts.push(root, tip);
      for (let k = 1; k < 7; k++) {
        const p = root.clone().lerp(tip, k / 7);
        pts.push(p, p.clone().add(new THREE.Vector3(0.03, 0.05, 0)), p, p.clone().add(new THREE.Vector3(0.02, -0.04, 0)));
      }
      a.add(new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(pts), aristaMat));
      this.head.add(a);
      this.antennae.push(a);
    }
    // proboscis: rostrum + labellum lobes
    this.prob = new THREE.Group();
    this.prob.position.set(0.22, -0.26, 0);
    this.head.add(this.prob);
    const rost = taper(0.22, 0.06, 0.05, tan);
    rost.rotation.z = Math.PI;
    this.prob.add(rost);
    for (const s of [1, -1]) {
      const l = ellipsoid([0.06, 0.05, 0.05], tan, 16);
      l.position.set(0.02, -0.24, 0.035 * s);
      this.prob.add(l);
    }

    // abdomen (male: dark tip), pivots at the waist
    this.abd = new THREE.Group();
    this.abd.position.set(-0.05, 0.44, 0);
    this.body.add(this.abd);
    const abdMat = new THREE.MeshPhysicalMaterial({ map: abdomenTexture(), roughness: 0.5, clearcoat: 0.3 });
    const abd = new THREE.Mesh(new THREE.SphereGeometry(1, 48, 32), abdMat);
    abd.rotation.z = -Math.PI / 2;          // poles along X (texture top = waist, bottom = black male tip)
    abd.scale.set(0.4, 0.62, 0.4);           // local y (pole axis) becomes the body length
    abd.position.set(-0.52, -0.06, 0);
    abd.castShadow = true;
    this.abd.add(abd);

    // wings (iridescent, with veins) + halteres
    const wmat = new THREE.MeshPhysicalMaterial({ color: 0xe6efff, transparent: true, opacity: 0.28, roughness: 0.15,
      metalness: 0, iridescence: 1, iridescenceIOR: 1.35, side: THREE.DoubleSide, depthWrite: false });
    const vmat = new THREE.LineBasicMaterial({ color: 0x6d5537, transparent: true, opacity: 0.8 });
    this.wings = [];
    for (const s of [1, -1]) {
      const hinge = new THREE.Group();
      hinge.position.set(0.5, 0.78, 0.16 * s);
      this.body.add(hinge);
      const copies = [];
      for (let k = 0; k < 4; k++) {       // extra copies = motion blur while buzzing
        const w = new THREE.Group();       // yaw (fold/spread) then flap about the costa axis
        const inner = new THREE.Group();   // lays the XY-plane wing flat: length +X, costa -Z (mirrored for the right wing)
        inner.rotation.x = -Math.PI / 2;
        if (s < 0) inner.scale.y = -1;
        const m = new THREE.Mesh(new THREE.ShapeGeometry(wingShape(), 24), wmat.clone());
        inner.add(m, wingVeins(vmat));
        w.add(inner);
        w.userData.mesh = m;
        hinge.add(w);
        copies.push(w);
      }
      this.wings.push({ hinge, copies, s });
      const hal = new THREE.Group();
      hal.position.set(0.12, 0.62, 0.3 * s);
      const stalk = taper(0.16, 0.012, 0.01, tan);
      stalk.userData.len = 0.16;
      aim(stalk, new THREE.Vector3(), new THREE.Vector3(-0.05, 0.14, 0.03 * s));
      hal.add(stalk);
      const knob = ellipsoid([0.04, 0.05, 0.04], tan, 12);
      knob.position.set(-0.05, 0.16, 0.03 * s);
      hal.add(knob);
      this.body.add(hal);
      (this.halteres ||= []).push(hal);
    }

    // legs: coxa -> femur -> tibia -> 5 tarsomeres + claws
    this.legs = [];
    const defs = { fl: [0.72, 0.5, 0.16], ml: [0.48, 0.02, 0.2], hl: [0.26, -0.5, 0.18] };
    for (const [seg, [ax, dx, az]] of Object.entries(defs)) {
      for (const s of [1, -1]) {
        const parts = { femur: taper(1, 0.05, 0.035, leg), tibia: taper(1, 0.032, 0.025, leg), tarsus: [] };
        parts.femur.userData.len = 1;
        parts.tibia.userData.len = 1;
        for (let k = 0; k < 5; k++) {
          const t = taper(1, 0.02, 0.016, leg);
          t.userData.len = 1;
          parts.tarsus.push(t);
          this.group.add(t);
        }
        const coxa = ellipsoid([0.09, 0.12, 0.08], thx, 16);
        coxa.position.set(ax, 0.22, az * s);
        this.body.add(coxa);
        this.group.add(parts.femur, parts.tibia);
        this.legs.push({ seg, s, ax, dx, az, key: (s > 0 ? "L" : "R") + seg, parts, phase: (seg === "ml") === (s > 0) ? Math.PI : 0 });
      }
    }
    this.group.traverse((o) => { if (o.isMesh) o.castShadow = true; });
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
    const ab = ch.abdomen || 0;
    this.abd.rotation.z = -(0.55 * ab + 0.08 * ab * Math.sin(2 * Math.PI * 3 * t));
    this.halteres.forEach((h, i) => { h.rotation.x = 0.5 * (ch.haltere || 0) * Math.sin(2 * Math.PI * 9 * t + i * Math.PI); });

    for (const w of this.wings) {
      const buzz = ch[w.s > 0 ? "wingL" : "wingR"] ?? ch.wings ?? 0;
      const spread = 0.2 + 1.05 * buzz;
      w.copies.forEach((c, k) => {
        const on = buzz > 0.04 || k === 0;
        c.visible = on;
        const phase = buzz > 0.04 ? [-1, -0.33, 0.33, 1][k] : 0;
        c.rotation.set(0, 0, 0);
        c.rotateY(Math.PI + w.s * spread);   // pi = folded back over the abdomen; spread swings it out sideways
        c.rotateZ(0.06 + 0.6 * buzz * phase); // flap: raises / lowers the wing tip
        c.userData.mesh.material.opacity = buzz > 0.04 ? 0.09 : 0.3;
      });
    }

    const ground = GROUND;
    const bodyY = this.body.position.y;
    for (const L of this.legs) {
      const amp = g(L.key);
      const ph = 2 * Math.PI * 6.5 * t + L.phase;
      const hip = new THREE.Vector3(L.ax, 0.2 + bodyY, L.az * L.s);
      const foot = new THREE.Vector3(L.ax + L.dx + 0.3 * amp * Math.sin(ph), ground + 0.15 * amp * Math.max(0, Math.cos(ph)),
        (L.seg === "ml" ? 0.95 : 0.8) * L.s);
      // two-bone IK, knee bent up and out
      const fl = 0.62, tl = 0.58;
      const d = foot.clone().sub(hip);
      const dist = Math.min(d.length(), fl + tl - 1e-3);
      const a = Math.acos(Math.min(1, (fl * fl + dist * dist - tl * tl) / (2 * fl * dist)));
      const dir = d.clone().normalize();
      const up = new THREE.Vector3(0, 1, 0.35 * L.s).normalize();
      const side = new THREE.Vector3().crossVectors(dir, up).normalize();
      const bend = new THREE.Vector3().crossVectors(side, dir).normalize();
      const knee = hip.clone().add(dir.clone().multiplyScalar(Math.cos(a) * fl)).add(bend.multiplyScalar(Math.sin(a) * fl));
      aim(L.parts.femur, hip, knee);
      aim(L.parts.tibia, knee, foot);
      let p = foot.clone();
      const tdir = new THREE.Vector3(L.seg === "hl" ? -1 : 1, 0, 0.35 * L.s).normalize();
      L.parts.tarsus.forEach((ts, k) => {
        const q = p.clone().add(tdir.clone().multiplyScalar(0.085 - 0.008 * k));
        aim(ts, p, q);
        p = q;
      });
    }
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
