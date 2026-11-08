// Castle Siege 3D - Phase 1
// A Stronghold-style castle builder scene: procedural low-poly geometry only,
// no external models, images or audio. Three.js + OrbitControls, bundled by Vite.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ---------------------------------------------------------------------------
// Game state (Phase 1: display only, except Build Wall which spends stone)
// ---------------------------------------------------------------------------
const state = {
  wood: 100,
  stone: 80,
  gold: 50,
  food: 60,
  population: 12,
  wave: 0,
  placingWall: false,
};

const WALL_COST_STONE = 10;

// ---------------------------------------------------------------------------
// Renderer / scene / camera
// ---------------------------------------------------------------------------
const container = document.getElementById('app');

let renderer;
try {
  renderer = new THREE.WebGLRenderer({ antialias: true });
} catch (err) {
  document.getElementById('selected-name').textContent =
    'WebGL is not available in this browser, the 3D scene cannot start.';
  throw err;
}
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.shadowMap.enabled = true;
renderer.shadowMap.type = THREE.PCFSoftShadowMap;
container.appendChild(renderer.domElement);

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x87bfe8);
scene.fog = new THREE.Fog(0xbfd9f2, 90, 230);

const camera = new THREE.PerspectiveCamera(
  55,
  window.innerWidth / window.innerHeight,
  0.1,
  600,
);
camera.position.set(44, 34, 44);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 2, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 14;
controls.maxDistance = 130;
controls.maxPolarAngle = Math.PI / 2 - 0.04; // never go under the ground

// ---------------------------------------------------------------------------
// Lighting
// ---------------------------------------------------------------------------
const hemi = new THREE.HemisphereLight(0xbfd9ff, 0x6a8f5f, 0.95);
scene.add(hemi);

const sun = new THREE.DirectionalLight(0xffe0b3, 1.7);
sun.position.set(45, 65, 28);
sun.castShadow = true;
sun.shadow.mapSize.set(2048, 2048);
sun.shadow.camera.left = -70;
sun.shadow.camera.right = 70;
sun.shadow.camera.top = 70;
sun.shadow.camera.bottom = -70;
sun.shadow.camera.far = 220;
sun.shadow.bias = -0.0006;
scene.add(sun);

// ---------------------------------------------------------------------------
// Terrain: gentle height variation, flat near the castle
// ---------------------------------------------------------------------------
function terrainHeight(x, z) {
  const d = Math.hypot(x, z);
  if (d < 30) return 0; // flat castle ground
  const t = Math.min((d - 30) / 40, 1); // fade the hills in
  return (
    t *
    (Math.sin(x * 0.08) * Math.cos(z * 0.06) * 1.4 +
      Math.sin((x + z) * 0.05) * 0.8)
  );
}

const groundGeo = new THREE.PlaneGeometry(240, 240, 72, 72);
groundGeo.rotateX(-Math.PI / 2);
{
  const pos = groundGeo.attributes.position;
  for (let i = 0; i < pos.count; i++) {
    pos.setY(i, terrainHeight(pos.getX(i), pos.getZ(i)));
  }
  groundGeo.computeVertexNormals();
}
const ground = new THREE.Mesh(
  groundGeo,
  new THREE.MeshStandardMaterial({ color: 0x5f9150, roughness: 1 }),
);
ground.receiveShadow = true;
scene.add(ground);

// Faint grid over the flat castle area, for a building-game feel.
const grid = new THREE.GridHelper(60, 30, 0x35592f, 0x35592f);
grid.material.transparent = true;
grid.material.opacity = 0.1;
grid.position.y = 0.04;
scene.add(grid);

// Stone courtyard disc inside the walls.
const courtyard = new THREE.Mesh(
  new THREE.CircleGeometry(13, 40),
  new THREE.MeshStandardMaterial({ color: 0x8f8a7c, roughness: 1 }),
);
courtyard.rotation.x = -Math.PI / 2;
courtyard.position.y = 0.03;
courtyard.receiveShadow = true;
scene.add(courtyard);

// Dirt path from the gate (south side) out into the fields.
const path = new THREE.Mesh(
  new THREE.PlaneGeometry(4.5, 30),
  new THREE.MeshStandardMaterial({ color: 0xa68a5e, roughness: 1 }),
);
path.rotation.x = -Math.PI / 2;
path.position.set(0, 0.05, 33);
path.receiveShadow = true;
scene.add(path);

