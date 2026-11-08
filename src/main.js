// Castle Siege 3D - graphics upgrade (Phase 5): procedural canvas textures,
// gradient sky with sun and clouds, detailed models, particles. Phases 1-3:
// 3D scene, economy and waves, sounds and music. (Phase 4 save game and
// leaderboard were removed at Saud's request; the game always starts fresh
// and has no score submission.) Phase 6: action buttons are icons, no save
// or leaderboard. Phase 7: bigger ground (440) and proper low-poly soldier
// characters with a walk animation. Phase 8: endless horizon, dense fog and
// a fog-coloured skirt hide the terrain edge (the mountain ring from Phase 8
// was removed in Phase 9, it looked fake). Phase 9: a real landscape,
// rolling hills, clustered forests, stones, a winding river, a pond, and
// animals (deer, rabbits, birds) moving around in the wild.
// A Stronghold-style castle builder scene: procedural low-poly geometry only,
// no external models, images or audio. Three.js + OrbitControls, bundled by Vite.

import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { mergeGeometries } from 'three/addons/utils/BufferGeometryUtils.js';

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
const soundLabel = document.getElementById('sound-label');

function updateSoundButton() {
  if (!soundBtn) return;
  soundBtn.classList.toggle('muted', muted);
  if (soundLabel) soundLabel.textContent = muted ? 'Off' : 'On';
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
scene.background = new THREE.Color(0x87bfe8); // replaced by the gradient sky texture below
// Dense fog (Phase 8): the far terrain edge must fade out before it is
// reached. At max zoom-out the camera sits 220 from the castle, so fog
// starts at 230 (the castle stays crisp even at max zoom) and is complete
// at 420, just short of the far edge at ~440. Colour matches the sky
// horizon band so the fade reads as haze, not a grey wall.
scene.fog = new THREE.Fog(0xc9d9ec, 230, 420);

const camera = new THREE.PerspectiveCamera(
  55,
  window.innerWidth / window.innerHeight,
  0.1,
  1000,
);
camera.position.set(56, 42, 56);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(0, 2, 0);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.minDistance = 14;
controls.maxDistance = 220;
controls.maxPolarAngle = Math.PI / 2 - 0.04; // never go under the ground

// ---------------------------------------------------------------------------
// Procedural canvas textures (graphics upgrade)
// Everything is drawn in code, no external downloads, so the build stays
// self-contained. Textures are 256x256, small enough for weak hardware.
// ---------------------------------------------------------------------------
function canvasTexture(canvas, rx = 1, ry = 1) {
  const t = new THREE.CanvasTexture(canvas);
  t.wrapS = THREE.RepeatWrapping;
  t.wrapT = THREE.RepeatWrapping;
  t.repeat.set(rx, ry);
  t.colorSpace = THREE.SRGBColorSpace;
  t.anisotropy = Math.min(2, renderer.capabilities.getMaxAnisotropy());
  return t;
}

function blankCanvas(size) {
  const c = document.createElement('canvas');
  c.width = size;
  c.height = size;
  return c;
}

function speckle(g, size, n, alpha) {
  for (let i = 0; i < n; i++) {
    const v = 90 + Math.floor(Math.random() * 90);
    g.fillStyle = `rgba(${v},${v},${v},${alpha})`;
    g.fillRect(Math.random() * size, Math.random() * size, 1.5, 1.5);
  }
}

// Ashlar stone: rows of blocks with per-block shade variation and mortar lines.
function stoneCanvas(base) {
  const s = 256;
  const c = blankCanvas(s);
  const g = c.getContext('2d');
  g.fillStyle = `rgb(${base},${base - 2},${base - 12})`;
  g.fillRect(0, 0, s, s);
  const rows = 8;
  const rh = s / rows;
  for (let row = 0; row < rows; row++) {
    const off = (row % 2) * 32;
    for (let col = -1; col < 5; col++) {
      const shade = base + Math.floor(Math.random() * 24) - 12;
      g.fillStyle = `rgb(${shade},${shade - 2},${shade - 12})`;
      g.fillRect(col * 64 + off + 1, row * rh + 1, 62, rh - 2);
    }
  }
  g.strokeStyle = 'rgba(60,58,50,0.5)';
  g.lineWidth = 1.5;
  for (let row = 0; row <= rows; row++) {
    g.beginPath(); g.moveTo(0, row * rh); g.lineTo(s, row * rh); g.stroke();
  }
  speckle(g, s, 2200, 0.07);
  return c;
}

// Grass: green base with soft blotches and tiny blade speckles.
function grassCanvas() {
  const s = 256;
  const c = blankCanvas(s);
  const g = c.getContext('2d');
  g.fillStyle = '#5d8f4e';
  g.fillRect(0, 0, s, s);
  const tones = ['#54854a', '#6b9c58', '#4f7d44', '#679a55'];
  for (let i = 0; i < 260; i++) {
    g.fillStyle = tones[i % tones.length];
    g.globalAlpha = 0.25;
    g.beginPath();
    g.ellipse(Math.random() * s, Math.random() * s, 4 + Math.random() * 12, 3 + Math.random() * 8, Math.random() * Math.PI, 0, Math.PI * 2);
    g.fill();
  }
  g.globalAlpha = 1;
  for (let i = 0; i < 900; i++) {
    g.fillStyle = Math.random() < 0.5 ? 'rgba(40,90,35,0.35)' : 'rgba(140,190,110,0.3)';
    g.fillRect(Math.random() * s, Math.random() * s, 1, 2 + Math.random() * 2);
  }
  return c;
}

// Wood planks with grain.
function woodCanvas() {
  const s = 256;
  const c = blankCanvas(s);
  const g = c.getContext('2d');
  g.fillStyle = '#8a6134';
  g.fillRect(0, 0, s, s);
  for (let col = 0; col < 6; col++) {
    const shade = 128 + Math.floor(Math.random() * 24) - 12;
    g.fillStyle = `rgb(${shade},${Math.floor(shade * 0.72)},${Math.floor(shade * 0.4)})`;
    g.fillRect(col * 43 + 1, 0, 41, s);
    g.strokeStyle = 'rgba(60,38,16,0.5)';
    g.beginPath(); g.moveTo(col * 43, 0); g.lineTo(col * 43, s); g.stroke();
    g.strokeStyle = 'rgba(90,58,24,0.35)';
    for (let i = 0; i < 5; i++) {
      const x = col * 43 + 6 + Math.random() * 30;
      g.beginPath(); g.moveTo(x, 0);
      g.bezierCurveTo(x + 4, s * 0.3, x - 4, s * 0.6, x + 2, s);
      g.stroke();
    }
  }
  return c;
}

// Terracotta roof tiles: overlapping rows of rounded tiles.
function roofCanvas() {
  const s = 256;
  const c = blankCanvas(s);
  const g = c.getContext('2d');
  g.fillStyle = '#8a4b2d';
  g.fillRect(0, 0, s, s);
  const rows = 8;
  const rh = s / rows;
  for (let row = 0; row < rows; row++) {
    const off = (row % 2) * 16;
    for (let col = -1; col < 9; col++) {
      const shade = 128 + Math.floor(Math.random() * 26) - 13;
      g.fillStyle = `rgb(${shade},${Math.floor(shade * 0.55)},${Math.floor(shade * 0.33)})`;
      g.beginPath();
      g.arc(col * 32 + off + 16, row * rh + rh, 15, Math.PI, 0);
      g.fill();
      g.strokeStyle = 'rgba(70,30,15,0.45)';
      g.stroke();
    }
  }
  return c;
}

// Packed dirt with speckles, darker at the left and right edges.
function dirtCanvas() {
  const s = 256;
  const c = blankCanvas(s);
  const g = c.getContext('2d');
  g.fillStyle = '#a68a5e';
  g.fillRect(0, 0, s, s);
  for (let i = 0; i < 500; i++) {
    g.fillStyle = Math.random() < 0.5 ? 'rgba(110,85,45,0.25)' : 'rgba(190,160,110,0.25)';
    g.beginPath();
    g.arc(Math.random() * s, Math.random() * s, 1 + Math.random() * 4, 0, Math.PI * 2);
    g.fill();
  }
  const edge = g.createLinearGradient(0, 0, s, 0);
  edge.addColorStop(0, 'rgba(70,55,30,0.45)');
  edge.addColorStop(0.2, 'rgba(70,55,30,0)');
  edge.addColorStop(0.8, 'rgba(70,55,30,0)');
  edge.addColorStop(1, 'rgba(70,55,30,0.45)');
  g.fillStyle = edge;
  g.fillRect(0, 0, s, s);
  return c;
}

// Large flagstones for the courtyard.
function slabCanvas() {
  const s = 256;
  const c = blankCanvas(s);
  const g = c.getContext('2d');
  g.fillStyle = '#8f8a7c';
  g.fillRect(0, 0, s, s);
  for (let row = 0; row < 4; row++) {
    const off = (row % 2) * 32;
    for (let col = -1; col < 5; col++) {
      const shade = 138 + Math.floor(Math.random() * 20) - 10;
      g.fillStyle = `rgb(${shade},${shade - 3},${shade - 12})`;
      g.fillRect(col * 64 + off + 2, row * 64 + 2, 60, 60);
    }
  }
  g.strokeStyle = 'rgba(70,66,58,0.55)';
  g.lineWidth = 2;
  for (let i = 0; i <= 4; i++) {
    g.beginPath(); g.moveTo(0, i * 64); g.lineTo(s, i * 64); g.stroke();
    g.beginPath(); g.moveTo(i * 64, 0); g.lineTo(i * 64, s); g.stroke();
  }
  speckle(g, s, 1500, 0.06);
  return c;
}

// Soft radial blob, used for the sun glow, clouds and particles.
function softCanvas() {
  const s = 128;
  const c = blankCanvas(s);
  const g = c.getContext('2d');
  const grad = g.createRadialGradient(s / 2, s / 2, 2, s / 2, s / 2, s / 2);
  grad.addColorStop(0, 'rgba(255,255,255,1)');
  grad.addColorStop(0.4, 'rgba(255,255,255,0.6)');
  grad.addColorStop(1, 'rgba(255,255,255,0)');
  g.fillStyle = grad;
  g.fillRect(0, 0, s, s);
  return c;
}

const stoneTex = canvasTexture(stoneCanvas(154), 2, 1);
const stoneDarkTex = canvasTexture(stoneCanvas(120), 1, 1);
const grassTex = canvasTexture(grassCanvas(), 70, 70);
const woodTex = canvasTexture(woodCanvas(), 1, 1);
const roofTex = canvasTexture(roofCanvas(), 2, 2);
const dirtTex = canvasTexture(dirtCanvas(), 1, 5);
const slabTex = canvasTexture(slabCanvas(), 3, 3);
const softTex = canvasTexture(softCanvas());

// Gradient sky: a vertical gradient texture used as the scene background.
{
  const c = document.createElement('canvas');
  c.width = 32;
  c.height = 512;
  const g = c.getContext('2d');
  const grad = g.createLinearGradient(0, 0, 0, 512);
  grad.addColorStop(0, '#4f8fd0');
  grad.addColorStop(0.42, '#8ab8e2');
  grad.addColorStop(0.55, '#bcd4ec');
  grad.addColorStop(0.68, '#c9d9ec'); // horizon band matches the fog colour
  grad.addColorStop(0.85, '#e2ecf4');
  grad.addColorStop(1, '#eef4f6');
  g.fillStyle = grad;
  g.fillRect(0, 0, 32, 512);
  const skyTex = new THREE.CanvasTexture(c);
  skyTex.colorSpace = THREE.SRGBColorSpace;
  skyTex.mapping = THREE.EquirectangularReflectionMapping;
  scene.background = skyTex;
}

// Sun disc + glow, and slow drifting clouds.
const sunSprite = new THREE.Sprite(new THREE.SpriteMaterial({
  map: softTex, color: 0xfff3c4, fog: false, depthWrite: false,
}));
sunSprite.position.set(150, 215, 95);
sunSprite.scale.set(70, 70, 1);
scene.add(sunSprite);
const sunGlow = new THREE.Sprite(new THREE.SpriteMaterial({
  map: softTex, color: 0xffe9a8, fog: false, depthWrite: false, transparent: true, opacity: 0.4,
}));
sunGlow.position.copy(sunSprite.position);
sunGlow.scale.set(170, 170, 1);
scene.add(sunGlow);

const clouds = [];
for (let i = 0; i < 6; i++) {
  const cloud = new THREE.Sprite(new THREE.SpriteMaterial({
    map: softTex, color: 0xffffff, fog: false, depthWrite: false, transparent: true, opacity: 0.75,
  }));
  const a = (i / 6) * Math.PI * 2 + 0.4;
  const r = 150 + (i % 3) * 70;
  cloud.position.set(Math.cos(a) * r, 70 + (i % 3) * 16, Math.sin(a) * r);
  const cs = 42 + (i % 3) * 16;
  cloud.scale.set(cs, cs * 0.42, 1);
  cloud.userData.drift = 0.4 + (i % 3) * 0.25;
  scene.add(cloud);
  clouds.push(cloud);
}

// ---------------------------------------------------------------------------
// Lighting
// ---------------------------------------------------------------------------
const hemi = new THREE.HemisphereLight(0xcfe4ff, 0x8a7a5f, 0.85);
scene.add(hemi);

const sun = new THREE.DirectionalLight(0xffd9a0, 2.0);
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
// Terrain: a real rolling landscape, flat near the castle
// ---------------------------------------------------------------------------
// Deterministic random (mulberry32) so the forest, rocks and animals are
// laid out the same way on every load, which also keeps screenshots
// comparable between runs.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function smoothstep(a, b, x) {
  const t = Math.min(1, Math.max(0, (x - a) / (b - a)));
  return t * t * (3 - 2 * t);
}

