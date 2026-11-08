"""Balance simulator for Castle Siege 3D.

Faithful re-implementation of the combat loop in src/main.js, using the
exact numbers from the source (speeds, HP, ranges, damage, fire interval,
arrow speed, stop distances, wave composition). Flat terrain, dt=0.05.

Strategies are kingdoms that persist across waves 1..10 (building HP and
soldier HP carry over, no healing, exactly like the game). Each strategy
runs over several random spawn seeds; the report shows keep HP after each
wave and whether wave 10 was won.

NOT part of the shipped game. Measurement evidence for the Phase 4
balance pass only.
"""
import math
import os
import random
import sys

# Balance knobs under test (defaults = current shipped numbers).
CAV_START = int(os.environ.get("CAV_START", "3"))
CAV_CAP = int(os.environ.get("CAV_CAP", "4"))
BRUTE_START = int(os.environ.get("BRUTE_START", "4"))
BRUTE_CAP = int(os.environ.get("BRUTE_CAP", "3"))
WALL_HP = int(os.environ.get("WALL_HP", "50"))
SOLDIER_HP_KNOB = int(os.environ.get("SOLDIER_HP", "30"))
KEEP_HP_KNOB = int(os.environ.get("KEEP_HP", "100"))
COUNT_EXTRA = int(os.environ.get("COUNT_EXTRA", "1"))
HP_BONUS = int(os.environ.get("HP_BONUS", "0"))  # +HP per HP_STEP waves, 0 = off
HP_STEP = int(os.environ.get("HP_STEP", "3"))
KEEP_DMG_DIV = float(os.environ.get("KEEP_DMG_DIV", "1"))  # keep takes damage/div
TOWER_RANGE_KNOB = float(os.environ.get("TOWER_RANGE", "26"))
TOWER_INTERVAL_KNOB = float(os.environ.get("TOWER_INTERVAL", "1.0"))

DT = 0.05
KEEP_STOP = 12.0
TOWER_RANGE = TOWER_RANGE_KNOB
TOWER_FIRE_INTERVAL = TOWER_INTERVAL_KNOB
ARROW_SPEED = 32.0
ENEMY_HIT_DAMAGE = 5
ENEMY_ATTACK_INTERVAL = 1.0
BUILDING_HP = {"wall": WALL_HP, "house": 30, "farm": 20, "tower": 60,
               "factory": 40, "barracks": 50}
BUILDING_STOP = {"house": 3.0, "farm": 3.8, "tower": 2.8,
                 "factory": 4.5, "barracks": 5.2}
WALL_STOP = 1.4
ENEMY_TYPES = {
    "soldier": {"hp": 2, "damage": 5, "reach": 0.0, "speed": None},
    "cavalry": {"hp": 4, "damage": 15, "reach": 1.2, "speed": 4.2},
    "brute": {"hp": 6, "damage": 20, "reach": 0.6, "speed": 1.9},
}
SOLDIER_HP = SOLDIER_HP_KNOB
SOLDIER_DAMAGE = 1
SOLDIER_SPEED = 3.2
SOLDIER_ENGAGE = 30.0
SOLDIER_MELEE = 1.8
SOLDIER_ATTACK_INTERVAL = 1.0


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def dist_to_wall(px, pz, b):
    dx, dz = math.cos(b["angle"]), -math.sin(b["angle"])
    rx, rz = px - b["x"], pz - b["z"]
    t = max(-2.0, min(2.0, rx * dx + rz * dz))
    return math.hypot(px - (b["x"] + dx * t), pz - (b["z"] + dz * t))