// ---------------------------------------------------------------------------
// Shared materials and small builders
// ---------------------------------------------------------------------------
const stoneMat = new THREE.MeshStandardMaterial({
  color: 0x9b9a90,
  roughness: 0.95,
});
const stoneDarkMat = new THREE.MeshStandardMaterial({
  color: 0x83827a,
  roughness: 0.95,
});
const woodMat = new THREE.MeshStandardMaterial({
  color: 0x8a6134,
  roughness: 0.9,
});
const darkMat = new THREE.MeshStandardMaterial({
  color: 0x2e2a24,
  roughness: 1,
});

function box(w, h, d, mat, x, y, z, parent = scene) {
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
  return m;
}

function cylinder(rt, rb, h, mat, x, y, z, parent = scene, segments = 16) {
  const m = new THREE.Mesh(new THREE.CylinderGeometry(rt, rb, h, segments), mat);
  m.position.set(x, y, z);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
  return m;
}

// Crenellations (merlons) along a wall running in X.
function addMerlonsX(parent, cx, topY, length, z, mat = stoneMat) {
  const n = Math.max(1, Math.floor(length / 1.4));
  for (let i = 0; i < n; i++) {
    const x = cx - length / 2 + (i + 0.5) * (length / n);
    box(0.7, 0.6, 1.5, mat, x, topY + 0.3, z, parent);
  }
}

// Crenellations along a wall running in Z.
function addMerlonsZ(parent, cz, topY, length, x, mat = stoneMat) {
  const n = Math.max(1, Math.floor(length / 1.4));
  for (let i = 0; i < n; i++) {
    const z = cz - length / 2 + (i + 0.5) * (length / n);
    box(1.5, 0.6, 0.7, mat, x, topY + 0.3, z, parent);
  }
}

// ---------------------------------------------------------------------------
// Selection: every named building gets cloned materials so we can tint it
// ---------------------------------------------------------------------------
const selectables = [];

function makeSelectable(group, name) {
  group.userData.selectName = name;
  group.traverse((o) => {
    if (o.isMesh) {
      o.material = o.material.clone();
      o.userData.selectRoot = group;
    }
  });
  selectables.push(group);
}

let selected = null;
const selectionBox = new THREE.BoxHelper(undefined, 0xffd34d);
selectionBox.visible = false;
scene.add(selectionBox);

const selectedNameEl = document.getElementById('selected-name');

function select(group) {
  deselect();
  selected = group;
  group.traverse((o) => {
    if (o.isMesh && o.material.emissive) {
      o.material.emissive.setHex(0x7a5c00);
    }
  });
  selectionBox.setFromObject(group);
  selectionBox.visible = true;
  selectedNameEl.textContent = 'Selected: ' + group.userData.selectName;
}

function deselect() {
  if (!selected) return;
  selected.traverse((o) => {
    if (o.isMesh && o.material.emissive) {
      o.material.emissive.setHex(0x000000);
    }
  });
  selected = null;
  selectionBox.visible = false;
  selectedNameEl.textContent = 'Click a building to select it';
}

// ---------------------------------------------------------------------------
// The castle: keep, walls, corner towers, gate
// ---------------------------------------------------------------------------
const WALL_H = 4.5;
const HALF = 18; // half side of the square wall ring

