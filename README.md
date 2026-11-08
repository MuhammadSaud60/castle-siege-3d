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
- `Build Wall (10 Stone)` enters placement mode: move the mouse over the
  ground to preview a wall segment, click to build it (grid snapped, costs
  10 stone). Press Esc or the button again to cancel.
- `Next Wave` advances the wave counter (enemies arrive in Phase 3).

## Phase plan

- **Phase 1 (done):** Playable 3D scene. Terrain with gentle hills, castle
  with keep, walls, corner towers and gatehouse, village houses, trees and
  rocks, orbit camera, click to select, wall placement, resource HUD.
- **Phase 2: Economy.** Gatherers and production: woodcutters, quarries and
  farms that raise Wood, Stone and Food over time, population growth, upkeep
  costs, and build costs for houses, farms and towers.
- **Phase 3: Enemy waves and siege.** Enemy units that march from the map
  edge, attack walls and the gate, archers on towers, melee defence, wave
  scaling, win and lose conditions.
- **Phase 4: Sounds and music from free sources.** Interface clicks, battle
  sounds and ambient medieval music from free libraries (Freesound,
  OpenGameArt, Pixabay Music, Kevin MacLeod), plus polish and a start screen.
