# Castle Siege 3D

A Stronghold-style castle builder and siege defence game that runs entirely in
the browser. Built with Vite + Three.js. All 3D content is procedural low-poly
geometry, there are no external models, images, audio files or CDN links, so
the game is fully self-contained.

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
- `Build Wall (10 Stone)`, `Build House (20 Wood)`, `Build Farm (15 Wood)`
  and `Build Tower (30 Stone, 10 Wood)` enter placement mode: move the mouse
  over the ground to preview the building, click to build it (grid snapped).
  Press Esc or the button again to cancel. A house raises the population cap
  by 4 and adds +1 Gold per income tick, a farm adds +2 Food per tick, a
  tower shoots arrows at enemies during waves.
- Resources grow every 5 seconds: +2 Wood, +2 Food, +3 Gold, +1 Stone, plus
  bonuses from farms and houses.
- `Next Wave` sends enemies marching from the map edge toward the keep
  (wave 1 has 3 enemies, each later wave adds 2). Corner towers and built
  towers shoot arrows at enemies in range, 2 hits kill one. An enemy that
  reaches the keep deals 10 damage. Clearing a wave pays +20 Gold. If Keep
  HP reaches 0 the castle has fallen and the page offers a restart.

## Phase plan

- **Phase 1 (done):** Playable 3D scene. Terrain with gentle hills, castle
  with keep, walls, corner towers and gatehouse, village houses, trees and
  rocks, orbit camera, click to select, wall placement, resource HUD.
- **Phase 2 (done):** Economy and enemy waves. Passive income tick, build
  menu (house, farm, tower, wall), enemy waves with tower archers, keep HP
  and win/lose conditions.
- **Phase 3: Sounds and music from free sources.** Interface clicks, battle
  sounds and ambient medieval music from free libraries (Freesound,
  OpenGameArt, Pixabay Music, Kevin MacLeod), plus polish and a start screen.
- **Phase 4: Save and leaderboard server backend.** Game progress saved on
  the server, a leaderboard, and the frontend talking to the backend API.