// The river winds west to east across the north half of the map, well
// clear of the castle (it never comes closer than about 115 units to the
// centre, so it never touches the village or the build area).
function riverZ(x) {
  return -(95 + 55 * Math.sin(x * 0.011 + 0.7) + 22 * Math.sin(x * 0.027 + 2.1));
}

// Distance from (x, z) to the river centreline. The river runs mostly
// west to east, so the vertical distance is a good approximation (the
// slope correction keeps it honest where the river bends).
function riverDistance(x, z) {
  const dz = z - riverZ(x);
  const slope = -55 * 0.011 * Math.cos(x * 0.011 + 0.7) - 22 * 0.027 * Math.cos(x * 0.027 + 2.1);
  return Math.abs(dz) / Math.sqrt(1 + slope * slope);
}

// The pond sits in the south meadow, far from the castle and the path.
// This spot was picked because the ground around it is gentle enough
// that a flat water disc sits below the bowl's rim all the way round.
const POND_X = -60;
const POND_Z = 150;
const POND_R = 20;

function pondDistance(x, z) {
  return Math.hypot(x - POND_X, z - POND_Z);
}

// True when a point is in water (river channel or pond bowl). Buildings
// cannot be placed there.
function isInWater(x, z) {
  return riverDistance(x, z) < 6.5 || pondDistance(x, z) < POND_R + 1;
}

// Rolling hills built from layered sines: gentle near the castle, growing
// into a proper ridge toward the far edge so the horizon is a hill line,
// not a cut. The river channel and the pond bowl are carved into it.
function terrainHeight(x, z) {
  const d = Math.hypot(x, z);
  const t = smoothstep(40, 80, d); // 0 on the flat castle ground, 1 beyond
  const roll =
    Math.sin(x * 0.045 + 1.7) * Math.cos(z * 0.038 + 0.6) * 2.0 +
    Math.sin((x + z) * 0.021 + 2.3) * 1.5 +
    Math.sin(x * 0.013 - 0.9) * Math.cos(z * 0.017 + 1.2) * 2.4 +
    Math.sin((x - z) * 0.008 + 0.4) * 2.0;
  // The far ground climbs into a ridge (up to about 10) so the terrain
  // itself hides its own edge; the rise varies along the rim so the
  // horizon line is uneven, like real hills.
  const rim = smoothstep(110, 215, d);
  const rimRise =
    rim * rim * 10 * (0.75 + 0.25 * Math.sin(x * 0.03 + 2.0) * Math.cos(z * 0.026 + 0.5));
  let h = t * roll * (0.6 + 0.4 * t) + rimRise;
  // River channel: a smooth valley about 14 wide, 4.0 deep. The channel
  // is deliberately deep so the water (one unit above the channel bottom)
  // sits well below the banks even where the hillside slopes away from
  // the river, and the ribbon's edges stay buried in the banks.
  const rd = riverDistance(x, z);
  h -= 4.0 * Math.exp(-(rd * rd) / (2 * 7 * 7));
  // Pond bowl: a round dip about 40 wide, 2.4 deep.
  const pd = pondDistance(x, z);
  h -= 2.4 * Math.exp(-(pd * pd) / (2 * 20 * 20));
  return h;
}

// Ground is 640 wide (up from 440 in Phase 9), so the green land feels
// much bigger and the edge sits far beyond the fog from any camera
// angle, while the castle stays centred on flat ground in the middle.
const GROUND_SIZE = 640;
const groundGeo = new THREE.PlaneGeometry(GROUND_SIZE, GROUND_SIZE, 200, 200);
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
  new THREE.MeshStandardMaterial({ map: grassTex, color: 0xffffff, roughness: 1 }),
);
ground.receiveShadow = true;
scene.add(ground);

