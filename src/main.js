// Castle Siege 3D - Phase 2: economy + enemy waves
// A Stronghold-style castle builder scene: procedural low-poly geometry only,
// no external models, images or audio. Three.js + OrbitControls, bundled by Vite.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// ---------------------------------------------------------------------------
// Audio: sound effects and background music (Phase 3)
// All files are bundled locally in public/audio/. Audio starts only after
// the player's first interaction (browser autoplay rules). M or the Sound
// button toggles mute; the choice is saved in localStorage.
// ---------------------------------------------------------------------------
const AUDIO_BASE = import.meta.env.BASE_URL + 'audio/';

const SOUND_DEFS = {
  shoot: { file: 'shoot.mp3', volume: 0.55, pool: 4 },
  hit: { file: 'hit.mp3', volume: 0.6, pool: 3 },
  death: { file: 'death.mp3', volume: 0.6, pool: 2 },
  build: { file: 'build.mp3', volume: 0.6, pool: 2 },
  horn: { file: 'horn.mp3', volume: 0.7, pool: 1 },
  victory: { file: 'victory.mp3', volume: 0.6, pool: 1 },
  thud: { file: 'thud.mp3', volume: 0.6, pool: 2 },
  gameover: { file: 'gameover.mp3', volume: 0.6, pool: 1 },
  click: { file: 'click.mp3', volume: 0.5, pool: 2 },
};

const soundPools = {}; // name -> { elements: HTMLAudioElement[], next: 0 }
let audioUnlocked = false;
let musicEl = null;
let muted = false;
try {
  muted = window.localStorage.getItem('castle-siege-muted') === '1';
} catch (err) {
  muted = false; // storage unavailable, mute still applies for this session
}

const soundBtn = document.getElementById('btn-sound');

function updateSoundButton() {
  if (!soundBtn) return;
  soundBtn.textContent = muted ? 'Sound: Off' : 'Sound: On';
}

function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  for (const [name, def] of Object.entries(SOUND_DEFS)) {
    const elements = [];
    for (let i = 0; i < def.pool; i++) {
      const el = new Audio(AUDIO_BASE + def.file);
      el.preload = 'auto';
      el.volume = def.volume;
      elements.push(el);
    }
    soundPools[name] = { elements, next: 0 };
  }
  musicEl = new Audio(AUDIO_BASE + 'music.mp3');
  musicEl.preload = 'auto';
  musicEl.loop = true;
  musicEl.volume = 0.35;
  if (!muted) {
    musicEl.play().catch(() => {});
  }
  updateSoundButton();
}

function playSound(name) {
  if (!audioUnlocked || muted) return;
  const pool = soundPools[name];
  if (!pool) return;
  const el = pool.elements[pool.next];
  pool.next = (pool.next + 1) % pool.elements.length;
  el.currentTime = 0;
  el.play().catch(() => {});
}

function toggleMute() {
  muted = !muted;
  try {
    window.localStorage.setItem('castle-siege-muted', muted ? '1' : '0');
  } catch (err) {
    // storage unavailable, mute still applies for this session
  }
  if (musicEl) {
    if (muted) musicEl.pause();
    else musicEl.play().catch(() => {});
  }
  updateSoundButton();
}

soundBtn.addEventListener('click', () => {
  unlockAudio();
  toggleMute();
});

// A click on any HUD or game-over button plays the UI click sound.
for (const id of ['hud', 'fallen-overlay']) {
  document.getElementById(id).addEventListener('click', (e) => {
    if (e.target.closest('button')) playSound('click');
  });
}

// First interaction unlocks audio (autoplay rules): pointer or key.
window.addEventListener('pointerdown', unlockAudio, { once: true });
window.addEventListener('keydown', unlockAudio, { once: true });
updateSoundButton();

// ---------------------------------------------------------------------------
// Game state
// ---------------------------------------------------------------------------
const state = {
  wood: 100,
  stone: 80,
  gold: 50,
  food: 60,
  population: 12,
  popCap: 16,
  wave: 0,
  waveActive: false,
  keepHp: 100,
  keepMaxHp: 100,
  kills: 0, // enemies defeated (arrow kills only)
  goldEarned: 0, // total gold gained from income ticks and wave rewards
  houseCount: 0, // houses built by the player (Phase 1 village houses are scenery)
  farmCount: 0,
  placing: null, // null or one of 'wall' | 'house' | 'farm' | 'tower'
};

const COSTS = {
  wall: { stone: 10 },
  house: { wood: 20 },
  farm: { wood: 15 },
  tower: { stone: 30, wood: 10 },
};

