# Castle Siege 3D

A Stronghold-style castle builder and siege defence game that runs entirely in
the browser. Built with Vite + Three.js. All 3D content is procedural low-poly
geometry, and all audio files are bundled locally, there are no external
models, images or CDN links, so the game is fully self-contained.

## Main goal (Saud's vision): Coding Battle

The finished game is a coding battle: the player builds their kingdom by
completing code challenges. Every building and every soldier costs one
solved code challenge, and the challenge matches the thing it unlocks: a
wall needs an Easy challenge, a tower an Easy-Medium one, a factory or a
soldier a Medium one, a barracks a Hard one. The more a thing helps, the
harder its challenge. There are 21 challenges in the bank, three variants
per kind, each with visible tests and two hidden tests, run in a Web
Worker with a time limit so an infinite loop cannot hang the game. While
a challenge is open the battle pauses. A solve buys exactly one
placement: place the building (or train the soldier) and the grant is
spent, so the next building needs a fresh challenge. The coding layer is
live now, not a later step: it is how the whole kingdom gets built.

## How to run

```bash
npm install
npm run dev      # local dev server, http://localhost:5173
npm run build    # production build into dist/
npm run preview  # serve the production build, http://localhost:4173
```

Deploy the `dist/` folder as a static site (for example a Render static site).

## Controls

- Drag to orbit the camera, scroll to zoom.
- Click a building to select it (it gets a gold outline and its name shows in
  the top left).
- `Build Wall`, `Build House`, `Build Farm`, `Build Tower`, `Build Factory`
  and `Build Barracks` are icon buttons (brick wall, house, wheat, tower,
  factory, barracks) with the cost shown as a tiny label under the icon,
  and a tooltip with the full action name. Clicking one first checks the
  cost, then opens a code challenge for that kind: solve it in the editor
  and click `Place building` to enter placement mode, then move the mouse
  over the ground to preview the building and click to build it (grid
  snapped). One solved challenge buys exactly one building: after it is
  placed, placement ends and the next building needs a fresh challenge.
  With the Wall tool, drag to build a whole straight wall line in one go;
  that line is the one placement the solve bought. Press Esc or the button
  again to cancel. A house raises the population cap by 4 and adds +1 Gold
  per income tick, a farm adds +2 Food per tick, a tower shoots arrows at
  enemies during waves, a factory adds +2 Stone per tick, a barracks
  unlocks soldier training and raises the army cap by 4. Costs: wall 10
  Stone, house 20 Wood, farm 15 Wood, tower 30 Stone + 10 Wood, factory
  25 Wood + 15 Stone, barracks 30 Wood + 20 Stone. `Train Soldier` costs
  20 Gold plus one solved soldier challenge (Medium), needs a barracks,
  and trains one royal-blue swordsman (HP 30, 1 damage per swing, army
  cap 8 + 4 per barracks). The `Remove` button demolishes a building with
  no refund.
- Resources grow every 5 seconds: +2 Wood, +2 Food, +3 Gold, +1 Stone, plus
  bonuses from farms, houses and factories.
- `Next Wave` (crossed swords icon) sends enemies marching from the map
  edge toward the keep. Wave 1 has 3 foot soldiers, each later wave adds
  2, and from wave 6 the horde grows by one extra enemy per wave, so wave
  10 has 26 enemies. Foot soldiers come from wave 1, cavalry riders (fast,
  tough, heavy hits) from wave 3, armoured brutes (slow, very tough,
  heaviest hits) from wave 4, up to 4 cavalry and 3 brutes in the late
  waves. Enemies walk straight at the keep and stop to attack whatever
  blocks them: walls, houses, farms, towers, factories and barracks all
  have hit points and can be destroyed. A player-built tower shoots one
  arrow per second at the nearest enemy in range (26 units), 2 hits kill
  a foot soldier. An enemy that reaches the keep attacks it every second:
  5 damage per foot soldier swing, 15 per cavalry swing, 20 per brute
  swing. Clearing a wave pays +20 Gold. Win by clearing wave 10; if Keep
  HP reaches 0 the castle has fallen. Both endings show a screen with the
  run stats (waves cleared, enemies defeated, gold earned, buildings
  built, challenges solved, time played) and a button to play again.
  Balance note: an empty castle falls on wave 1, walls alone cannot win
  (nothing shoots back), and a kingdom of towers, soldiers and a wall ring
  wins wave 10 with the keep hurt but standing. Build at least one tower
  before calling the first wave.
- Sound: the speaker icon button (or the `M` key) toggles sound, and the
  choice is remembered. Music starts after your first click, browsers block
  audio before any interaction. Arrow shots, hits, deaths, building, the
  wave horn, the victory fanfare, keep damage and game over all have sounds.