// Faint grid over the flat castle area, for a building-game feel.
const grid = new THREE.GridHelper(80, 40, 0x35592f, 0x35592f);
grid.material.transparent = true;
grid.material.opacity = 0.1;
grid.position.y = 0.04;
scene.add(grid);

// Stone courtyard disc inside the walls.
const courtyard = new THREE.Mesh(
  new THREE.CircleGeometry(13, 40),
  new THREE.MeshStandardMaterial({ map: slabTex, color: 0xffffff, roughness: 1 }),
);
courtyard.rotation.x = -Math.PI / 2;
courtyard.position.y = 0.03;
courtyard.receiveShadow = true;
scene.add(courtyard);

// Dirt path from the gate (south side) out into the fields.
const path = new THREE.Mesh(
  new THREE.PlaneGeometry(4.5, 30),
  new THREE.MeshStandardMaterial({ map: dirtTex, color: 0xffffff, roughness: 1 }),
);
path.rotation.x = -Math.PI / 2;
path.position.set(0, 0.05, 33);
path.receiveShadow = true;
scene.add(path);

// ---------------------------------------------------------------------------
// Horizon: fog + edge-blend skirt (Phase 8, mountains removed in Phase 9)
// The wide view used to show the hard cut of the square terrain. Two
// things hide it now: the denser fog above, and a huge flat disc in the
// fog colour under the rim, so any sight line past the map meets
// fog-coloured ground, never a cut edge or bare sky. The far terrain
// itself also climbs into a ridge (see terrainHeight), so the horizon is
// a hill line. The Phase 8 mountain ring was removed in Phase 9, it
// looked fake; real rolling hills do the job now.
// ---------------------------------------------------------------------------

// Edge blend: a huge disc in the fog colour, just under the lowest terrain
// dip (the river channel drops to about -7), so it never pokes through
// the ground.
const skirt = new THREE.Mesh(
  new THREE.CircleGeometry(1600, 48),
  new THREE.MeshBasicMaterial({ color: 0xc9d9ec, fog: true }),
);
skirt.rotation.x = -Math.PI / 2;
skirt.position.y = -9;
scene.add(skirt);