const TOWER_RANGE = 26;
const TOWER_FIRE_INTERVAL = 0.8;
const ARROW_SPEED = 32;

// Towers that shoot during waves: { pos: Vector3 (arrow origin), cooldown }
const towers = [];
// Enemies alive right now: { group, hp, speed, phase }
const enemies = [];
// Arrows in flight: { mesh, target }
const arrows = [];
// Buildings the player placed: { kind: 'wall' | 'house' | 'farm' | 'tower', x, z }
// (Phase 4: saved to localStorage so a game can continue after a reload.)
const built = [];

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

// Corner towers: cylinders with a cap ring and merlons. They shoot arrows
// during waves, so each one registers in the towers list.
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
  towers.push({ pos: new THREE.Vector3(x, 8, z), cooldown: 0 });
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
let houseColorIdx = 6; // Phase 1 village used indices 0-5

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
  keepHp: document.getElementById('keep-hp'),
  hpFill: document.getElementById('hp-fill'),
};
const waveStatusEl = document.getElementById('wave-status');
const fallenOverlay = document.getElementById('fallen-overlay');
const fallenWaveEl = document.getElementById('fallen-wave');

function setStatus(text) {
  waveStatusEl.textContent = text;
}

function updateHUD() {
  resEls.wood.textContent = state.wood;
  resEls.stone.textContent = state.stone;
  resEls.gold.textContent = state.gold;
  resEls.food.textContent = state.food;
  resEls.population.textContent = state.population + ' / ' + state.popCap;
  resEls.keepHp.textContent = state.keepHp;
  const pct = Math.max(0, (state.keepHp / state.keepMaxHp) * 100);
  resEls.hpFill.style.width = pct + '%';
  resEls.hpFill.style.background =
    pct > 50 ? '#58b368' : pct > 25 ? '#e0a53a' : '#d23b2e';
  updateScoreLine();
}

document.getElementById('btn-restart').addEventListener('click', () => {
  window.location.reload();
});

// ---------------------------------------------------------------------------
// Economy: passive income tick every 5 seconds
// ---------------------------------------------------------------------------
function incomePerTick() {
  return {
    wood: 2, // lumber
    food: 2 + state.farmCount * 2, // farms
    gold: 3 + state.houseCount, // taxes from houses
    stone: 1, // quarry
  };
}

// ---------------------------------------------------------------------------
// Placement: one mode for wall / house / farm / tower
// ---------------------------------------------------------------------------
const PLACE_DEFS = {
  wall: { label: 'Build Wall (10 Stone)' },
  house: { label: 'Build House (20 Wood)' },
  farm: { label: 'Build Farm (15 Wood)' },
  tower: { label: 'Build Tower (30 Stone, 10 Wood)' },
};
const placeBtns = {
  wall: document.getElementById('btn-build-wall'),
  house: document.getElementById('btn-build-house'),
  farm: document.getElementById('btn-build-farm'),
  tower: document.getElementById('btn-build-tower'),
};

function canAfford(cost) {
  if (cost.wood && state.wood < cost.wood) return false;
  if (cost.stone && state.stone < cost.stone) return false;
  if (cost.gold && state.gold < cost.gold) return false;
  return true;
}

function payCost(cost) {
  if (cost.wood) state.wood -= cost.wood;
  if (cost.stone) state.stone -= cost.stone;
  if (cost.gold) state.gold -= cost.gold;
}

// Ghost preview while placing. Rebuilt per building type.
const ghost = new THREE.Group();
const ghostMat = new THREE.MeshStandardMaterial({
  color: 0x7ec850,
  transparent: true,
  opacity: 0.55,
  roughness: 0.9,
});
ghost.visible = false;
scene.add(ghost);