// Keep: tall central tower with a flag.
const keep = new THREE.Group();
box(10, 2, 10, stoneDarkMat, 0, 1, 0, keep); // base plinth
box(8, 13, 8, stoneMat, 0, 8.5, 0, keep); // tower body
box(9, 0.8, 9, stoneDarkMat, 0, 15.4, 0, keep); // top slab
addMerlonsX(keep, 0, 15.8, 8, -4.2);
addMerlonsX(keep, 0, 15.8, 8, 4.2);
addMerlonsZ(keep, 0, 15.8, 8, -4.2);
addMerlonsZ(keep, 0, 15.8, 8, 4.2);
// Small dark windows on the tower faces.
box(1, 1.6, 0.2, darkMat, -2, 10, 4.05, keep);
box(1, 1.6, 0.2, darkMat, 2, 12, 4.05, keep);
box(1, 1.6, 0.2, darkMat, -2, 10, -4.05, keep);
box(0.2, 1.6, 1, darkMat, 4.05, 11, 0, keep);
box(0.2, 1.6, 1, darkMat, -4.05, 12, 0, keep);
// Flag pole and waving flag.
cylinder(0.12, 0.12, 5.2, woodMat, 0, 18.4, 0, keep, 8);
const flagShape = new THREE.Shape();
flagShape.moveTo(0, 0);
flagShape.lineTo(3.4, 0.95);
flagShape.lineTo(0, 1.9);
flagShape.lineTo(0, 0);
const flag = new THREE.Mesh(
  new THREE.ShapeGeometry(flagShape),
  new THREE.MeshStandardMaterial({
    color: 0xd23b2e,
    side: THREE.DoubleSide,
    roughness: 0.8,
  }),
);
flag.position.set(0.12, 19.4, 0);
flag.castShadow = true;
keep.add(flag);
scene.add(keep);
makeSelectable(keep, 'Stone Keep');

// Wall ring. North wall is solid, east and west are solid, south has a gate gap.
const northWall = new THREE.Group();
box(37.4, WALL_H, 1.4, stoneMat, 0, WALL_H / 2, -HALF, northWall);
addMerlonsX(northWall, 0, WALL_H, 37.4, -HALF);
scene.add(northWall);
makeSelectable(northWall, 'North Wall');

const eastWall = new THREE.Group();
box(1.4, WALL_H, 34.6, stoneMat, HALF, WALL_H / 2, 0, eastWall);
addMerlonsZ(eastWall, 0, WALL_H, 34.6, HALF);
scene.add(eastWall);
makeSelectable(eastWall, 'East Wall');

const westWall = new THREE.Group();
box(1.4, WALL_H, 34.6, stoneMat, -HALF, WALL_H / 2, 0, westWall);
addMerlonsZ(westWall, 0, WALL_H, 34.6, -HALF);
scene.add(westWall);
makeSelectable(westWall, 'West Wall');

const southWall = new THREE.Group();
box(15.7, WALL_H, 1.4, stoneMat, -10.85, WALL_H / 2, HALF, southWall);
box(15.7, WALL_H, 1.4, stoneMat, 10.85, WALL_H / 2, HALF, southWall);
addMerlonsX(southWall, -10.85, WALL_H, 15.7, HALF);
addMerlonsX(southWall, 10.85, WALL_H, 15.7, HALF);
scene.add(southWall);
makeSelectable(southWall, 'South Wall');

// Gatehouse: wooden posts and beam over the gap in the south wall.
const gate = new THREE.Group();
box(0.9, 5.6, 0.9, woodMat, -3.3, 2.8, HALF, gate);
box(0.9, 5.6, 0.9, woodMat, 3.3, 2.8, HALF, gate);
box(7.5, 0.9, 1.1, woodMat, 0, 5.6, HALF, gate);
box(5.6, 4.6, 0.3, new THREE.MeshStandardMaterial({ color: 0x6e4a22, roughness: 0.9 }), 0, 2.3, HALF, gate);
scene.add(gate);
makeSelectable(gate, 'Gatehouse');

// Corner towers: cylinders with a cap ring and merlons.
function cornerTower(x, z) {
  const g = new THREE.Group();
  cylinder(2.4, 2.6, 7.5, stoneMat, x, 3.75, z, g, 18);
  cylinder(2.75, 2.75, 0.7, stoneDarkMat, x, 7.6, z, g, 18);
  for (let i = 0; i < 8; i++) {
    const a = (i / 8) * Math.PI * 2;
    box(0.7, 0.6, 0.7, stoneMat, x + Math.cos(a) * 2.4, 8.25, z + Math.sin(a) * 2.4, g);
  }
  scene.add(g);
  makeSelectable(g, 'Corner Tower');
  return g;
}
cornerTower(-HALF, -HALF);
cornerTower(HALF, -HALF);
cornerTower(-HALF, HALF);
cornerTower(HALF, HALF);

