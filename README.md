# Castle Siege 3D

A Stronghold-style castle builder and siege defence game that runs entirely in
the browser. Built with Vite + Three.js. All 3D content is procedural low-poly
geometry, and all audio files are bundled locally, there are no external
models, images or CDN links, so the game is fully self-contained.

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
- `Build Wall`, `Build House`, `Build Farm` and `Build Tower` are icon
  buttons (brick wall, house, wheat, tower) with the cost shown as a tiny
  label under the icon, and a tooltip with the full action name. Clicking
  one enters placement mode: move the mouse over the ground to preview the
  building, click to build it (grid snapped). Press Esc or the button again
  to cancel. A house raises the population cap by 4 and adds +1 Gold per
  income tick, a farm adds +2 Food per tick, a tower shoots arrows at
  enemies during waves. Costs: wall 10 Stone, house 20 Wood, farm 15 Wood,
  tower 30 Stone + 10 Wood.
- Resources grow every 5 seconds: +2 Wood, +2 Food, +3 Gold, +1 Stone, plus
  bonuses from farms and houses.
- `Next Wave` (crossed swords icon) sends enemies marching from the map
  edge toward the keep (wave 1 has 3 enemies, each later wave adds 2).
  Corner towers and built towers shoot arrows at enemies in range, 2 hits
  kill one. An enemy that reaches the keep deals 10 damage. Clearing a
  wave pays +20 Gold. If Keep HP reaches 0 the castle has fallen and the
  page offers a restart.
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
- **Phase 8 (done):** Endless horizon. The wide view used to show the hard
  cut of the square terrain, so the edge is hidden three ways: denser fog
  (near 250, far 430, colour matched to the sky horizon band, the castle
  stays crisp even at max zoom-out), a ring of 30 tall procedural peaks
  with snow caps around the map edge, and a huge flat disc in the fog
  // colour under the rim so any sight line past the map meets fog-coloured
  ground. The camera target is also kept over the playable map (radius
  110) and the camera itself inside the mountain ring (radius 220) so the
  view can never be panned out among the mountains. The
  playable ground is still 440 wide, and nothing about gameplay changed.

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