function setGhostFor(kind) {
  while (ghost.children.length > 0) ghost.remove(ghost.children[0]);
  if (kind === 'wall') {
    const b = new THREE.Mesh(new THREE.BoxGeometry(4, 3.2, 1.2), ghostMat);
    b.position.y = 1.6;
    ghost.add(b);
    const t = new THREE.Mesh(new THREE.BoxGeometry(4, 0.6, 1.2), ghostMat);
    t.position.y = 3.5;
    ghost.add(t);
  } else if (kind === 'house') {
    const b = new THREE.Mesh(new THREE.BoxGeometry(4.5, 3, 4), ghostMat);
    b.position.y = 1.5;
    ghost.add(b);
    const r = new THREE.Mesh(new THREE.ConeGeometry(3.6, 2.4, 4), ghostMat);
    r.position.y = 4.2;
    r.rotation.y = Math.PI / 4;
    ghost.add(r);
  } else if (kind === 'farm') {
    const b = new THREE.Mesh(new THREE.BoxGeometry(6, 0.5, 6), ghostMat);
    b.position.y = 0.25;
    ghost.add(b);
    for (let i = -1; i <= 1; i++) {
      const row = new THREE.Mesh(new THREE.BoxGeometry(5.4, 0.5, 0.8), ghostMat);
      row.position.set(0, 0.6, i * 1.8);
      ghost.add(row);
    }
  } else if (kind === 'tower') {
    const b = new THREE.Mesh(new THREE.CylinderGeometry(1.8, 2, 6, 14), ghostMat);
    b.position.y = 3;
    ghost.add(b);
    const c = new THREE.Mesh(new THREE.CylinderGeometry(2.1, 2.1, 0.6, 14), ghostMat);
    c.position.y = 6.2;
    ghost.add(c);
  }
}

function resetPlaceButtons() {
  for (const [kind, btn] of Object.entries(placeBtns)) {
    btn.classList.remove('active');
    btn.textContent = PLACE_DEFS[kind].label;
  }
}

function cancelPlacing() {
  state.placing = null;
  ghost.visible = false;
  resetPlaceButtons();
  deselect();
}

function togglePlacing(kind) {
  if (state.placing === kind) {
    cancelPlacing();
    return;
  }
  state.placing = kind;
  setGhostFor(kind);
  ghost.visible = false;
  resetPlaceButtons();
  const btn = placeBtns[kind];
  btn.classList.add('active');
  btn.textContent = 'Placing ' + kind + ', click ground (Esc to cancel)';
}

for (const [kind, btn] of Object.entries(placeBtns)) {
  btn.addEventListener('click', () => togglePlacing(kind));
}

window.addEventListener('keydown', (e) => {
  if (e.key === 'Escape' && state.placing) cancelPlacing();
  if (e.key === 'm' || e.key === 'M') {
    unlockAudio();
    toggleMute();
  }
});

function placeWallAt(x, z) {
  const gx = Math.round(x / 2) * 2;
  const gz = Math.round(z / 2) * 2;
  const gy = terrainHeight(gx, gz);
  const g = new THREE.Group();
  box(4, 3.2, 1.2, stoneMat, gx, gy + 1.6, gz, g);
  addMerlonsX(g, gx, gy + 3.2, 4, gz);
  scene.add(g);
  makeSelectable(g, 'Wall Segment');
  built.push({ kind: 'wall', x: gx, z: gz });
  setStatus('Wall built at ' + gx + ', ' + gz);
}

function placeHouseAt(x, z) {
  const gx = Math.round(x / 2) * 2;
  const gz = Math.round(z / 2) * 2;
  house(gx, gz, houseColorIdx++);
  state.houseCount += 1;
  state.popCap += 4;
  built.push({ kind: 'house', x: gx, z: gz });
  setStatus('House built at ' + gx + ', ' + gz + '. Population cap is now ' + state.popCap);
}

function placeFarmAt(x, z) {
  const gx = Math.round(x / 2) * 2;
  const gz = Math.round(z / 2) * 2;
  const gy = terrainHeight(gx, gz);
  const g = new THREE.Group();
  const soilMat = new THREE.MeshStandardMaterial({ color: 0x6e4a22, roughness: 1 });
  const cropMat = new THREE.MeshStandardMaterial({ color: 0x4d8a2f, roughness: 1 });
  box(6, 0.5, 6, soilMat, gx, gy + 0.25, gz, g);
  for (let i = -1; i <= 1; i++) {
    box(5.4, 0.5, 0.8, cropMat, gx, gy + 0.6, gz + i * 1.8, g);
  }
  scene.add(g);
  makeSelectable(g, 'Farm');
  state.farmCount += 1;
  built.push({ kind: 'farm', x: gx, z: gz });
  setStatus('Farm built at ' + gx + ', ' + gz + '. Food income is now +' + (2 + state.farmCount * 2) + ' per tick');
}