- The game always starts fresh. There is no save game and no leaderboard.

## Phase plan

- **Phase 1 (done):** Playable 3D scene. Terrain with gentle hills, castle
  with keep, walls, corner towers and gatehouse, village houses, trees and
  rocks, orbit camera, click to select, wall placement, resource HUD.
- **Phase 2 (done):** Economy and enemy waves. Passive income tick, build
  menu (house, farm, tower, wall), enemy waves with tower archers, keep HP
  and win/lose conditions.
- **Phase 3 (done):** Sounds and music from free sources. Arrow shots,
  enemy hits and deaths, building, wave horn, victory fanfare, keep damage,
  game over and UI clicks, plus a quiet ambient medieval music loop with a
  mute button (and M key). All audio is bundled locally in `public/audio/`.
- **Phase 4 (cancelled by Saud):** Save game and leaderboard server
  backend were built (localStorage save with autosave, Continue / New Game
  on reload, a Node/Express leaderboard API with a Postgres store) and
  then removed at Saud's request. The database was deleted, the `server/`
  directory is gone, and the game has no save game, no score submission
  and no leaderboard. The game always starts fresh.
- **Phase 5 (done):** Graphics-first visual upgrade. Procedural canvas
  textures drawn in code (ashlar stone, grass, wood planks, roof tiles,
  dirt path, courtyard flagstones), a gradient sky with a sun disc and
  drifting clouds, warmer sunlight, more detailed models (pine and
  broadleaf trees, houses with chimneys and lit windows, keep banners,
  tower pennants, flickering gate torches with one shared point light),
  and a one-draw-call particle system (arrow trails, hit sparks,
  chimney smoke, enemy dust). Merlons are merged into one mesh per wall
  to keep draw calls low. No post-processing, so the game stays fast on
  weak hardware.
- **Phase 6 (done):** Action buttons are icons (SVG brick wall, house,
  wheat, tower, crossed swords, speaker) with the cost as a tiny label
  under each icon. Save game and leaderboard are gone entirely: no save
  button, no Continue overlay, no score submission, no leaderboard panel,
  the `server/` directory is deleted, and the game always starts fresh.
- **Phase 7 (done):** Bigger ground and proper soldier characters. The
  terrain is 440 wide (about 1.8x the old 240), with hills, trees, rocks
  and two more village houses spread across the new area, fog and camera
  retuned so the whole map is viewable, and build placement works out to
  100 units from the centre. Enemies spawn at the new map edge (about
  125 units out) and are now proper low-poly humanoids: helmeted head,
  tunic torso, swinging arms and legs with a walk animation, shield and
  spear or sword, in three visual variants (red spearman, blue swordsman,
  olive spearman) with identical behaviour, speed, health and ranges.
- **Phase 8 (done, then replaced by Phase 9):** Endless horizon. The wide
  view used to show the hard cut of the square terrain, so the edge was
  hidden with denser fog (near 250, far 430, colour matched to the sky
  horizon band, the castle stays crisp even at max zoom-out), a ring of
  30 tall procedural peaks with snow caps around the map edge, and a huge
  flat disc in the fog colour under the rim so any sight line past the map
  meets fog-coloured ground. The camera target is also kept over the
  playable map (radius 110) and the camera itself inside radius 220. The
  mountain ring looked fake, so Phase 9 removed it and hid the edge with
  real rolling hills instead.
- **Phase 9 (done):** A real landscape. The mountain ring is gone for
  good; the horizon is now gentle rolling hills that rise toward the map
  edge and fade into the fog (near 230, far 420). The green land is now
  640 wide (up from 440), so the ground looks endless from max zoom-out,
  panned corners and low angles alike, with the far hills and the fog
  hiding the edge. The terrain itself rolls across the whole map while
  the castle ground stays flat. Trees grow in twelve dense forest
  clusters with varied pines and broadleaf trees, plus bushes and grass
  tufts, and open meadow is left around the castle.
  Rocks sit in natural clusters near the hills, with big boulders and
  small stones along the river banks. A winding river crosses the north
  of the map with animated flowing water, and a small pond sits in the
  south meadow; buildings cannot be placed in the water, and enemies
  wade across the shallow river on their way to the keep. A herd of five
  deer, four rabbits and five birds live in the forest and meadow: they
  wander, graze and change direction, and they never affect gameplay.
  Nothing about the castle, economy, waves or balance changed.
- **Camera fix (done):** The camera looked stuck on the castle: a drag
  barely moved it. Root cause was OrbitControls damping, which applies
  only 8% of a drag per rendered frame, so at the few frames per second
  this game runs at on weak hardware a drag took a minute to play out.
  Damping is off now, so drags, zoom and pan apply in full on the next
  frame at any frame rate. WASD / arrow keys were also added to move the
  view across the map (right-drag pans too), since left-drag only orbits
  the castle. The camera bounds are unchanged (target inside radius 110,
  camera inside radius 220), so the terrain edge stays hidden.