class Sim:
    def __init__(self, rng):
        self.rng = rng
        self.keep_hp = KEEP_HP_KNOB
        self.towers = []   # {"x","z","cooldown"}
        self.buildings = []  # {"kind","x","z","angle","hp","maxHp"}
        self.soldiers = []  # {"x","z","hp","target","attackTimer","home"}
        self.enemies = []
        self.arrows = []  # {"x","y","z","target"}
        self.kills = 0
        self.time = 0.0

    # -- kingdom setup -------------------------------------------------
    def add_tower(self, x, z):
        self.towers.append({"x": x, "z": z, "cooldown": 0.0})
        self.buildings.append({"kind": "tower", "x": x, "z": z,
                               "angle": 0.0, "hp": 60, "maxHp": 60})

    def add_wall_ring(self, radius=30.0):
        n = round(2 * math.pi * radius / 4)
        for i in range(n):
            a = i * 2 * math.pi / n
            x, z = math.cos(a) * radius, math.sin(a) * radius
            self.buildings.append({"kind": "wall", "x": x, "z": z,
                                   "angle": a + math.pi / 2,
                                   "hp": WALL_HP, "maxHp": WALL_HP})

    def add_barracks(self, x, z):
        self.buildings.append({"kind": "barracks", "x": x, "z": z,
                               "angle": 0.0, "hp": 50, "maxHp": 50})

    def add_soldiers(self, n):
        for _ in range(n):
            i = len(self.soldiers)
            a = (i * 2.4) % (2 * math.pi)
            x, z = math.cos(a) * 16, math.sin(a) * 16
            self.soldiers.append({"x": x, "z": z, "hp": SOLDIER_HP,
                                  "target": None, "attackTimer": 0.0,
                                  "home": (x, z)})

    # -- waves ---------------------------------------------------------
    def spawn_wave(self, wave):
        count = 3 + (wave - 1) * 2 + max(0, wave - 5) * COUNT_EXTRA
        cav = min(wave - CAV_START + 1, CAV_CAP) if wave >= CAV_START else 0
        brute = min(wave - BRUTE_START + 1, BRUTE_CAP) if wave >= BRUTE_START else 0
        types = (["soldier"] * (count - cav - brute)
                 + ["cavalry"] * cav + ["brute"] * brute)
        self.rng.shuffle(types)
        for i, typ in enumerate(types):
            ang = (i / count) * 2 * math.pi + self.rng.random() * 0.6
            r = 125 + self.rng.random() * 8
            if typ == "soldier":
                speed = min(2.4 + wave * 0.15, 4.0)
            else:
                speed = ENEMY_TYPES[typ]["speed"]
            st = ENEMY_TYPES[typ]
            bonus = ((wave - 1) // HP_STEP) * HP_BONUS
            self.enemies.append({
                "x": math.cos(ang) * r, "z": math.sin(ang) * r,
                "hp": st["hp"] + bonus, "speed": speed, "damage": st["damage"],
                "reach": st["reach"], "type": typ, "target": None,
                "attackTimer": 0.0})

    def find_blocker(self, px, pz, reach):
        best, best_d = None, float("inf")
        for b in self.buildings:
            if b["kind"] == "wall":
                d = dist_to_wall(px, pz, b)
                stop = WALL_STOP + reach
            else:
                d = dist((px, pz), (b["x"], b["z"]))
                stop = BUILDING_STOP[b["kind"]] + reach
            if d <= stop and d < best_d:
                best, best_d = b, d
        return best

    def step(self):
        dt = DT
        self.time += dt
        # Towers fire at the nearest enemy in range.
        for t in self.towers:
            t["cooldown"] -= dt
            if t["cooldown"] > 0:
                continue
            best, best_d = None, TOWER_RANGE
            for e in self.enemies:
                d = dist((e["x"], e["z"]), (t["x"], t["z"]))
                if d < best_d:
                    best, best_d = e, d
            if best is not None:
                self.arrows.append({"x": t["x"], "y": 6.5, "z": t["z"],
                                    "target": best})
                t["cooldown"] = TOWER_FIRE_INTERVAL
        # Arrows fly; a hit deals 1 damage.
        for i in range(len(self.arrows) - 1, -1, -1):
            a = self.arrows[i]
            tgt = a["target"]
            if tgt not in self.enemies:
                self.arrows.pop(i)
                continue
            dx, dy, dz = tgt["x"] - a["x"], 1.2 - a["y"], tgt["z"] - a["z"]
            d = math.sqrt(dx * dx + dy * dy + dz * dz)
            if d < 1.4:
                self.arrows.pop(i)
                tgt["hp"] -= 1
                if tgt["hp"] <= 0:
                    self.enemies.remove(tgt)
                    self.kills += 1
                continue
            step_len = ARROW_SPEED * dt
            a["x"] += dx / d * step_len
            a["y"] += dy / d * step_len
            a["z"] += dz / d * step_len
        # Enemies: fight a nearby soldier, attack a blocker/keep, or walk.
        for e in list(self.enemies):
            if self.keep_hp <= 0:
                return
            px, pz = e["x"], e["z"]
            d_keep = math.hypot(px, pz)
            near, near_d = None, 2.2
            for s in self.soldiers:
                sd = dist((s["x"], s["z"]), (px, pz))
                if sd < near_d:
                    near, near_d = s, sd
            if near is not None:
                if e["target"] and e["target"] != "keep":
                    e["target"] = None
                e["attackTimer"] -= dt
                if e["attackTimer"] <= 0:
                    e["attackTimer"] = ENEMY_ATTACK_INTERVAL
                    near["hp"] -= e["damage"]
                    if near["hp"] <= 0:
                        self.soldiers.remove(near)
                continue
            if e["target"] and e["target"] != "keep" \
                    and e["target"] not in self.buildings:
                e["target"] = None
            if not e["target"]:
                blocker = self.find_blocker(px, pz, e["reach"])
                if blocker is not None:
                    e["target"] = blocker
                    e["attackTimer"] = 0.4
                elif d_keep < KEEP_STOP:
                    e["target"] = "keep"
                    e["attackTimer"] = 0.4
            if e["target"]:
                e["attackTimer"] -= dt
                if e["attackTimer"] <= 0:
                    e["attackTimer"] = ENEMY_ATTACK_INTERVAL
                    if e["target"] == "keep":
                        import math as _m
                        self.keep_hp -= _m.ceil(e["damage"] / KEEP_DMG_DIV)
                    else:
                        b = e["target"]
                        b["hp"] -= e["damage"]
                        if b["hp"] <= 0:
                            self.buildings.remove(b)
                            if b["kind"] == "tower":
                                self.towers = [t for t in self.towers
                                               if not (t["x"] == b["x"]
                                                       and t["z"] == b["z"])]
                continue
            step_len = e["speed"] * dt
            e["x"] += (-px / d_keep) * step_len
            e["z"] += (-pz / d_keep) * step_len
        # Soldiers: engage, fight, or walk home.
        for s in list(self.soldiers):
            if s["target"] and s["target"] not in self.enemies:
                s["target"] = None
            if not s["target"]:
                best, best_d = None, SOLDIER_ENGAGE
                for e in self.enemies:
                    d = dist((s["x"], s["z"]), (e["x"], e["z"]))
                    if d < best_d:
                        best, best_d = e, d
                s["target"] = best
            if s["target"]:
                e = s["target"]
                dx, dz = e["x"] - s["x"], e["z"] - s["z"]
                d = math.hypot(dx, dz)
                if d > SOLDIER_MELEE:
                    step_len = min(SOLDIER_SPEED * dt, d - SOLDIER_MELEE)
                    s["x"] += dx / d * step_len
                    s["z"] += dz / d * step_len
                else:
                    s["attackTimer"] -= dt
                    if s["attackTimer"] <= 0:
                        s["attackTimer"] = SOLDIER_ATTACK_INTERVAL
                        e["hp"] -= SOLDIER_DAMAGE
                        if e["hp"] <= 0:
                            self.enemies.remove(e)
                            self.kills += 1
                            s["target"] = None
                continue
            hx, hz = s["home"][0] - s["x"], s["home"][1] - s["z"]
            hd = math.hypot(hx, hz)
            if hd > 0.6:
                step_len = min(SOLDIER_SPEED * dt, hd)
                s["x"] += hx / hd * step_len
                s["z"] += hz / hd * step_len

    def run_wave(self, wave, max_time=400.0):
        self.spawn_wave(wave)
        t0 = self.time
        while self.enemies and self.keep_hp > 0 \
                and self.time - t0 < max_time:
            self.step()
        return self.keep_hp


# -- strategies: kingdom build-up per wave ----------------------------
def towers_at(sim, n, radius=16.0):
    # Top the tower count up to n (never remove or duplicate).
    have = len(sim.towers)
    for i in range(have, n):
        a = i * 2 * math.pi / 6  # 6 slots, 60 degrees apart
        sim.add_tower(round(math.cos(a) * radius),
                      round(math.sin(a) * radius))


def setup_passive(sim, wave):
    pass


def setup_walls_only(sim, wave):
    if wave == 1:
        sim.add_wall_ring(30.0)


def setup_towers2(sim, wave):
    if wave == 1:
        towers_at(sim, 2)


def setup_towers4(sim, wave):
    if wave == 1:
        towers_at(sim, 4)


def setup_towers6(sim, wave):
    if wave == 1:
        towers_at(sim, 6)


def setup_competent(sim, wave):
    # Sensible player pace: 2 towers for wave 1, a 3rd before wave 2
    # (30 Stone is 10 income ticks of waiting), a 4th for wave 4,
    # barracks + 4 soldiers for wave 5, 5th tower + 2 more soldiers
    # for wave 7, 6th tower + 2 more for wave 9.
    if wave == 1:
        towers_at(sim, 2)
    elif wave == 2:
        towers_at(sim, 3)
    elif wave == 4:
        towers_at(sim, 4)
    elif wave == 5:
        sim.add_barracks(34, -34)
        sim.add_soldiers(4)
    elif wave == 7:
        towers_at(sim, 5)
        sim.add_soldiers(2)
    elif wave == 9:
        towers_at(sim, 6)
        sim.add_soldiers(2)


def setup_competent_walls(sim, wave):
    # Same as competent, plus a full wall ring at radius 30 from wave 5.
    setup_competent(sim, wave)
    if wave == 5:
        sim.add_wall_ring(30.0)


STRATEGIES = [
    ("passive (nothing built)", setup_passive),
    ("walls only (full ring r=30)", setup_walls_only),
    ("2 towers only", setup_towers2),
    ("4 towers only", setup_towers4),
    ("6 towers only", setup_towers6),
    ("competent (towers + soldiers, progressive)", setup_competent),
    ("competent + full wall ring from wave 5", setup_competent_walls),
]


def run_strategy(name, setup, seeds=8):
    print(f"--- {name} ---", flush=True)
    wins = 0
    for seed in range(seeds):
        rng = random.Random(1000 + seed)
        sim = Sim(rng)
        hp_trace = []
        died_at = None
        for wave in range(1, 11):
            setup(sim, wave)
            sim.run_wave(wave)
            hp_trace.append(sim.keep_hp)
            if sim.keep_hp <= 0:
                died_at = wave
                break
        if died_at is None:
            wins += 1
        print(f"  seed {seed}: keep HP by wave {hp_trace} "
              f"kills={sim.kills} soldiers left={len(sim.soldiers)} "
              f"buildings left={len(sim.buildings)} "
              f"{'WON' if died_at is None else 'DIED wave ' + str(died_at)}",
              flush=True)
    print(f"  => won {wins}/{seeds}", flush=True)
    return wins


if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    for name, setup in STRATEGIES:
        if only and only not in name:
            continue
        run_strategy(name, setup)