function placeTowerAt(x, z) {
  const gx = Math.round(x / 2) * 2;
  const gz = Math.round(z / 2) * 2;
  const gy = terrainHeight(gx, gz);
  const g = new THREE.Group();
  cylinder(1.8, 2, 6, stoneMat, gx, gy + 3, gz, g, 14);
  cylinder(2.1, 2.1, 0.6, stoneDarkMat, gx, gy + 6.2, gz, g, 14);
  for (let i = 0; i < 6; i++) {
    const a = (i / 6) * Math.PI * 2;
    box(0.6, 0.5, 0.6, stoneMat, gx + Math.cos(a) * 1.8, gy + 6.7, gz + Math.sin(a) * 1.8, g);
  }
  scene.add(g);
  makeSelectable(g, 'Tower');
  towers.push({ pos: new THREE.Vector3(gx, gy + 6.5, gz), cooldown: 0 });
  built.push({ kind: 'tower', x: gx, z: gz });
  setStatus('Tower built at ' + gx + ', ' + gz);
}

function placeAt(kind, x, z) {
  if (Math.abs(x) > 55 || Math.abs(z) > 55) {
    setStatus('Too far out, build closer to the castle');
    return false;
  }
  const cost = COSTS[kind];
  if (!canAfford(cost)) {
    setStatus('Not enough resources');
    return false;
  }
  payCost(cost);
  if (kind === 'wall') placeWallAt(x, z);
  else if (kind === 'house') placeHouseAt(x, z);
  else if (kind === 'farm') placeFarmAt(x, z);
  else if (kind === 'tower') placeTowerAt(x, z);
  playSound('build');
  updateHUD();
  return true;
}

// ---------------------------------------------------------------------------
// Enemy waves
// ---------------------------------------------------------------------------
const waveBtn = document.getElementById('btn-next-wave');

const enemyBodyMat = new THREE.MeshStandardMaterial({ color: 0x8a2a22, roughness: 0.9 });
const enemyHeadMat = new THREE.MeshStandardMaterial({ color: 0x5c1d16, roughness: 0.9 });
const enemySkinMat = new THREE.MeshStandardMaterial({ color: 0xd9b48a, roughness: 0.9 });

function createEnemy(x, z, speed) {
  const g = new THREE.Group();
  const y = terrainHeight(x, z);
  box(1.1, 1.5, 0.7, enemyBodyMat, 0, 1.05, 0, g);
  box(0.65, 0.6, 0.65, enemySkinMat, 0, 2.1, 0, g);
  box(0.7, 0.25, 0.7, enemyHeadMat, 0, 2.45, 0, g); // helmet
  box(0.12, 2.2, 0.12, darkMat, 0.7, 1.1, 0, g); // spear
  g.position.set(x, y, z);
  scene.add(g);
  enemies.push({ group: g, hp: 2, speed, phase: Math.random() * Math.PI * 2 });
}

function spawnWave(count) {
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2 + Math.random() * 0.6;
    const r = 66 + Math.random() * 6;
    createEnemy(
      Math.cos(angle) * r,
      Math.sin(angle) * r,
      Math.min(2.4 + state.wave * 0.15, 4),
    );
  }
}

waveBtn.addEventListener('click', () => {
  if (state.keepHp <= 0) return;
  if (state.waveActive) {
    setStatus('Wave ' + state.wave + ' is still raging');
    return;
  }
  cancelPlacing();
  state.wave += 1;
  const count = 3 + (state.wave - 1) * 2;
  state.waveActive = true;
  spawnWave(count);
  playSound('horn');
  setStatus('Wave ' + state.wave + ': ' + count + ' enemies approach');
});

function damageKeep(amount) {
  state.keepHp = Math.max(0, state.keepHp - amount);
  updateHUD();
  if (state.keepHp <= 0) {
    state.waveActive = false;
    playSound('gameover');
    fallenWaveEl.textContent = state.wave;
    fallenOverlay.classList.remove('hidden');
    setStatus('The castle has fallen');
    enableScoreSubmit();
  } else {
    playSound('thud');
  }
}

function removeEnemy(index) {
  const e = enemies[index];
  scene.remove(e.group);
  enemies.splice(index, 1);
}

function killEnemy(index) {
  state.kills += 1;
  removeEnemy(index);
}

function checkWaveEnd() {
  if (!state.waveActive || state.keepHp <= 0) return;
  if (enemies.length === 0) {
    state.waveActive = false;
    state.gold += 20;
    state.goldEarned += 20;
    updateHUD();
    playSound('victory');
    setStatus('Wave ' + state.wave + ' cleared! +20 Gold');
    enableScoreSubmit();
    saveGame(true); // autosave after every wave clear
  }
}