// ---------------------------------------------------------------------------
// Village: houses, trees, rocks
// ---------------------------------------------------------------------------
const houseColors = [0xd9a066, 0xc98f5f, 0xe0b070, 0xb98a5a, 0xdba47a, 0xcf9a68];
const roofColors = [0x8a4b2d, 0x7a3b22, 0x96482a, 0x6e3a24, 0x8a4026, 0x7d3f28];

function house(x, z, i) {
  const g = new THREE.Group();
  const wallMat = new THREE.MeshStandardMaterial({
    color: houseColors[i % houseColors.length],
    roughness: 0.9,
  });
  const roofMat = new THREE.MeshStandardMaterial({
    color: roofColors[i % roofColors.length],
    roughness: 0.95,
  });
  const y = terrainHeight(x, z);
  box(4.5, 3, 4, wallMat, x, y + 1.5, z, g);
  const roof = new THREE.Mesh(new THREE.ConeGeometry(3.6, 2.4, 4), roofMat);
  roof.position.set(x, y + 4.2, z);
  roof.rotation.y = Math.PI / 4;
  roof.castShadow = true;
  roof.receiveShadow = true;
  g.add(roof);
  box(1, 1.8, 0.2, darkMat, x, y + 0.9, z + 2.05, g); // door
  scene.add(g);
  makeSelectable(g, 'House');
  return g;
}

house(-30, 6, 0);
house(-34, -16, 1);
house(28, -22, 2);
house(36, 8, 3);
house(26, 32, 4);
house(-28, 28, 5);

const treeSpots = [
  [-42, -8], [-46, 14], [-38, -34], [42, -30], [48, -6],
  [44, 26], [-44, 34], [14, -42], [-12, 46], [58, 12],
];

function tree(x, z, s) {
  const g = new THREE.Group();
  const y = terrainHeight(x, z);
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x6e4a22, roughness: 1 });
  const leafMat = new THREE.MeshStandardMaterial({ color: 0x3f7a33, roughness: 1 });
  cylinder(0.28 * s, 0.36 * s, 1.8 * s, trunkMat, x, y + 0.9 * s, z, g, 8);
  const cone = new THREE.Mesh(new THREE.ConeGeometry(1.9 * s, 3.6 * s, 8), leafMat);
  cone.position.set(x, y + 3.4 * s, z);
  cone.castShadow = true;
  cone.receiveShadow = true;
  g.add(cone);
  scene.add(g);
  makeSelectable(g, 'Tree');
  return g;
}
treeSpots.forEach(([x, z], i) => tree(x, z, 0.85 + (i % 4) * 0.15));

const rockSpots = [
  [-52, -22, 1.4], [52, 34, 1.1], [-8, -52, 1.7], [20, 52, 1.2], [-58, 2, 1.0],
];

function rock(x, z, r) {
  const g = new THREE.Group();
  const m = new THREE.Mesh(
    new THREE.DodecahedronGeometry(r, 0),
    new THREE.MeshStandardMaterial({ color: 0x8d8d85, roughness: 1 }),
  );
  m.position.set(x, terrainHeight(x, z) + r * 0.45, z);
  m.rotation.set(Math.random() * 0.6, Math.random() * Math.PI, Math.random() * 0.6);
  m.castShadow = true;
  m.receiveShadow = true;
  g.add(m);
  scene.add(g);
  makeSelectable(g, 'Rock');
  return g;
}
rockSpots.forEach(([x, z, r]) => rock(x, z, r));

// ---------------------------------------------------------------------------
// HUD
// ---------------------------------------------------------------------------
const resEls = {
  wood: document.getElementById('res-wood'),
  stone: document.getElementById('res-stone'),
  gold: document.getElementById('res-gold'),
  food: document.getElementById('res-food'),
  population: document.getElementById('pop-count'),
};
const waveStatusEl = document.getElementById('wave-status');
const buildBtn = document.getElementById('btn-build-wall');
const waveBtn = document.getElementById('btn-next-wave');

function updateHUD() {
  resEls.wood.textContent = state.wood;
  resEls.stone.textContent = state.stone;
  resEls.gold.textContent = state.gold;
  resEls.food.textContent = state.food;
  resEls.population.textContent = state.population;
}

waveBtn.addEventListener('click', () => {
  state.wave += 1;
  waveStatusEl.textContent = 'Wave ' + state.wave + ' incoming soon';
});