// ---------------------------------------------------------------------------
// Shared materials and small builders
// ---------------------------------------------------------------------------
const stoneMat = new THREE.MeshStandardMaterial({
  map: stoneTex,
  color: 0xffffff,
  roughness: 0.95,
});
const stoneDarkMat = new THREE.MeshStandardMaterial({
  map: stoneDarkTex,
  color: 0xffffff,
  roughness: 0.95,
});
const woodMat = new THREE.MeshStandardMaterial({
  map: woodTex,
  color: 0xffffff,
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

// Crenellations (merlons) along a wall running in X. Merged into one mesh
// per wall so the many small blocks cost a single draw call, not one each.
function addMerlonsX(parent, cx, topY, length, z, mat = stoneMat) {
  const n = Math.max(1, Math.floor(length / 1.4));
  const geos = [];
  for (let i = 0; i < n; i++) {
    const x = cx - length / 2 + (i + 0.5) * (length / n);
    const geo = new THREE.BoxGeometry(0.7, 0.6, 1.5);
    geo.translate(x, topY + 0.3, z);
    geos.push(geo);
  }
  const m = new THREE.Mesh(mergeGeometries(geos), mat);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
}

// Crenellations along a wall running in Z, merged the same way.
function addMerlonsZ(parent, cz, topY, length, x, mat = stoneMat) {
  const n = Math.max(1, Math.floor(length / 1.4));
  const geos = [];
  for (let i = 0; i < n; i++) {
    const z = cz - length / 2 + (i + 0.5) * (length / n);
    const geo = new THREE.BoxGeometry(1.5, 0.6, 0.7);
    geo.translate(x, topY + 0.3, z);
    geos.push(geo);
  }
  const m = new THREE.Mesh(mergeGeometries(geos), mat);
  m.castShadow = true;
  m.receiveShadow = true;
  parent.add(m);
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
// Red banners hanging from the keep's top slab, with a gold trim.
const bannerMat = new THREE.MeshStandardMaterial({ color: 0xa32a22, roughness: 0.85, side: THREE.DoubleSide });
const bannerGoldMat = new THREE.MeshStandardMaterial({ color: 0xd9a441, roughness: 0.6 });
const banners = [];
for (const bx of [-2.2, 2.2]) {
  const b = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 3.2), bannerMat);
  b.position.set(bx, 13.4, 4.06);
  b.castShadow = true;
  keep.add(b);
  const trim = new THREE.Mesh(new THREE.BoxGeometry(1.4, 0.25, 0.06), bannerGoldMat);
  trim.position.set(bx, 11.85, 4.06);
  keep.add(trim);
  banners.push(b);
}
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

// Torches flanking the gate, with flickering flames. One shared point light
// between them keeps the lighting cheap on weak hardware.
const torchLights = [];
const torchFlames = [];
for (const tx of [-4.8, 4.8]) {
  const post = new THREE.Mesh(new THREE.CylinderGeometry(0.09, 0.13, 1.5, 8), darkMat);
  post.position.set(tx, 0.75, HALF + 0.9);
  post.castShadow = true;
  scene.add(post);
  const cup = new THREE.Mesh(new THREE.CylinderGeometry(0.2, 0.12, 0.3, 8), darkMat);
  cup.position.set(tx, 1.6, HALF + 0.9);
  scene.add(cup);
  const flame = new THREE.Mesh(
    new THREE.ConeGeometry(0.22, 0.65, 8),
    new THREE.MeshBasicMaterial({ color: 0xffa63d }),
  );
  flame.position.set(tx, 2.05, HALF + 0.9);
  scene.add(flame);
  const flameCore = new THREE.Mesh(
    new THREE.ConeGeometry(0.11, 0.4, 8),
    new THREE.MeshBasicMaterial({ color: 0xffe08a }),
  );
  flameCore.position.set(tx, 2.0, HALF + 0.9);
  scene.add(flameCore);
  torchFlames.push(flame, flameCore);
}
{
  const light = new THREE.PointLight(0xff9a3d, 16, 20, 1.6);
  light.position.set(0, 2.6, HALF + 1.2);
  scene.add(light);
  torchLights.push({ light, phase: 0 });
}

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
  // Small red pennant on a pole above the tower.
  const pole = new THREE.Mesh(new THREE.CylinderGeometry(0.07, 0.07, 2.2, 6), woodMat);
  pole.position.set(x, 9.2, z);
  pole.castShadow = true;
  g.add(pole);
  const penShape = new THREE.Shape();
  penShape.moveTo(0, 0);
  penShape.lineTo(1.6, 0.4);
  penShape.lineTo(0, 0.8);
  penShape.lineTo(0, 0);
  const pen = new THREE.Mesh(
    new THREE.ShapeGeometry(penShape),
    new THREE.MeshStandardMaterial({ color: 0xd23b2e, side: THREE.DoubleSide, roughness: 0.8 }),
  );
  pen.position.set(x + 0.07, 9.9, z);
  pen.castShadow = true;
  g.add(pen);
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

const windowLitMat = new THREE.MeshStandardMaterial({
  color: 0xffc46b, emissive: 0xff9d2e, emissiveIntensity: 0.65, roughness: 0.6,
});
const chimneys = []; // world positions of chimney tops, for smoke particles

function house(x, z, i) {
  const g = new THREE.Group();
  const wallMat = new THREE.MeshStandardMaterial({
    color: houseColors[i % houseColors.length],
    roughness: 0.9,
  });
  const roofMat = new THREE.MeshStandardMaterial({
    map: roofTex,
    color: 0xffffff,
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
  // Chimney on the roof, and warm lit windows on the front.
  box(0.7, 1.8, 0.7, stoneDarkMat, x + 1.4, y + 4.9, z - 1, g);
  chimneys.push(new THREE.Vector3(x + 1.4, y + 5.9, z - 1));
  box(0.8, 1, 0.2, windowLitMat, x - 1.2, y + 1.7, z + 2.05, g);
  box(0.8, 1, 0.2, windowLitMat, x + 1.2, y + 1.7, z + 2.05, g);
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
house(62, -40, 6);
house(-64, 48, 7);

// Place a geometry in the world: rotate around Y, scale uniformly, move.
const _xformM = new THREE.Matrix4();
const _xformQ = new THREE.Quaternion();
const _xformV = new THREE.Vector3();
const _xformS = new THREE.Vector3();
function xformGeo(geo, x, y, z, rotY, s) {
  _xformQ.setFromAxisAngle(new THREE.Vector3(0, 1, 0), rotY);
  _xformV.set(x, y, z);
  _xformS.set(s, s, s);
  _xformM.compose(_xformV, _xformQ, _xformS);
  geo.applyMatrix4(_xformM);
  return geo;
}

// ---------------------------------------------------------------------------
// Forest: trees grow in real clusters (Phase 9), not scattered singles.
// Dense groups of varied pine and broadleaf trees with varied sizes, and
// open meadow left between the forest and the castle. All trees of one
// kind are merged into a single mesh, so about 90 trees cost three draw
// calls. Forest trees are scenery and are not selectable.
// ---------------------------------------------------------------------------
const FORESTS = [
  { x: -75, z: -165, r: 34, n: 14 },
  { x: 75, z: -165, r: 34, n: 14 },
  { x: 140, z: -110, r: 34, n: 12 },
  { x: -140, z: -110, r: 34, n: 12 },
  { x: 165, z: 15, r: 30, n: 10 },
  { x: -165, z: -5, r: 30, n: 10 },
  { x: -150, z: 85, r: 28, n: 9 },
  { x: 125, z: 125, r: 24, n: 7 },
  // Outer forests on the bigger ground, filling the far land.
  { x: 240, z: -140, r: 30, n: 10 },
  { x: -240, z: -140, r: 30, n: 10 },
  { x: 250, z: 120, r: 30, n: 10 },
  { x: -250, z: 140, r: 28, n: 9 },
];
// A few lone trees standing in the open meadow.
const LONE_TREES = [
  [-60, 60], [70, 65], [-100, 40], [100, -60], [30, 110], [-40, 110],
];

const VILLAGE_HOUSES = [
  [-30, 6], [-34, -16], [28, -22], [36, 8], [26, 32], [-28, 28], [62, -40], [-64, 48],
];

function treeSpotOk(x, z) {
  if (Math.abs(x) > 300 || Math.abs(z) > 300) return false;
  if (Math.hypot(x, z) < 55) return false; // keep the meadow around the castle open
  if (riverDistance(x, z) < 10) return false; // no trees standing in the river
  if (pondDistance(x, z) < 28) return false; // none on the pond shore either
  for (const [hx, hz] of VILLAGE_HOUSES) {
    if (Math.hypot(x - hx, z - hz) < 9) return false;
  }
  return true;
}

let forestTreeCount = 0;

function buildForest() {
  const rng = mulberry32(20261108);
  const trunkGeos = [];
  const pineGeos = [];
  const leafGeos = [];
  const bushGeos = [];
  const tuftGeos = [];
  function plantTree(x, z) {
    const s = 0.8 + rng() * 0.5;
    const y = terrainHeight(x, z);
    const rotY = rng() * Math.PI * 2;
    if (rng() < 0.55) {
      // Pine: trunk + three stacked cones.
      trunkGeos.push(xformGeo(new THREE.CylinderGeometry(0.28, 0.36, 1.8, 7), x, y + 0.9 * s, z, rotY, s));
      for (let k = 0; k < 3; k++) {
        pineGeos.push(xformGeo(
          new THREE.ConeGeometry(1.9 - k * 0.45, 2.2, 7),
          x, y + (2.6 + k * 1.5) * s, z, rotY, s,
        ));
      }
    } else {
      // Broadleaf: trunk + a cluster of leafy blobs.
      trunkGeos.push(xformGeo(new THREE.CylinderGeometry(0.3, 0.4, 2.6, 7), x, y + 1.3 * s, z, rotY, s));
      const blobs = [
        [0, 3.4, 0, 1.7], [-1, 2.8, 0.4, 1.1], [1, 2.9, -0.3, 1.2], [0.2, 4.1, -0.2, 1.1],
      ];
      for (const [bx, by, bz, br] of blobs) {
        leafGeos.push(xformGeo(
          new THREE.IcosahedronGeometry(br, 0),
          x + bx * s, y + by * s, z + bz * s, rotY, s,
        ));
      }
    }
  }
  for (const f of FORESTS) {
    let placed = 0;
    let tries = 0;
    while (placed < f.n && tries < f.n * 8) {
      tries += 1;
      const a = rng() * Math.PI * 2;
      const r = Math.sqrt(rng()) * f.r;
      const x = f.x + Math.cos(a) * r;
      const z = f.z + Math.sin(a) * r;
      if (!treeSpotOk(x, z)) continue;
      plantTree(x, z);
      placed += 1;
      forestTreeCount += 1;
    }
  }
  for (const [x, z] of LONE_TREES) {
    if (treeSpotOk(x, z)) {
      plantTree(x, z);
      forestTreeCount += 1;
    }
  }
  // Undergrowth: bushes at the forest edges and grass tufts in the meadow.
  for (const f of FORESTS) {
    for (let i = 0; i < 6; i++) {
      const a = rng() * Math.PI * 2;
      const r = f.r + 2 + rng() * 7;
      const x = f.x + Math.cos(a) * r;
      const z = f.z + Math.sin(a) * r;
      if (!treeSpotOk(x, z)) continue;
      const s = 0.7 + rng() * 0.8;
      const geo = new THREE.IcosahedronGeometry(1, 0);
      geo.scale(1, 0.65, 1);
      bushGeos.push(xformGeo(geo, x, terrainHeight(x, z) + 0.45 * s, z, rng() * Math.PI * 2, s));
    }
  }
  for (let i = 0; i < 110; i++) {
    const a = rng() * Math.PI * 2;
    const r = 48 + Math.sqrt(rng()) * 240;
    const x = Math.cos(a) * r;
    const z = Math.sin(a) * r;
    if (!treeSpotOk(x, z)) continue;
    if (Math.abs(x) < 4 && z > 14 && z < 52) continue; // keep the dirt path clear
    const s = 0.7 + rng() * 0.7;
    const y = terrainHeight(x, z);
    for (let k = -1; k <= 1; k++) {
      tuftGeos.push(xformGeo(
        new THREE.ConeGeometry(0.16, 0.9, 5),
        x + k * 0.22 * s, y + 0.4 * s, z + (k % 2) * 0.15 * s, rng() * Math.PI, s,
      ));
    }
  }
  const trunkMat = new THREE.MeshStandardMaterial({ color: 0x6e4a22, roughness: 1 });
  const pineMat = new THREE.MeshStandardMaterial({ color: 0x2e6b2f, roughness: 1 });
  const leafMat = new THREE.MeshStandardMaterial({ color: 0x4d8a33, roughness: 1 });
  const bushMat = new THREE.MeshStandardMaterial({ color: 0x3a6b2f, roughness: 1 });
  const tuftMat = new THREE.MeshStandardMaterial({ color: 0x6fae4e, roughness: 1 });
  function addMerged(geos, mat) {
    if (geos.length === 0) return;
    const m = new THREE.Mesh(mergeGeometries(geos), mat);
    m.castShadow = true;
    m.receiveShadow = true;
    scene.add(m);
  }
  addMerged(trunkGeos, trunkMat);
  addMerged(pineGeos, pineMat);
  addMerged(leafGeos, leafMat);
  addMerged(bushGeos, bushMat);
  addMerged(tuftGeos, tuftMat);
}

buildForest();

// ---------------------------------------------------------------------------
// Stones: rocks and boulders in natural clusters (Phase 9). A few big
// boulders near the hills, clusters of smaller rocks, and small stones
// along the river banks and the pond shore. Varied sizes and two grey
// tones, sunk partway into the ground for a half-buried look. Two merged
// meshes, not selectable, no gameplay effect.
// ---------------------------------------------------------------------------
let rockCount = 0;

function buildRocks() {
  const rng = mulberry32(77031);
  const greyA = [];
  const greyB = [];
  function plantRock(x, z, s, sink) {
    const y = terrainHeight(x, z) + (0.35 - sink) * s;
    const geo = new THREE.DodecahedronGeometry(1.4, 0);
    geo.rotateX(rng() * Math.PI);
    geo.rotateZ(rng() * Math.PI);
    (rng() < 0.5 ? greyA : greyB).push(
      xformGeo(geo, x, y, z, rng() * Math.PI * 2, s),
    );
    rockCount += 1;
  }
  function rockSpotOk(x, z) {
    if (Math.abs(x) > 300 || Math.abs(z) > 300) return false;
    if (Math.hypot(x, z) < 52) return false; // keep the castle ground clear
    if (riverDistance(x, z) < 6.5) return false; // not in the river channel
    if (pondDistance(x, z) < POND_R + 1) return false; // not in the pond
    for (const [hx, hz] of VILLAGE_HOUSES) {
      if (Math.hypot(x - hx, z - hz) < 8) return false;
    }
    return true;
  }
  // Big boulders near the hills.
  const boulders = [
    [-150, -130], [150, -140], [-60, -170], [175, 60], [-170, 60], [40, 170],
    [260, 40], [-260, 60],
  ];
  for (const [x, z] of boulders) {
    if (rockSpotOk(x, z)) plantRock(x, z, 2.8 + rng() * 1.2, 0.6);
  }
  // Rock clusters: five groups of 4-7 mid rocks, plus two on the far land.
  const clusters = [
    [-120, -150], [130, -140], [170, -30], [-170, 25], [90, 150],
    [230, 200], [-240, -180],
  ];
  for (const [cx, cz] of clusters) {
    const n = 4 + Math.floor(rng() * 4);
    for (let i = 0; i < n; i++) {
      const x = cx + (rng() * 2 - 1) * 10;
      const z = cz + (rng() * 2 - 1) * 10;
      if (!rockSpotOk(x, z)) continue;
      plantRock(x, z, 0.7 + rng() * 0.9, 0.55);
    }
  }
  // Small stones along the river banks: both banks, a stone every few units.
  for (let x = -312; x <= 312; x += 7) {
    const zc = riverZ(x);
    for (const side of [-1, 1]) {
      if (rng() < 0.55) continue; // gaps, not a solid wall
      const z = zc + side * (8 + rng() * 4);
      if (!rockSpotOk(x, z)) continue;
      plantRock(x, z, 0.3 + rng() * 0.45, 0.7);
    }
  }
  // Small stones around the pond shore.
  for (let i = 0; i < 10; i++) {
    const a = rng() * Math.PI * 2;
    const r = POND_R + 2 + rng() * 4;
    const x = POND_X + Math.cos(a) * r;
    const z = POND_Z + Math.sin(a) * r;
    if (!rockSpotOk(x, z)) continue;
    plantRock(x, z, 0.35 + rng() * 0.4, 0.7);
  }
  const matA = new THREE.MeshStandardMaterial({ color: 0x8d8d8d, roughness: 1 });
  const matB = new THREE.MeshStandardMaterial({ color: 0x6e6e6e, roughness: 1 });
  for (const [geos, mat] of [[greyA, matA], [greyB, matB]]) {
    if (geos.length === 0) continue;
    const m = new THREE.Mesh(mergeGeometries(geos), mat);
    m.castShadow = true;
    m.receiveShadow = true;
    scene.add(m);
  }
}

buildRocks();

// ---------------------------------------------------------------------------
// Water: a winding river and a small pond (Phase 9). The river surface is
// a long sheet of quads that follows the river centreline; each vertex
// sits one unit above the channel bottom at its own position, so the
// sheet follows the valley floor with no steps. It is wider than the
// point where the ground rises above the water level, so its edges sink
// into the banks instead of floating. A canvas texture of pale flow
// streaks scrolls along the river in the animation loop, so the water
// visibly moves. The pond is a still disc in the south-west meadow.
// Enemies walk straight across the shallow river on their way to the
// keep, their feet on the channel bottom, so crossing it looks like
// wading and needs no pathing change.
// ---------------------------------------------------------------------------
function makeWaterTexture() {
  const c = document.createElement('canvas');
  c.width = 256;
  c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#3f8fbf';
  g.fillRect(0, 0, 256, 256);
  // Flow streaks: pale dashes running along the canvas Y axis, which
  // maps to the river's length (the V texture coordinate).
  const rng = mulberry32(5150);
  for (let i = 0; i < 90; i++) {
    const x = rng() * 256;
    const y = rng() * 256;
    const len = 14 + rng() * 34;
    g.strokeStyle = `rgba(255,255,255,${0.10 + rng() * 0.16})`;
    g.lineWidth = 1 + rng() * 2;
    g.beginPath();
    g.moveTo(x, y);
    g.lineTo(x, y + len);
    g.stroke();
  }
  const tex = new THREE.CanvasTexture(c);
  tex.wrapS = THREE.RepeatWrapping;
  tex.wrapT = THREE.RepeatWrapping;
  return tex;
}

const riverWaterMat = new THREE.MeshStandardMaterial({
  map: makeWaterTexture(), color: 0x9fd4e8, roughness: 0.25, metalness: 0.1,
  transparent: true, opacity: 0.92,
});
const pondWaterMat = new THREE.MeshStandardMaterial({
  map: makeWaterTexture(), color: 0x9fd4e8, roughness: 0.25, metalness: 0.1,
  transparent: true, opacity: 0.92,
});

const riverPoints = [];
{
  const geos = [];
  const HALF_WIDTH = 13;
  for (let x = -316; x <= 316; x += 4) {
    const quad = new THREE.PlaneGeometry(HALF_WIDTH * 2, 4);
    // After the two rotations the plane lies flat: local X runs along
    // the river (length 4), local Z runs across it (width 26).
    quad.rotateX(-Math.PI / 2);
    quad.rotateY(Math.PI / 2);
    const pos = quad.attributes.position;
    for (let i = 0; i < pos.count; i++) {
      const along = pos.getX(i); // -2..2, along the river
      const across = pos.getZ(i); // -13..13, across the river
      const wx = x + along;
      const wz = riverZ(wx) + across;
      // One unit above the channel bottom at this exact spot.
      pos.setY(i, terrainHeight(wx, riverZ(wx)) + 1.0);
      pos.setX(i, wx);
      pos.setZ(i, wz);
    }
    // UVs: U runs across the river (one texture repeat), V runs along
    // it so the streaks scroll with the flow.
    const uv = quad.attributes.uv;
    for (let i = 0; i < uv.count; i++) {
      uv.setXY(i, uv.getX(i), pos.getX(i) / 24);
    }
    geos.push(quad);
    riverPoints.push([x, riverZ(x)]);
  }
  const river = new THREE.Mesh(mergeGeometries(geos), riverWaterMat);
  scene.add(river);
}

// The pond: a still disc in the south meadow, wide enough that its
// rim sinks into the bowl's slope.
const pond = new THREE.Mesh(
  new THREE.CircleGeometry(30, 40),
  pondWaterMat,
);
pond.rotation.x = -Math.PI / 2;
pond.position.set(POND_X, terrainHeight(POND_X, POND_Z) + 1.0, POND_Z);
scene.add(pond);

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
  wall: { label: '10 Stone' },
  house: { label: '20 Wood' },
  farm: { label: '15 Wood' },
  tower: { label: '30 Stone, 10 Wood' },
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

function placeBtnLabel(btn) {
  return btn.querySelector('.btn-label');
}

function resetPlaceButtons() {
  for (const [kind, btn] of Object.entries(placeBtns)) {
    btn.classList.remove('active');
    placeBtnLabel(btn).textContent = PLACE_DEFS[kind].label;
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
  placeBtnLabel(btn).textContent = 'Placing';
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
  if (Math.abs(x) > 100 || Math.abs(z) > 100) {
    setStatus('Too far out, build closer to the castle');
    return false;
  }
  if (isInWater(x, z)) {
    setStatus('Too wet to build here');
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
// Particles: arrow trails, hit sparks, chimney smoke, enemy dust
// One THREE.Points draw call, capped at 400 live particles, updated on CPU.
// ---------------------------------------------------------------------------
const P_MAX = 400;
const pGeo = new THREE.BufferGeometry();
const pPos = new Float32Array(P_MAX * 3);
const pCol = new Float32Array(P_MAX * 3);
const pSize = new Float32Array(P_MAX);
const pAlpha = new Float32Array(P_MAX);
pGeo.setAttribute('position', new THREE.BufferAttribute(pPos, 3));
pGeo.setAttribute('aColor', new THREE.BufferAttribute(pCol, 3));
pGeo.setAttribute('aSize', new THREE.BufferAttribute(pSize, 1));
pGeo.setAttribute('aAlpha', new THREE.BufferAttribute(pAlpha, 1));
const pMat = new THREE.ShaderMaterial({
  uniforms: { uTex: { value: softTex } },
  vertexShader: `
    attribute vec3 aColor;
    attribute float aSize;
    attribute float aAlpha;
    varying vec3 vColor;
    varying float vAlpha;
    void main() {
      vColor = aColor;
      vAlpha = aAlpha;
      vec4 mv = modelViewMatrix * vec4(position, 1.0);
      gl_PointSize = aSize * 260.0 / max(1.0, -mv.z);
      gl_Position = projectionMatrix * mv;
    }`,
  fragmentShader: `
    uniform sampler2D uTex;
    varying vec3 vColor;
    varying float vAlpha;
    void main() {
      vec4 tex = texture2D(uTex, gl_PointCoord);
      float a = tex.a * vAlpha;
      if (a < 0.02) discard;
      gl_FragColor = vec4(vColor, a);
    }`,
  transparent: true,
  depthWrite: false,
});
const pPoints = new THREE.Points(pGeo, pMat);
pPoints.frustumCulled = false;
scene.add(pPoints);

const parts = []; // {x,y,z,vx,vy,vz,life,max,size,r,g,b,grav,grow,peak}

function spawnParticle(o) {
  if (parts.length >= P_MAX) return;
  parts.push({
    x: o.x, y: o.y, z: o.z,
    vx: o.vx || 0, vy: o.vy || 0, vz: o.vz || 0,
    life: 0, max: o.life || 1,
    size: o.size || 1,
    r: o.r ?? 1, g: o.g ?? 1, b: o.b ?? 1,
    grav: o.grav || 0, grow: o.grow || 0, peak: o.peak ?? 0.5,
  });
}

function burstSparks(x, y, z) {
  for (let i = 0; i < 7; i++) {
    const a = Math.random() * Math.PI * 2;
    const sp = 2 + Math.random() * 5;
    spawnParticle({
      x, y, z,
      vx: Math.cos(a) * sp, vy: 1 + Math.random() * 3, vz: Math.sin(a) * sp,
      life: 0.3 + Math.random() * 0.15, size: 0.32,
      r: 1, g: 0.62, b: 0.15, grav: -7,
    });
  }
}

function updateParticles(delta) {
  for (let i = parts.length - 1; i >= 0; i--) {
    const p = parts[i];
    p.life += delta;
    if (p.life >= p.max) {
      parts.splice(i, 1);
      continue;
    }
    p.vy += p.grav * delta;
    p.x += p.vx * delta;
    p.y += p.vy * delta;
    p.z += p.vz * delta;
  }
  for (let i = 0; i < parts.length; i++) {
    const p = parts[i];
    const t = p.life / p.max;
    const a = t < 0.15 ? t / 0.15 : 1 - (t - 0.15) / 0.85;
    const idx = i * 3;
    pPos[idx] = p.x; pPos[idx + 1] = p.y; pPos[idx + 2] = p.z;
    pCol[idx] = p.r; pCol[idx + 1] = p.g; pCol[idx + 2] = p.b;
    pSize[i] = p.size * (1 + p.grow * t);
    pAlpha[i] = Math.max(0, a) * p.peak;
  }
  pGeo.setDrawRange(0, parts.length);
  pGeo.attributes.position.needsUpdate = true;
  pGeo.attributes.aColor.needsUpdate = true;
  pGeo.attributes.aSize.needsUpdate = true;
  pGeo.attributes.aAlpha.needsUpdate = true;
}

// ---------------------------------------------------------------------------
// Enemy waves
// ---------------------------------------------------------------------------
const waveBtn = document.getElementById('btn-next-wave');

// Proper low-poly soldiers (Phase 7): helmeted head, tunic torso, swinging
// arms and legs, shield and spear or sword. Three visual variants with
// IDENTICAL behaviour and hitboxes: same speed, same hp, same ranges.
const enemySkinMat = new THREE.MeshStandardMaterial({ color: 0xd9b48a, roughness: 0.9 });
const enemyLegMat = new THREE.MeshStandardMaterial({ color: 0x4a3421, roughness: 1 });
const enemyMetalMat = new THREE.MeshStandardMaterial({ color: 0x9a9a92, roughness: 0.5, metalness: 0.4 });
const enemyShieldMat = new THREE.MeshStandardMaterial({ color: 0x8a6134, roughness: 0.9 });
const enemyTunicMats = [
  new THREE.MeshStandardMaterial({ color: 0x8a2a22, roughness: 0.9 }), // red spearman
  new THREE.MeshStandardMaterial({ color: 0x2e4a6e, roughness: 0.9 }), // blue swordsman
  new THREE.MeshStandardMaterial({ color: 0x5a6e2e, roughness: 0.9 }), // olive spearman
];

// A limb group pivoted at its top joint; the mesh hangs below the pivot
// so rotating the group swings the limb while walking.
function limbMesh(w, h, d, mat, px, py) {
  const pivot = new THREE.Group();
  pivot.position.set(px, py, 0);
  const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat);
  m.position.y = -h / 2;
  m.castShadow = true;
  m.receiveShadow = true;
  pivot.add(m);
  return pivot;
}

function createSoldier(variant) {
  const v = variant % 3;
  const tunic = enemyTunicMats[v];
  const g = new THREE.Group();
  // Legs (swing from the hip while walking).
  const legL = limbMesh(0.26, 0.9, 0.3, enemyLegMat, -0.22, 0.95);
  const legR = limbMesh(0.26, 0.9, 0.3, enemyLegMat, 0.22, 0.95);
  g.add(legL, legR);
  // Torso with tunic and belt.
  box(1.05, 1.0, 0.62, tunic, 0, 1.45, 0, g);
  box(1.08, 0.12, 0.65, darkMat, 0, 1.0, 0, g);
  // Left arm, carrying the shield on the forearm.
  const armL = limbMesh(0.22, 0.8, 0.24, tunic, -0.63, 1.88);
  if (v === 1) {
    // Kite shield: tall board.
    const shield = new THREE.Mesh(new THREE.BoxGeometry(0.72, 1.0, 0.08), enemyShieldMat);
    shield.position.set(0, -0.55, 0.24);
    shield.castShadow = true;
    armL.add(shield);
  } else {
    // Round shield with a metal boss.
    const shield = new THREE.Mesh(new THREE.CylinderGeometry(0.52, 0.52, 0.08, 14), enemyShieldMat);
    shield.rotation.x = Math.PI / 2;
    shield.position.set(0, -0.55, 0.24);
    shield.castShadow = true;
    armL.add(shield);
    const boss = new THREE.Mesh(new THREE.SphereGeometry(0.14, 10, 8), enemyMetalMat);
    boss.position.set(0, -0.55, 0.32);
    armL.add(boss);
  }
  g.add(armL);
  // Right arm, carrying the weapon.
  const armR = limbMesh(0.22, 0.8, 0.24, tunic, 0.63, 1.88);
  if (v === 1) {
    // Sword: blade, guard and grip, held down at the side.
    box(0.12, 1.05, 0.05, enemyMetalMat, 0, -0.35, 0.08, armR);
    box(0.38, 0.08, 0.1, darkMat, 0, 0.22, 0.08, armR);
    cylinder(0.05, 0.05, 0.25, darkMat, 0, 0.35, 0.08, armR, 6);
  } else {
    // Spear: long shaft with a metal tip, held upright.
    cylinder(0.05, 0.05, 2.6, woodMat, 0, 0.35, 0.1, armR, 6);
    const tip = new THREE.Mesh(new THREE.ConeGeometry(0.09, 0.35, 6), enemyMetalMat);
    tip.position.set(0, 1.8, 0.1);
    tip.castShadow = true;
    armR.add(tip);
  }
  g.add(armR);
  // Head with skin, plus a helmet that differs per variant.
  box(0.55, 0.55, 0.55, enemySkinMat, 0, 2.22, 0, g);
  if (v === 0) {
    // Pointed kettle helm with a brim.
    const helm = new THREE.Mesh(new THREE.ConeGeometry(0.42, 0.55, 8), enemyMetalMat);
    helm.position.set(0, 2.72, 0);
    helm.castShadow = true;
    g.add(helm);
    cylinder(0.44, 0.44, 0.06, enemyMetalMat, 0, 2.5, 0, g, 12);
  } else if (v === 1) {
    // Dome helm with a brim.
    const helm = new THREE.Mesh(
      new THREE.SphereGeometry(0.34, 12, 8, 0, Math.PI * 2, 0, Math.PI / 2),
      enemyMetalMat,
    );
    helm.position.set(0, 2.5, 0);
    helm.castShadow = true;
    g.add(helm);
    cylinder(0.4, 0.4, 0.06, enemyMetalMat, 0, 2.5, 0, g, 12);
  } else {
    // Nasal helm: flat cap with a nose guard strip.
    box(0.6, 0.16, 0.6, enemyMetalMat, 0, 2.52, 0, g);
    box(0.08, 0.38, 0.06, enemyMetalMat, 0, 2.32, 0.29, g);
  }
  return { group: g, limbs: { legL, legR, armL, armR } };
}

function createEnemy(x, z, speed, variant = 0) {
  const s = createSoldier(variant);
  s.group.position.set(x, terrainHeight(x, z), z);
  scene.add(s.group);
  enemies.push({ group: s.group, limbs: s.limbs, hp: 2, speed, phase: Math.random() * Math.PI * 2 });
}

function spawnWave(count) {
  for (let i = 0; i < count; i++) {
    const angle = (i / count) * Math.PI * 2 + Math.random() * 0.6;
    const r = 125 + Math.random() * 8; // new map edge
    createEnemy(
      Math.cos(angle) * r,
      Math.sin(angle) * r,
      Math.min(2.4 + state.wave * 0.15, 4),
      i % 3, // visual variant only, behaviour is identical
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
      burstSparks(tp.x, tp.y + 1.2, tp.z);
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
    a.frame = (a.frame || 0) + 1;
    if (a.frame % 3 === 0) {
      spawnParticle({
        x: a.mesh.position.x, y: a.mesh.position.y, z: a.mesh.position.z,
        life: 0.22, size: 0.35, r: 0.85, g: 0.75, b: 0.55, peak: 0.45,
      });
    }
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
    // Walk cycle: legs and arms swing, body bobs (the bob is in p.y above).
    const swing = Math.sin(elapsed * 6 + e.phase);
    if (e.limbs) {
      e.limbs.legL.rotation.x = swing * 0.55;
      e.limbs.legR.rotation.x = -swing * 0.55;
      e.limbs.armL.rotation.x = -swing * 0.4;
      e.limbs.armR.rotation.x = swing * 0.3;
    }
    // Dust puffs at the enemy's feet while it marches.
    e.dust = (e.dust || 0) + delta;
    if (e.dust > 0.4) {
      e.dust = 0;
      spawnParticle({
        x: p.x, y: p.y + 0.15, z: p.z,
        vx: (Math.random() - 0.5) * 0.4, vy: 0.35, vz: (Math.random() - 0.5) * 0.4,
        life: 0.7, size: 0.7, r: 0.62, g: 0.55, b: 0.42, grow: 1.2, peak: 0.3,
      });
    }
  }
}

// ---------------------------------------------------------------------------
// Animals: ambient wildlife (Phase 9). A small herd of deer, a few
// rabbits and birds flying overhead. They wander, graze (head down),
// change direction, and keep to the forest and meadow areas, away from
// the castle. They are ambient only: towers ignore them, enemies ignore
// them, and they never affect resources or waves. Deer share one body
// geometry and material; the animation is per-animal pivots.
// ---------------------------------------------------------------------------
const animals = [];
const deerList = [];
const rabbitList = [];
const birdList = [];

const deerBodyMat = new THREE.MeshStandardMaterial({ color: 0x8a6b4a, roughness: 1 });
const deerDarkMat = new THREE.MeshStandardMaterial({ color: 0x5f4830, roughness: 1 });
const deerAntlerMat = new THREE.MeshStandardMaterial({ color: 0xd8cdb8, roughness: 1 });
const rabbitMat = new THREE.MeshStandardMaterial({ color: 0x9b8f7a, roughness: 1 });
const birdMat = new THREE.MeshStandardMaterial({ color: 0x3a3a3a, roughness: 1 });

const deerBodyGeo = new THREE.BoxGeometry(1.15, 0.62, 0.5);
const deerHeadGeo = new THREE.BoxGeometry(0.26, 0.26, 0.48);
const deerEarGeo = new THREE.BoxGeometry(0.1, 0.18, 0.04);
const deerLegGeo = new THREE.BoxGeometry(0.09, 0.62, 0.09);
const deerAntlerGeo = new THREE.CylinderGeometry(0.03, 0.05, 0.5, 5);
const rabbitBodyGeo = new THREE.SphereGeometry(0.28, 8, 6);
const rabbitHeadGeo = new THREE.SphereGeometry(0.17, 8, 6);
const rabbitEarGeo = new THREE.BoxGeometry(0.05, 0.3, 0.03);
const birdBodyGeo = new THREE.ConeGeometry(0.16, 0.9, 5);
const birdWingGeo = new THREE.BoxGeometry(0.3, 0.04, 0.9);

function makeDeer(x, z, hasAntlers) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(deerBodyGeo, deerBodyMat);
  body.position.y = 0.72;
  body.castShadow = true;
  g.add(body);
  // The neck pivots low on the chest so it can swing from upright down
  // to the grass for grazing.
  const neck = new THREE.Group();
  neck.position.set(0.52, 0.62, 0);
  const neckMesh = new THREE.Mesh(new THREE.BoxGeometry(0.18, 0.85, 0.16), deerBodyMat);
  neckMesh.position.y = 0.42;
  neckMesh.castShadow = true;
  neck.add(neckMesh);
  const head = new THREE.Mesh(deerHeadGeo, deerBodyMat);
  head.position.set(0.08, 0.88, 0);
  head.castShadow = true;
  neck.add(head);
  for (const side of [1, -1]) {
    const ear = new THREE.Mesh(deerEarGeo, deerDarkMat);
    ear.position.set(-0.02, 0.95, side * 0.16);
    ear.rotation.x = side * 0.4;
    neck.add(ear);
  }
  if (hasAntlers) {
    for (const side of [1, -1]) {
      const antler = new THREE.Mesh(deerAntlerGeo, deerAntlerMat);
      antler.position.set(-0.04, 1.08, side * 0.12);
      antler.rotation.z = -0.25;
      neck.add(antler);
    }
  }
  g.add(neck);
  const legs = [];
  for (const [lx, lz] of [[0.42, 0.18], [0.42, -0.18], [-0.42, 0.18], [-0.42, -0.18]]) {
    const leg = new THREE.Group();
    leg.position.set(lx, 0.62, lz);
    const mesh = new THREE.Mesh(deerLegGeo, deerDarkMat);
    mesh.position.y = -0.31;
    mesh.castShadow = true;
    leg.add(mesh);
    g.add(leg);
    legs.push(leg);
  }
  g.position.set(x, terrainHeight(x, z), z);
  scene.add(g);
  const a = {
    group: g, neck, legs, kind: 'deer',
    home: { x, z }, heading: Math.random() * Math.PI * 2,
    state: 'idle', stateT: 1 + Math.random() * 2,
    speed: 1.15, wanderR: 45, phase: Math.random() * Math.PI * 2,
  };
  animals.push(a);
  deerList.push(a);
  return a;
}

function makeRabbit(x, z) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(rabbitBodyGeo, rabbitMat);
  body.scale.set(1.25, 0.85, 0.8);
  body.position.y = 0.24;
  body.castShadow = true;
  g.add(body);
  const head = new THREE.Mesh(rabbitHeadGeo, rabbitMat);
  head.position.set(0.28, 0.36, 0);
  head.castShadow = true;
  g.add(head);
  for (const side of [1, -1]) {
    const ear = new THREE.Mesh(rabbitEarGeo, rabbitMat);
    ear.position.set(0.26, 0.58, side * 0.07);
    ear.rotation.z = -0.15;
    g.add(ear);
  }
  g.position.set(x, terrainHeight(x, z), z);
  scene.add(g);
  const a = {
    group: g, kind: 'rabbit',
    home: { x, z }, heading: Math.random() * Math.PI * 2,
    state: 'idle', stateT: 1 + Math.random() * 2,
    speed: 1.7, wanderR: 18, phase: Math.random() * Math.PI * 2,
  };
  animals.push(a);
  rabbitList.push(a);
  return a;
}

function makeBird(cx, cz) {
  const g = new THREE.Group();
  const body = new THREE.Mesh(birdBodyGeo, birdMat);
  body.rotation.z = -Math.PI / 2; // the cone points along +X (forward)
  g.add(body);
  const wingL = new THREE.Group();
  wingL.position.set(0, 0.05, 0.08);
  const wl = new THREE.Mesh(birdWingGeo, birdMat);
  wl.position.z = 0.45;
  wingL.add(wl);
  g.add(wingL);
  const wingR = new THREE.Group();
  wingR.position.set(0, 0.05, -0.08);
  const wr = new THREE.Mesh(birdWingGeo, birdMat);
  wr.position.z = -0.45;
  wingR.add(wr);
  g.add(wingR);
  const a = {
    group: g, wingL, wingR, kind: 'bird',
    centre: { x: cx, z: cz },
    home: { x: cx, z: cz },
    angle: Math.random() * Math.PI * 2,
    angularSpeed: 0.12 + Math.random() * 0.08,
    radius: 55 + Math.random() * 36,
    height: 38 + Math.random() * 10,
    state: 'fly', stateT: 8 + Math.random() * 8,
    phase: Math.random() * Math.PI * 2,
  };
  const p = g.position;
  p.x = cx + Math.cos(a.angle) * a.radius;
  p.z = cz + Math.sin(a.angle) * a.radius;
  p.y = a.height;
  scene.add(g);
  animals.push(a);
  birdList.push(a);
  return a;
}

// One deer per forest, antlers on two of them.
makeDeer(-75, -165, true);
makeDeer(75, -165, false);
makeDeer(140, -110, true);
makeDeer(-140, -110, false);
makeDeer(-150, 85, false);
// Rabbits near the forest edges.
makeRabbit(-60, -140);
makeRabbit(90, -140);
makeRabbit(120, 100);
makeRabbit(-130, 60);
// Birds circling high over the map.
makeBird(0, -80);
makeBird(-100, 0);
makeBird(100, 40);
makeBird(-40, 120);
makeBird(60, -140);

function animalHomeOk(x, z) {
  const r = Math.hypot(x, z);
  if (r < 60) return false; // away from the castle
  if (Math.abs(x) > 195 || Math.abs(z) > 195) return false;
  if (riverDistance(x, z) < 12) return false; // not in or at the river
  if (pondDistance(x, z) < POND_R + 6) return false; // not in the pond
  return true;
}

function updateAnimals(delta, elapsed) {
  for (const a of animals) {
    a.stateT -= delta;
    if (a.stateT <= 0) {
      const roll = Math.random();
      if (a.kind === 'bird') {
        a.state = 'fly';
        a.stateT = 8 + Math.random() * 8;
      } else if (roll < 0.40) {
        a.state = 'graze';
        a.stateT = 3 + Math.random() * 4;
      } else if (roll < 0.65) {
        a.state = 'idle';
        a.stateT = 2 + Math.random() * 3;
      } else {
        a.state = 'walk';
        a.stateT = 3 + Math.random() * 3;
        // Turn toward a random nearby point that stays in good ground.
        for (let tries = 0; tries < 6; tries++) {
          const ang = Math.random() * Math.PI * 2;
          const dist = 8 + Math.random() * 18;
          const tx = a.group.position.x + Math.cos(ang) * dist;
          const tz = a.group.position.z + Math.sin(ang) * dist;
          if (animalHomeOk(tx, tz) && Math.hypot(tx - a.home.x, tz - a.home.z) < a.wanderR) {
            a.heading = Math.atan2(tz - a.group.position.z, tx - a.group.position.x);
            break;
          }
        }
      }
    }
    const p = a.group.position;
    if (a.kind === 'bird') {
      a.angle += a.angularSpeed * delta;
      p.x = a.centre.x + Math.cos(a.angle) * a.radius;
      p.z = a.centre.z + Math.sin(a.angle) * a.radius;
      p.y = a.height + Math.sin(elapsed * 0.7 + a.phase) * 1.5;
      a.group.rotation.y = Math.atan2(-Math.cos(a.angle), -Math.sin(a.angle));
      const flap = Math.sin(elapsed * 8 + a.phase) * 0.5;
      a.wingL.rotation.x = flap;
      a.wingR.rotation.x = -flap;
      continue;
    }
    if (a.state === 'walk') {
      const step = a.speed * delta;
      const nx = p.x + Math.cos(a.heading) * step;
      const nz = p.z + Math.sin(a.heading) * step;
      if (animalHomeOk(nx, nz) && Math.hypot(nx - a.home.x, nz - a.home.z) < a.wanderR) {
        p.x = nx;
        p.z = nz;
      } else {
        a.heading += Math.PI / 2; // turn away from the bad ground
      }
      // Rabbits hop while they move.
      p.y = terrainHeight(p.x, p.z) + (a.kind === 'rabbit' ? Math.abs(Math.sin(elapsed * 6 + a.phase)) * 0.3 : 0);
      a.group.rotation.y = Math.atan2(-Math.sin(a.heading), Math.cos(a.heading));
      const swing = Math.sin(elapsed * 7 + a.phase);
      if (a.legs) {
        a.legs[0].rotation.x = swing * 0.5;
        a.legs[1].rotation.x = -swing * 0.5;
        a.legs[2].rotation.x = -swing * 0.5;
        a.legs[3].rotation.x = swing * 0.5;
      }
      if (a.neck) a.neck.rotation.z += (0.15 - a.neck.rotation.z) * Math.min(1, delta * 4);
    } else if (a.state === 'graze') {
      p.y = terrainHeight(p.x, p.z);
      if (a.neck) a.neck.rotation.z += (-1.5 - a.neck.rotation.z) * Math.min(1, delta * 3);
    } else {
      // Idle: head up, legs still.
      p.y = terrainHeight(p.x, p.z);
      if (a.neck) a.neck.rotation.z += (0.15 - a.neck.rotation.z) * Math.min(1, delta * 4);
      if (a.legs) {
        for (const leg of a.legs) leg.rotation.x *= 0.9;
      }
    }
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
  const gx = Math.round(p.x / 2) * 2;
  const gz = Math.round(p.z / 2) * 2;
  ghost.position.set(
    gx,
    terrainHeight(p.x, p.z),
    gz,
  );
  ghost.visible = true;
  ghostMat.color.setHex(
    canAfford(COSTS[state.placing]) && !isInWater(gx, gz) ? 0x7ec850 : 0xd23b2e,
  );
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
let smokeTimer = 0;
let smokeIdx = 0;

function animate() {
  requestAnimationFrame(animate);
  const delta = Math.min(clock.getDelta(), 0.1);
  elapsed += delta;
  // Gentle flag wave.
  flag.rotation.y = Math.sin(elapsed * 2.2) * 0.18;
  // The river flows: scroll the streak texture along the river.
  riverWaterMat.map.offset.y -= delta * 0.02;
  // Torch flames flicker.
  for (const t of torchLights) {
    t.light.intensity = 13 + Math.sin(elapsed * 11 + t.phase) * 2 + Math.sin(elapsed * 23 + t.phase * 2) * 1;
  }
  for (let i = 0; i < torchFlames.length; i++) {
    const f = torchFlames[i];
    f.scale.set(
      1 + Math.sin(elapsed * 13 + i * 1.7) * 0.12,
      1 + Math.sin(elapsed * 17 + i) * 0.15,
      1 + Math.sin(elapsed * 13 + i * 1.7) * 0.12,
    );
  }
  // Clouds drift across the sky.
  for (const cloud of clouds) {
    cloud.position.x += cloud.userData.drift * delta;
    if (cloud.position.x > 380) cloud.position.x = -380;
  }
  // Banners sway gently.
  for (let i = 0; i < banners.length; i++) {
    banners[i].rotation.x = Math.sin(elapsed * 1.3 + i * 1.2) * 0.05;
  }
  // Chimney smoke: one slow puff at a time, round-robin through chimneys.
  smokeTimer += delta;
  if (smokeTimer >= 0.55 && chimneys.length > 0) {
    smokeTimer = 0;
    const c = chimneys[smokeIdx % chimneys.length];
    smokeIdx += 1;
    spawnParticle({
      x: c.x, y: c.y, z: c.z,
      vx: 0.25 + Math.random() * 0.2, vy: 1.1 + Math.random() * 0.4, vz: 0.1,
      life: 2.6, size: 0.8, r: 0.72, g: 0.72, b: 0.72, grow: 2.2, peak: 0.32,
    });
  }
  updateParticles(delta);
  // Economy tick every 5 seconds.
  incomeTimer += delta;
  if (incomeTimer >= 5) {
    incomeTimer -= 5;
    const inc = incomePerTick();
    state.wood += inc.wood;
    state.food += inc.food;
    state.gold += inc.gold;
    state.goldEarned += inc.gold;
    state.stone += inc.stone;
    updateHUD();
  }
  updateTowers(delta);
  updateArrows(delta);
  updateEnemies(delta, elapsed);
  updateAnimals(delta, elapsed);
  checkWaveEnd();
  controls.update();
  // Camera bounds: keep the orbit target over the playable map (build
  // placement reaches radius 100) so the camera can never be panned out
  // past the far hills looking back at the map.
  const targetR = Math.hypot(controls.target.x, controls.target.z);
  if (targetR > 110) {
    const s = 110 / targetR;
    controls.target.x *= s;
    controls.target.z *= s;
  }
  // ... and keep the camera itself inside radius 220, so the fog and the
  // far hills always hide the terrain edge from view.
  const camR = Math.hypot(camera.position.x, camera.position.z);
  if (camR > 220) {
    const s = 220 / camR;
    camera.position.x *= s;
    camera.position.z *= s;
  }
  renderer.render(scene, camera);
}

// Small debug handle used by automated tests (harmless in normal play).
window.__castle = {
  state,
  enemies,
  towers,
  arrows,
  built,
  camera,
  controls,
  groundSize: () => GROUND_SIZE,
  incomePerTick,
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
  fx: {
    particles: () => parts.length,
    clouds: () => clouds.length,
    chimneys: () => chimneys.length,
  },
  horizon: {
    fog: () => ({
      near: scene.fog.near,
      far: scene.fog.far,
      color: '#' + scene.fog.color.getHexString(),
    }),
  },
  world: {
    trees: () => forestTreeCount,
    rocks: () => rockCount,
    animals: () => animals.length,
    deer: () => deerList.length,
    deerPositions: () => deerList.map((d) => [d.group.position.x, d.group.position.z]),
    riverPoints: () => riverPoints.length,
    terrain: (x, z) => terrainHeight(x, z),
    riverZ: (x) => riverZ(x),
    riverWaterLevel: (x) => terrainHeight(x, riverZ(x)) + 1.0,
    pond: () => ({ x: POND_X, z: POND_Z, r: POND_R }),
    pondWaterLevel: () => terrainHeight(POND_X, POND_Z) + 1.0,
  },
};

updateHUD();
animate();