// ---------------------------------------------------------------------------
// Tower shooting and arrows
// ---------------------------------------------------------------------------
const arrowMat = new THREE.MeshStandardMaterial({ color: 0x3a2c18, roughness: 1 });

function fireArrow(tower, target) {
  const mesh = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.12, 1.1), arrowMat);
  mesh.position.copy(tower.pos);
  mesh.castShadow = false;
  scene.add(mesh);
  arrows.push({ mesh, target });
  playSound('shoot');
}

function updateTowers(delta) {
  if (!state.waveActive || state.keepHp <= 0) return;
  for (const t of towers) {
    t.cooldown -= delta;
    if (t.cooldown > 0) continue;
    let best = null;
    let bestD = TOWER_RANGE;
    for (const e of enemies) {
      const d = Math.hypot(
        e.group.position.x - t.pos.x,
        e.group.position.z - t.pos.z,
      );
      if (d < bestD) {
        bestD = d;
        best = e;
      }
    }
    if (best) {
      fireArrow(t, best);
      t.cooldown = TOWER_FIRE_INTERVAL;
    }
  }
}

function updateArrows(delta) {
  for (let i = arrows.length - 1; i >= 0; i--) {
    const a = arrows[i];
    const target = a.target;
    if (!enemies.includes(target)) {
      scene.remove(a.mesh);
      arrows.splice(i, 1);
      continue;
    }
    const tp = target.group.position;
    const dest = new THREE.Vector3(tp.x, tp.y + 1.2, tp.z);
    const dir = dest.clone().sub(a.mesh.position);
    const dist = dir.length();
    if (dist < 1.4) {
      scene.remove(a.mesh);
      arrows.splice(i, 1);
      target.hp -= 1;
      if (target.hp <= 0) {
        const idx = enemies.indexOf(target);
        if (idx >= 0) killEnemy(idx);
        playSound('death');
      } else {
        playSound('hit');
      }
      continue;
    }
    dir.normalize();
    a.mesh.position.addScaledVector(dir, ARROW_SPEED * delta);
    a.mesh.lookAt(dest);
  }
}

// ---------------------------------------------------------------------------
// Enemy movement: walk toward the keep, strike it on arrival
// ---------------------------------------------------------------------------
function updateEnemies(delta, elapsed) {
  if (state.keepHp <= 0) return;
  for (let i = enemies.length - 1; i >= 0; i--) {
    const e = enemies[i];
    const p = e.group.position;
    const dx = -p.x;
    const dz = -p.z;
    const d = Math.hypot(dx, dz);
    if (d < 12) {
      damageKeep(10);
      removeEnemy(i);
      if (state.keepHp > 0) {
        setStatus('An enemy struck the keep! Keep HP ' + state.keepHp);
      }
      continue;
    }
    const step = e.speed * delta;
    p.x += (dx / d) * step;
    p.z += (dz / d) * step;
    p.y = terrainHeight(p.x, p.z) + Math.abs(Math.sin(elapsed * 6 + e.phase)) * 0.12;
    e.group.rotation.y = Math.atan2(dx, dz);
  }
}

// ---------------------------------------------------------------------------
// Picking: click to select, placement mode drops a building
// ---------------------------------------------------------------------------
const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const groundPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const hitPoint = new THREE.Vector3();

function setPointerFromEvent(e) {
  pointer.x = (e.clientX / window.innerWidth) * 2 - 1;
  pointer.y = -(e.clientY / window.innerHeight) * 2 + 1;
}

function groundPointFromEvent(e) {
  setPointerFromEvent(e);
  raycaster.setFromCamera(pointer, camera);
  return raycaster.ray.intersectPlane(groundPlane, hitPoint);
}