- **Coding Battle (done):** The game Saud asked for: every building and
  soldier costs one solved code challenge. The bank has 21 challenges in
  `src/challenges.js`, three variants per kind, graded Easy (wall, house,
  farm), Easy-Medium (tower), Medium (factory, soldier) and Hard
  (barracks), each with a story, visible tests and two hidden tests. The
  panel (`src/challengePanel.js`) runs code in a Web Worker
  (`src/challengeRunner.js`) with a time limit, shows per-test results,
  and pauses the battle while open. Build buttons and Train Soldier all
  go through the panel, with affordability and army-cap checks before it
  opens. A solved challenge buys exactly one placement: the grant is
  spent when the building lands (or when a wall drag finishes), and
  cancelling also spends it. The start screen, victory and game-over
  screens with run stats, How to Play, and a full reset (`Play again`)
  are all in.
- **Balance pass and full playthrough (done, final):** The numbers were
  measured with a combat simulator (`balance-sim.py`, a faithful
  re-implementation of the combat loop) and then verified in a real
  headless playthrough (`playthrough-test.py`). The simulator showed the
  shipped game was upside down: waves 2-3 could kill a two-tower castle
  outright, while waves 4-10 never scratched a four-tower one. The fixes:
  towers fire one arrow per second (was one per 0.8s); cavalry arrive
  from wave 3 and brutes from wave 4 (both one wave later), up to 4
  cavalry and 3 brutes late; wave size grows by one extra enemy per wave
  from wave 6, so wave 10 has 26 enemies (135 across the whole game).
  The same pass fixed the challenge gate: a solved challenge used to
  leave placement armed, so one solve bought unlimited buildings of that
  kind; now one solve buys one placement, as the Phase 2 design said.
  The playthrough test wins wave 10 the real way (real Start click, real
  challenge solves, real canvas placements, real Next Wave clicks, 6
  towers, a factory, a barracks, a wall line and 8 soldiers) with the
  keep alive but pressured, and a second run with nothing built loses on
  wave 1. Nothing else about the economy, costs or unit stats changed.

## Audio credits

Every sound and the music track come from free libraries, downloaded without
an account. Files live in `public/audio/` (MP3, mono, compressed).

| File | Used for | Source | Author | License |
| --- | --- | --- | --- | --- |
| `music.mp3` | Background music (60 s loop) | "Morgana Rides" by Kevin MacLeod, incompetech.com | Kevin MacLeod | CC-BY 4.0 |
| `shoot.mp3` | Arrow shot | "Bow & Arrow Shot", opengameart.org/content/bow-arrow-shot | ripple182 | CC-BY-SA 3.0 |
| `hit.mp3` | Enemy hit | "5 Hit Sounds + Dying", opengameart.org/content/5-hit-sounds-dying | alket | CC0 |
| `death.mp3` | Enemy death | "5 Hit Sounds + Dying", opengameart.org/content/5-hit-sounds-dying | alket | CC0 |
| `build.mp3` | Building placed | "75 CC0 breaking / falling / hit sfx", opengameart.org/content/75-cc0-breaking-falling-hit-sfx | frances | CC0 |
| `horn.mp3` | Wave start | "Their Coming (generic horn sound)", opengameart.org/content/their-coming-generic-horn-sound | StumpyStrust | CC0 |
| `victory.mp3` | Wave cleared | "Victory Fanfare Short", opengameart.org/content/victory-fanfare-short | Thalon | CC0 |
| `thud.mp3` | Keep damaged | "Thud Underfoot", opengameart.org/content/thud-underfoot | spookymodem | CC-BY 3.0 |
| `gameover.mp3` | Castle fallen | "The End (Death Screen mix)", opengameart.org/content/the-end-death-screen-mix | yd (mix by Avgvst, music by Metaruka) | CC-BY-SA 3.0 |
| `click.mp3` | UI button click | "Button Click Sound Effect", opengameart.org/content/button-click-sound-effect-cc0public-domain | qubodup | CC0 |

Notes: the "Medieval Horn" pack on OpenGameArt turned out to be a 3D model,
not audio, so the wave horn uses "Their Coming" instead. The "Build" track
on OpenGameArt is an 87 second music piece, not a placement sound, so
building uses a wood hit from the CC0 breaking/falling pack. The game over
track was trimmed to its first 12 seconds and the victory fanfare to 6
seconds; the music is a 60 second section of "Morgana Rides" with soft
fades so the loop is gentle.