buildBtn.addEventListener('click', () => {
  state.placingWall = !state.placingWall;
  buildBtn.classList.toggle('active', state.placingWall);
  buildBtn.textContent = state.placingWall
    ? 'Placing wall, click ground (Esc to cancel)'
    : 'Build Wall (10 Stone)';
  ghost.visible = false;
  if (!state.placingWall) deselect();
});

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && state.placingWall) buildBtn.click();
});

// ---------------------------------------------------------------------------
// Picking: click to select, placement mode drops a wall segment
// ---------------------------------------------------------------------------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const hitPoint = new THREE.Vector3();

// Ghost preview while placing a wall.
const ghost = new THREE.Group();
{
  const ghostMat = new THREE.MeshStandardMaterial({
    color: 0x7ec850,
    transparent: true,
    opacity: 0.55,
    roughness: 0.9,
  });
  const gBox = new THREE.Mesh(new THREE.BoxGeometry(4, 3.2, 1.2), ghostMat);
  gBox.position.y = 1.6;
  ghost.add(gBox);
  const gTop = new THREE.Mesh(new THREE.BoxGeometry(4, 0.6, 1.2), ghostMat);
  gTop.position.y = 3.5;
  ghost.add(gTop);
  ghost.visible = false;
  scene.add(ghost);
}

function setPointerFromEvent(e) {
  pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
}

function groundPointFromEvent(e) {
  setPointerFromEvent(e);
  raycaster.setFromCamera(pointer, camera);
  return raycaster.ray.intersectPlane(groundPlane, hitPoint);
}

function placeWallAt(x, z) {
  if (state.stone < WALL_COST_STONE) {
    waveStatusEl.textContent = 'Not enough stone to build a wall';
    return false;
  }
  state.stone -= WALL_COST_STONE;
  const gx = Math.round(x / 2) * 2;
  const gz = Math.round(z / 2) * 2;
  const gy = terrainHeight(gx, gz);
  const g = new THREE.Group();
  box(4, 3.2, 1.2, stoneMat, gx, gy + 1.6, gz, g);
  addMerlonsX(g, gx, gy + 3.2, 4, gz);
  scene.add(g);
  makeSelectable(g, 'Wall Segment');
  updateHUD();
  waveStatusEl.textContent = 'Wall built at ' + gx + ', ' + gz;
  return true;
}

renderer.domElement.addEventListener('pointermove', (e) => {
  if (!state.placingWall) return;
  const p = groundPointFromEvent(e);
  if (!p) {
    ghost.visible = false;
    return;
  }
  ghost.position.set(Math.round(p.x / 2) * 2, terrainHeight(p.x, p.z), Math.round(p.z / 2) * 2);
  ghost.visible = true;
  ghost.children.forEach((c) => {
    c.material.color.setHex(state.stone >= WALL_COST_STONE ? 0x7ec850 : 0xd23b2e);
  });
});

// Distinguish a click from an orbit drag.
let downX = 0;
let downY = 0;
renderer.domElement.addEventListener('pointerdown', (e) => {
  downX = e.clientX;
  downY = e.clientY;
});
renderer.domElement.addEventListener('pointerup', (e) => {
  if (Math.hypot(e.clientX - downX, e.clientY - downY) > 5) return; // it was a drag
  if (state.placingWall) {
    const p = groundPointFromEvent(e);
    if (p) placeWallAt(p.x, p.z);
    return;
  }
  setPointerFromEvent(e);
  raycaster.setFromCamera(pointer, camera);
  const hits = raycaster.intersectObjects(selectables, true);
  if (hits.length > 0) {
    const root = hits[0].object.userData.selectRoot;
    if (root) select(root);
  } else {
    deselect();
  }
});

// ---------------------------------------------------------------------------
// Resize + render loop
// ---------------------------------------------------------------------------
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

const clock = new THREE.Clock();

function animate() {
  requestAnimationFrame(animate);
  const t = clock.getElapsedTime();
  // Gentle flag wave.
  flag.rotation.y = Math.sin(t * 2.2) * 0.18;
  controls.update();
  renderer.render(scene, camera);
}

updateHUD();
animate();