renderer.domElement.addEventListener('pointermove', (e) => {
  if (!state.placing) return;
  const p = groundPointFromEvent(e);
  if (!p) {
    ghost.visible = false;
    return;
  }
  ghost.position.set(
    Math.round(p.x / 2) * 2,
    terrainHeight(p.x, p.z),
    Math.round(p.z / 2) * 2,
  );
  ghost.visible = true;
  ghostMat.color.setHex(canAfford(COSTS[state.placing]) ? 0x7ec850 : 0xd23b2e);
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
  if (state.placing) {
    const p = groundPointFromEvent(e);
    if (p) placeAt(state.placing, p.x, p.z);
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
// Save game + leaderboard (Phase 4)
// Save: localStorage, autosaved after every wave clear, plus a Save button.
// A corrupt or out-of-date save is ignored and the game starts fresh.
// Leaderboard: a small Node API (see server/). The game talks to it with
// fetch; if the server is unreachable the panel shows scores saved on this
// device instead, clearly marked as local.
// ---------------------------------------------------------------------------
const SAVE_KEY = 'castle-siege-save-v1';
const LOCAL_SCORES_KEY = 'castle-siege-local-scores-v1';
const DEFAULT_API_BASE = 'https://castle-siege-3d-api.onrender.com';
let apiBase = import.meta.env.VITE_LEADERBOARD_API_URL || DEFAULT_API_BASE;
let gameStarted = true; // false while the Continue / New Game overlay is up
let canSubmit = false;
let boardServerOk = false;

const startOverlay = document.getElementById('start-overlay');
const saveSummaryEl = document.getElementById('save-summary');
const scoreLineEl = document.getElementById('score-line');
const lbPanel = document.getElementById('leaderboard-panel');
const lbList = document.getElementById('leaderboard-list');
const lbNote = document.getElementById('leaderboard-note');
const scoreNameInput = document.getElementById('score-name');
const submitScoreBtn = document.getElementById('btn-submit-score');
const scoreStatusEl = document.getElementById('score-status');
const fallenNameInput = document.getElementById('fallen-name');
const submitFallenBtn = document.getElementById('btn-submit-fallen');
const fallenScoreStatusEl = document.getElementById('fallen-score-status');

function isFiniteNumber(n, min, max) {
  return typeof n === 'number' && Number.isFinite(n) && n >= min && n <= max;
}

function collectSave() {
  return {
    v: 1,
    savedAt: Date.now(),
    wood: state.wood,
    stone: state.stone,
    gold: state.gold,
    food: state.food,
    population: state.population,
    popCap: state.popCap,
    wave: state.wave,
    keepHp: state.keepHp,
    kills: state.kills,
    goldEarned: state.goldEarned,
    houseCount: state.houseCount,
    farmCount: state.farmCount,
    houseColorIdx,
    buildings: built.map((b) => ({ kind: b.kind, x: b.x, z: b.z })),
  };
}

function saveGame(quiet) {
  try {
    window.localStorage.setItem(SAVE_KEY, JSON.stringify(collectSave()));
    if (!quiet) setStatus('Game saved. Wave ' + state.wave + ', Keep HP ' + state.keepHp);
    return true;
  } catch (err) {
    if (!quiet) setStatus('Could not save the game in this browser');
    return false;
  }
}

function loadSave() {
  let raw;
  try {
    raw = window.localStorage.getItem(SAVE_KEY);
  } catch (err) {
    return null;
  }
  if (!raw) return null;
  let save;
  try {
    save = JSON.parse(raw);
  } catch (err) {
    return null; // corrupt save, start fresh
  }
  if (!save || save.v !== 1 || typeof save !== 'object') return null;
  const nums = [
    ['wood', 0, 100000],
    ['stone', 0, 100000],
    ['gold', 0, 100000],
    ['food', 0, 100000],
    ['population', 0, 1000],
    ['popCap', 4, 1000],
    ['wave', 0, 100],
    ['keepHp', 1, 100],
    ['kills', 0, 100000],
    ['goldEarned', 0, 10000000],
    ['houseCount', 0, 200],
    ['farmCount', 0, 200],
    ['houseColorIdx', 6, 1000],
  ];
  for (const [key, min, max] of nums) {
    if (!isFiniteNumber(save[key], min, max)) return null;
  }
  if (!Array.isArray(save.buildings) || save.buildings.length > 200) return null;
  for (const b of save.buildings) {
    if (!b || !['wall', 'house', 'farm', 'tower'].includes(b.kind)) return null;
    if (!isFiniteNumber(b.x, -60, 60) || !isFiniteNumber(b.z, -60, 60)) return null;
  }
  return save;
}

function clearSave() {
  try {
    window.localStorage.removeItem(SAVE_KEY);
  } catch (err) {
    // storage unavailable, nothing to clear
  }
}

function applySave(save) {
  // Rebuild player buildings from the base counts, then apply the rest.
  state.houseCount = 0;
  state.farmCount = 0;
  state.popCap = 16;
  houseColorIdx = 6;
  built.length = 0;
  for (const b of save.buildings) {
    if (b.kind === 'wall') placeWallAt(b.x, b.z);
    else if (b.kind === 'house') placeHouseAt(b.x, b.z);
    else if (b.kind === 'farm') placeFarmAt(b.x, b.z);
    else if (b.kind === 'tower') placeTowerAt(b.x, b.z);
  }
  state.wood = save.wood;
  state.stone = save.stone;
  state.gold = save.gold;
  state.food = save.food;
  state.population = save.population;
  state.popCap = save.popCap;
  state.wave = save.wave;
  state.keepHp = save.keepHp;
  state.kills = save.kills;
  state.goldEarned = save.goldEarned;
  state.houseCount = save.houseCount;
  state.farmCount = save.farmCount;
  houseColorIdx = save.houseColorIdx;
  state.waveActive = false;
  updateHUD();
  setStatus('Save loaded. Wave ' + state.wave + ' continues, Keep HP ' + state.keepHp);
}

document.getElementById('btn-save').addEventListener('click', () => {
  unlockAudio();
  saveGame(false);
  playSound('click');
});

document.getElementById('btn-continue').addEventListener('click', () => {
  const save = loadSave();
  if (save) applySave(save);
  startOverlay.classList.add('hidden');
  gameStarted = true;
});

document.getElementById('btn-new-game').addEventListener('click', () => {
  clearSave();
  startOverlay.classList.add('hidden');
  gameStarted = true;
  setStatus('New game. Wave 0, no enemies yet');
});

// Show the Continue overlay when a save exists, otherwise start right away.
{
  const existing = loadSave();
  if (existing) {
    gameStarted = false;
    const when = existing.savedAt
      ? new Date(existing.savedAt).toLocaleString()
      : 'an earlier session';
    saveSummaryEl.textContent =
      'Saved game from ' + when + ': Wave ' + existing.wave +
      ', Keep HP ' + existing.keepHp + ', Gold ' + existing.gold +
      ', ' + existing.buildings.length + ' buildings placed.';
    startOverlay.classList.remove('hidden');
  }
}

// ---------------------------------------------------------------------------
// Leaderboard
// ---------------------------------------------------------------------------
function updateScoreLine() {
  if (!scoreLineEl) return;
  scoreLineEl.textContent =
    'Your score: Wave ' + state.wave +
    ', ' + state.kills + ' kills, ' + state.goldEarned + ' gold';
}

function updateSubmitButtons() {
  const enabled = canSubmit && state.wave > 0;
  submitScoreBtn.disabled = !enabled;
  submitFallenBtn.disabled = !enabled;
  if (enabled) {
    scoreStatusEl.textContent = 'Submit your score to the leaderboard.';
    fallenScoreStatusEl.textContent = '';
  } else if (state.wave === 0) {
    scoreStatusEl.textContent = 'Clear a wave to submit your score.';
  }
}

function enableScoreSubmit() {
  canSubmit = true;
  updateSubmitButtons();
}

function compareLocalScores(a, b) {
  if (b.waves !== a.waves) return b.waves - a.waves;
  if (b.kills !== a.kills) return b.kills - a.kills;
  if (b.gold !== a.gold) return b.gold - a.gold;
  return new Date(a.created_at) - new Date(b.created_at);
}

function readLocalScores() {
  try {
    const rows = JSON.parse(window.localStorage.getItem(LOCAL_SCORES_KEY) || '[]');
    return Array.isArray(rows) ? rows : [];
  } catch (err) {
    return [];
  }
}

function addLocalScore(entry) {
  const rows = readLocalScores();
  rows.push({ ...entry, created_at: new Date().toISOString() });
  rows.sort(compareLocalScores);
  try {
    window.localStorage.setItem(LOCAL_SCORES_KEY, JSON.stringify(rows.slice(0, 10)));
  } catch (err) {
    // storage unavailable, local fallback just stays empty
  }
}

function renderBoard(scores) {
  lbList.replaceChildren();
  if (scores.length === 0) {
    const li = document.createElement('li');
    li.textContent = 'No scores yet. Be the first to clear a wave.';
    lbList.appendChild(li);
    return;
  }
  for (const s of scores) {
    const li = document.createElement('li');
    const rank = document.createElement('b');
    rank.textContent = '#' + s.rank + ' ';
    li.appendChild(rank);
    li.appendChild(document.createTextNode(
      s.name + '  Wave ' + s.waves + ', ' + s.kills + ' kills, ' + s.gold + ' gold',
    ));
    lbList.appendChild(li);
  }
}

async function fetchBoard() {
  lbNote.textContent = 'Waking up the leaderboard server, this can take a minute...';
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 70000);
  try {
    const res = await fetch(apiBase + '/api/scores?limit=10', { signal: controller.signal });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    boardServerOk = true;
    renderBoard(data.scores || []);
    lbNote.textContent = 'Top 10 players, from the server.';
  } catch (err) {
    boardServerOk = false;
    renderBoard(
      readLocalScores().map((s, i) => ({ ...s, rank: i + 1 })),
    );
    lbNote.textContent = 'Leaderboard server is unreachable, showing scores saved on this device.';
  } finally {
    clearTimeout(timer);
  }
}

async function submitScore(name) {
  if (!canSubmit || state.wave === 0) {
    scoreStatusEl.textContent = 'Clear a wave to submit your score.';
    return;
  }
  const entry = {
    name: (name || '').trim() || 'Anonymous',
    waves: state.wave,
    kills: state.kills,
    gold: state.goldEarned,
  };
  submitScoreBtn.disabled = true;
  submitFallenBtn.disabled = true;
  scoreStatusEl.textContent = 'Submitting...';
  fallenScoreStatusEl.textContent = 'Submitting...';
  try {
    const res = await fetch(apiBase + '/api/scores', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(entry),
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    const data = await res.json();
    canSubmit = false;
    addLocalScore(entry);
    const msg = 'Score submitted' + (data.rank ? ', rank #' + data.rank : '') + '.';
    scoreStatusEl.textContent = msg;
    fallenScoreStatusEl.textContent = msg;
    fetchBoard();
  } catch (err) {
    canSubmit = false;
    addLocalScore(entry);
    const msg = 'Server unreachable, your score was saved on this device.';
    scoreStatusEl.textContent = msg;
    fallenScoreStatusEl.textContent = msg;
    fetchBoard();
  }
  updateSubmitButtons();
}

submitScoreBtn.addEventListener('click', () => {
  unlockAudio();
  submitScore(scoreNameInput.value);
});
submitFallenBtn.addEventListener('click', () => {
  unlockAudio();
  submitScore(fallenNameInput.value);
});
document.getElementById('btn-refresh-board').addEventListener('click', () => {
  unlockAudio();
  fetchBoard();
});
document.getElementById('btn-leaderboard').addEventListener('click', () => {
  unlockAudio();
  lbPanel.classList.toggle('hidden');
  if (!lbPanel.classList.contains('hidden') && !boardServerOk) fetchBoard();
});

updateScoreLine();
updateSubmitButtons();
fetchBoard();

// ---------------------------------------------------------------------------
// Resize + render loop
// ---------------------------------------------------------------------------
window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});

const clock = new THREE.Clock();
let elapsed = 0;
let incomeTimer = 0;

function animate() {
  requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.1);
  elapsed += delta;
  // Gentle flag wave.
  flag.rotation.y = Math.sin(elapsed * 2.2) * 0.18;
  // Economy tick every 5 seconds. Paused while the Continue / New Game
  // overlay is up so resources do not grow before the player chooses.
  incomeTimer += delta;
  if (incomeTimer >= 5) {
    incomeTimer -= 5;
    if (gameStarted) {
      const inc = incomePerTick();
      state.wood += inc.wood;
      state.food += inc.food;
      state.gold += inc.gold;
      state.goldEarned += inc.gold;
      state.stone += inc.stone;
      updateHUD();
    }
  }
  updateTowers(delta);
  updateArrows(delta);
  updateEnemies(delta, elapsed);
  checkWaveEnd();
  controls.update();
  renderer.render(scene, camera);
}

// Small debug handle used by automated tests (harmless in normal play).
window.__castle = {
  state,
  enemies,
  towers,
  arrows,
  built,
  incomePerTick,
  save: {
    collect: collectSave,
    save: saveGame,
    load: loadSave,
    apply: applySave,
    clear: clearSave,
    isStarted: () => gameStarted,
    canSubmit: () => canSubmit,
  },
  leaderboard: {
    getApiBase: () => apiBase,
    setApiBase: (url) => { apiBase = url; },
    fetchBoard,
    submitScore,
    enableSubmit: enableScoreSubmit,
    serverOk: () => boardServerOk,
  },
  audio: {
    isUnlocked: () => audioUnlocked,
    isMuted: () => muted,
    musicPaused: () => (musicEl ? musicEl.paused : true),
    poolSizes: () => Object.fromEntries(
      Object.entries(soundPools).map(([k, v]) => [k, v.elements.length]),
    ),
    poolState: (name) => (soundPools[name] || { elements: [] }).elements.map(
      (el) => ({ paused: el.paused, time: el.currentTime, src: el.currentSrc.split('/').pop() }),
    ),
  },
};

updateHUD();
animate();
