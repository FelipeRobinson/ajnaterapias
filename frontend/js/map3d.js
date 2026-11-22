/* Visualizador 3D do mapa de pontos (Three.js).
 * Masculino: BodyParts3D 4.0 (CC BY 4.0) — frontend/models/anatomy/ATRIBUICAO.md
 * Feminino: HuBMAP VH Female v1.5 (CC BY 4.0) — frontend/models/anatomy-f/ATRIBUICAO.md
 * Usado por admin.js: const viewer = await (await import("./map3d.js")).createViewer(container, opts)
 */
import * as THREE from "three";
import { OrbitControls } from "../vendor/three/OrbitControls.js";

const MODELS = { m: "../models/anatomy/", f: "../models/anatomy-f/" };
const LAYER_STYLE = {
  skin: { color: 0xf2c9b1, roughness: 0.72 },
  muscles: { color: 0xb5524a, roughness: 0.55 },
  bones: { color: 0xeee3cc, roughness: 0.8 },
};
const POINT_R = 0.0062;

export async function createViewer(container, opts) {
  const { getPoints, styleOf, onSelect, onHover } = opts;
  // corpo atual: "m" (masculino) ou "f" (feminino)
  let model = opts.model === "f" ? "f" : "m";
  let BASE, manifest, defaults3d, bmin, span;
  async function loadModelData() {
    BASE = MODELS[model];
    manifest = await fetch(BASE + "anatomy.json").then((r) => r.json());
    defaults3d = await fetch(BASE + "acupoints3d.json").then((r) => r.json());
    const [a, b] = manifest.bounds.map((x) => new THREE.Vector3(...x));
    bmin = a;
    span = b.clone().sub(a);
  }
  await loadModelData();

  // ---------------------------------------------------------------- cena
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  container.appendChild(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.01, 20);
  scene.add(new THREE.HemisphereLight(0xffffff, 0x8a6a7a, 1.4));
  const key = new THREE.DirectionalLight(0xffffff, 1.6);
  key.position.set(1.5, 2.5, 2.5);
  scene.add(key);
  const back = new THREE.DirectionalLight(0xffeedd, 0.8);
  back.position.set(-1.5, 1.5, -2.5);
  scene.add(back);
  camera.add(new THREE.PointLight(0xffffff, 0.6, 0, 0));
  scene.add(camera);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.minDistance = 0.12;
  controls.maxDistance = 4.5;
  controls.target.set(0, 0.95, 0);
  camera.position.set(0, 1.0, 3.6);

  const label = document.createElement("div");
  label.className = "m3-label";
  label.hidden = true;
  container.appendChild(label);
  const loading = document.createElement("div");
  loading.className = "m3-loading";
  container.appendChild(loading);

  // ---------------------------------------------------------------- camadas
  let layers = {};
  async function loadLayer(key) {
    if (layers[key]) return layers[key];
    const info = manifest.layers[key];
    if (!info) return null;
    loading.textContent = `Carregando ${info.label.toLowerCase()}…`;
    loading.hidden = false;
    const buf = await fetch(BASE + info.file).then((r) => r.arrayBuffer());
    const q = new Uint16Array(buf, 0, info.vertexCount * 3);
    const pos = new Float32Array(info.vertexCount * 3);
    for (let i = 0; i < pos.length; i += 3) {
      pos[i] = bmin.x + (q[i] / 65535) * span.x;
      pos[i + 1] = bmin.y + (q[i + 1] / 65535) * span.y;
      pos[i + 2] = bmin.z + (q[i + 2] / 65535) * span.z;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
    geo.setIndex(new THREE.BufferAttribute(new Uint32Array(buf, info.indexOffset, info.indexCount), 1));
    geo.computeVertexNormals();
    const mat = new THREE.MeshStandardMaterial({ ...LAYER_STYLE[key], side: THREE.DoubleSide });
    const mesh = new THREE.Mesh(geo, mat);
    mesh.userData = { key, parts: info.parts };
    scene.add(mesh);
    layers[key] = mesh;
    loading.hidden = true;
    return mesh;
  }

  function partName(mesh, faceIndex) {
    const at = faceIndex * 3;
    const parts = mesh.userData.parts;
    let lo = 0, hi = parts.length - 1;
    while (lo <= hi) {
      const mid = (lo + hi) >> 1;
      if (at < parts[mid].start) hi = mid - 1;
      else if (at >= parts[mid].start + parts[mid].count) lo = mid + 1;
      else return parts[mid].name;
    }
    return "";
  }

  // modo: "skin" (pele), "muscles" (músculos), "bones" (ossos); skinOpacity 0..1
  let mode = "skin";
  let skinOpacity = 1;
  async function setLayer(next, opacity) {
    mode = next;
    if (opacity !== undefined) skinOpacity = opacity;
    if (!manifest.layers[next]) next = mode = "skin";
    const skin = await loadLayer("skin");
    if (next !== "skin") await loadLayer(next);
    const op = next === "skin" ? skinOpacity : Math.min(skinOpacity, 0.18);
    skin.material.transparent = op < 1;
    skin.material.opacity = op;
    skin.material.depthWrite = op >= 1;
    skin.renderOrder = 2;
    if (layers.muscles) {
      layers.muscles.visible = next === "muscles";
    }
    if (layers.bones) layers.bones.visible = next === "bones";
    refresh();
  }

  // ---------------------------------------------------------------- pontos
  const sphere = new THREE.SphereGeometry(POINT_R, 14, 10);
  const pointMat = new THREE.MeshStandardMaterial({ roughness: 0.35, metalness: 0.05, emissive: 0x000000 });
  let inst = null;
  let instIndex = []; // [{code, side}]
  const ring = new THREE.Mesh(new THREE.TorusGeometry(POINT_R * 2.6, POINT_R * 0.45, 8, 32),
    new THREE.MeshBasicMaterial({ color: 0x7800b4, depthTest: false, transparent: true }));
  ring.renderOrder = 10;
  ring.visible = false;
  scene.add(ring);
  let selected = null;
  // tamanho dos pontos acompanha o zoom (de longe maiores, de perto menores)
  let sizeK = 1, lastDist = 0;
  const sizeFor = (d) => Math.min(1.15, Math.max(0.22, d / 3.2));

  function positionsOf(p) {
    let saved = p.pos3d ? (typeof p.pos3d === "string" ? JSON.parse(p.pos3d) : p.pos3d) : null;
    if (Array.isArray(saved)) saved = { m: saved };
    const a = saved?.[model];
    if (a) {
      const bilateral = (defaults3d[p.code] || []).length > 1;
      return bilateral ? [a, [-a[0], a[1], a[2], -a[3], a[4], a[5]]] : [a];
    }
    return defaults3d[p.code] || [];
  }

  const tmpM = new THREE.Matrix4(), tmpQ = new THREE.Quaternion(), tmpS = new THREE.Vector3(), tmpC = new THREE.Color();
  const up = new THREE.Vector3(0, 0, 1);

  function refresh() {
    const pts = getPoints();
    const list = [];
    for (const p of pts) positionsOf(p).forEach((v, side) => list.push({ p, v, side }));
    if (!inst || inst.count !== list.length) {
      if (inst) { scene.remove(inst); inst.dispose(); }
      inst = new THREE.InstancedMesh(sphere, pointMat, list.length);
      inst.renderOrder = 5;
      scene.add(inst);
    }
    instIndex = list.map(({ p, side }) => ({ code: p.code, side }));
    list.forEach(({ p, v }, i) => {
      const st = styleOf(p.code);
      const n = new THREE.Vector3(v[3], v[4], v[5]);
      const pos = new THREE.Vector3(v[0], v[1], v[2]).addScaledVector(n, POINT_R * 0.6);
      const s = (st.selected ? 1.6 : st.used ? 1.3 : st.dim ? 0.7 : 1) * sizeK;
      tmpS.set(s, s, s);
      tmpM.compose(pos, tmpQ.identity(), tmpS);
      inst.setMatrixAt(i, tmpM);
      tmpC.set(st.color);
      if (st.dim) tmpC.lerp(new THREE.Color(0xffffff), 0.75);
      inst.setColorAt(i, tmpC);
    });
    inst.instanceMatrix.needsUpdate = true;
    if (inst.instanceColor) inst.instanceColor.needsUpdate = true;
    placeRing();
  }

  function placeRing() {
    const p = selected && getPoints().find((x) => x.code === selected);
    const v = p && positionsOf(p)[0];
    ring.visible = !!v;
    if (!v) return;
    const n = new THREE.Vector3(v[3], v[4], v[5]).normalize();
    ring.position.set(v[0], v[1], v[2]).addScaledVector(n, POINT_R * 0.8);
    ring.quaternion.setFromUnitVectors(up, n);
  }

  // ---------------------------------------------------------------- câmera
  let anim = null;
  function animateTo(target, position, ms = 750) {
    const t0 = performance.now();
    const fromT = controls.target.clone(), fromP = camera.position.clone();
    anim = (now) => {
      const k = Math.min(1, (now - t0) / ms);
      const e = k < 0.5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
      controls.target.lerpVectors(fromT, target, e);
      camera.position.lerpVectors(fromP, position, e);
      if (k >= 1) anim = null;
    };
  }

  function flyTo(code, side = 0) {
    const p = getPoints().find((x) => x.code === code);
    const v = p && positionsOf(p)[side];
    if (!v) return;
    const pos = new THREE.Vector3(v[0], v[1], v[2]);
    const n = new THREE.Vector3(v[3], v[4], v[5]).normalize();
    // olha de frente para a superfície do ponto (orelha -> vista de lado, etc.)
    const dir = n.clone().add(new THREE.Vector3(0, 0.12, 0)).normalize();
    animateTo(pos, pos.clone().addScaledVector(dir, 0.55));
  }

  const VIEWS = {
    front: [new THREE.Vector3(0, 0.95, 0), new THREE.Vector3(0, 1.0, 3.6)],
    back: [new THREE.Vector3(0, 0.95, 0), new THREE.Vector3(0, 1.0, -3.6)],
    left: [new THREE.Vector3(0, 0.95, 0), new THREE.Vector3(3.6, 1.0, 0)],
    right: [new THREE.Vector3(0, 0.95, 0), new THREE.Vector3(-3.6, 1.0, 0)],
    head: [new THREE.Vector3(0, 1.6, 0.02), new THREE.Vector3(0.25, 1.65, 0.75)],
    ear: [new THREE.Vector3(-0.075, 1.59, -0.015), new THREE.Vector3(-0.5, 1.62, 0.05)],
    trunk: [new THREE.Vector3(0, 1.2, 0.05), new THREE.Vector3(0, 1.25, 1.8)],
    arm: [new THREE.Vector3(-0.24, 1.05, 0), new THREE.Vector3(-0.6, 1.1, 1.2)],
    hand: [new THREE.Vector3(-0.29, 0.75, 0.02), new THREE.Vector3(-0.45, 0.8, 0.55)],
    leg: [new THREE.Vector3(-0.09, 0.5, 0.02), new THREE.Vector3(-0.2, 0.55, 1.6)],
    foot: [new THREE.Vector3(-0.09, 0.06, 0.05), new THREE.Vector3(-0.25, 0.25, 0.6)],
  };
  const VIEWS_F = {
    arm: [new THREE.Vector3(-0.3, 1.05, 0), new THREE.Vector3(-0.75, 1.1, 1.2)],
    hand: [new THREE.Vector3(-0.43, 0.8, 0.02), new THREE.Vector3(-0.62, 0.85, 0.55)],
    ear: [new THREE.Vector3(-0.07, 1.55, -0.02), new THREE.Vector3(-0.5, 1.58, 0.05)],
    head: [new THREE.Vector3(0, 1.56, 0.02), new THREE.Vector3(0.25, 1.6, 0.75)],
  };
  // orelha e mão: enquadra pelos próprios pontos do corpo aberto (serve para os dois corpos)
  const ANCHOR = { ear: ["TA17", 0.32], hand: ["IG4", 0.42] };
  function view(name) {
    const a = ANCHOR[name] && defaults3d[ANCHOR[name][0]]?.[0];
    if (a) {
      const pos = new THREE.Vector3(a[0], a[1], a[2]);
      const side = new THREE.Vector3(Math.sign(a[0]) || -1, 0.05, name === "hand" ? 0.9 : 0.15).normalize();
      return animateTo(pos, pos.clone().addScaledVector(side, ANCHOR[name][1]));
    }
    const v = (model === "f" && VIEWS_F[name]) || VIEWS[name];
    if (v) animateTo(v[0], v[1]);
  }

  // ---------------------------------------------------------------- interação
  const ray = new THREE.Raycaster();
  const mouse = new THREE.Vector2();
  let downAt = null;
  let pickHandler = null;

  function setMouse(e) {
    const r = renderer.domElement.getBoundingClientRect();
    mouse.set(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
    ray.setFromCamera(mouse, camera);
  }

  function hitPoint() {
    if (!inst) return null;
    const h = ray.intersectObject(inst)[0];
    return h ? { ...instIndex[h.instanceId], distance: h.distance } : null;
  }

  function hitSurface(onlySkin = false) {
    const objs = Object.values(layers).filter((m) => m.visible && (!onlySkin || m.userData.key === "skin"));
    return ray.intersectObjects(objs)[0] || null;
  }

  renderer.domElement.addEventListener("pointerdown", (e) => { downAt = { x: e.clientX, y: e.clientY }; });
  renderer.domElement.addEventListener("pointerup", (e) => {
    if (!downAt || Math.hypot(e.clientX - downAt.x, e.clientY - downAt.y) > 5) return;
    setMouse(e);
    if (pickHandler) {
      const h = hitSurface(true);
      if (h) {
        const n = h.face.normal.clone().transformDirection(h.object.matrixWorld);
        pickHandler([h.point.x, h.point.y, h.point.z, n.x, n.y, n.z].map((x) => Math.round(x * 10000) / 10000));
      }
      return;
    }
    const hp = hitPoint();
    if (hp) onSelect(hp.code, hp.side);
  });
  renderer.domElement.addEventListener("pointermove", (e) => {
    if (e.pointerType !== "mouse") return;
    setMouse(e);
    const hp = hitPoint();
    const surf = hitSurface();
    const r = container.getBoundingClientRect();
    let text = "";
    if (hp) text = `<b>${hp.code}</b>`;
    else if (surf && surf.object.userData.key !== "skin") text = partName(surf.object, surf.faceIndex);
    renderer.domElement.style.cursor = pickHandler ? "crosshair" : hp ? "pointer" : "grab";
    onHover?.(hp?.code || null, surf && surf.object.userData.key !== "skin" ? partName(surf.object, surf.faceIndex) : "");
    label.hidden = !text;
    if (text) {
      label.innerHTML = text;
      label.style.left = `${e.clientX - r.left + 14}px`;
      label.style.top = `${e.clientY - r.top + 10}px`;
    }
  });
  renderer.domElement.addEventListener("pointerleave", () => { label.hidden = true; onHover?.(null, ""); });

  // ---------------------------------------------------------------- loop
  function resize() {
    const w = container.clientWidth, h = container.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  const ro = new ResizeObserver(resize);
  ro.observe(container);
  resize();
  let running = true;
  renderer.setAnimationLoop((now) => {
    if (!running) return;
    if (anim) anim(now);
    controls.update();
    const dist = camera.position.distanceTo(controls.target);
    if (Math.abs(dist - lastDist) / (lastDist || 1) > 0.06) {
      lastDist = dist;
      sizeK = sizeFor(dist);
      ring.scale.setScalar(sizeK);
      if (inst) refresh();
    }
    renderer.render(scene, camera);
  });

  await setLayer("skin", 1);

  async function setModel(next) {
    if (next === model) return Object.keys(manifest.layers);
    model = next;
    for (const m of Object.values(layers)) { scene.remove(m); m.geometry.dispose(); m.material.dispose(); }
    layers = {};
    await loadModelData();
    await setLayer(manifest.layers[mode] ? mode : "skin", skinOpacity);
    if (selected) flyTo(selected); else view("front");
    return Object.keys(manifest.layers);
  }

  return {
    refresh,
    setLayer,
    setModel,
    get model() { return model; },
    layersAvailable: () => Object.keys(manifest.layers),
    view,
    select(code, { fly = true, side = 0 } = {}) {
      selected = code;
      placeRing();
      refresh();
      if (fly && code) flyTo(code, side);
    },
    startPick(handler) { pickHandler = handler; renderer.domElement.style.cursor = "crosshair"; },
    stopPick() { pickHandler = null; renderer.domElement.style.cursor = "grab"; },
    pause(on) { running = !on; },
    hasDefault: (code) => !!defaults3d[code],
  };
}
