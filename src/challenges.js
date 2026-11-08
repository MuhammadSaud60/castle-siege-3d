// Castle Siege 3D - code challenge bank.
// 7 actions x 3 variants = 21 challenges. One new concept per step,
// clear instructions, immediate verification, no penalty for wrong tries.
// Difficulty ladder: wall (arithmetic), house and farm (conditionals),
// tower (loops), factory (arrays), soldier (loops + conditionals),
// barracks (objects and higher-order functions).
// Every challenge: id, title, difficulty, story, description, examples,
// constraints, functionName, starterCode, visibleTests (3), hiddenTests (2),
// hint. All tests are deterministic.

export const CHALLENGE_KINDS = ['wall', 'house', 'farm', 'tower', 'factory', 'barracks', 'soldier'];

export const CHALLENGES = [
  // ---------------------------------------------------------------- wall
  {
    id: 'wall-1',
    kind: 'wall',
    title: 'Stones for a Wall',
    difficulty: 'Easy',
    story: 'The mason counts stones before the first wall goes up.',
    description: 'Each unit of wall length needs 3 stones. Write stonesForLength(length) to return how many stones a wall of the given length needs.',
    examples: [
      { input: 'stonesForLength(5)', output: '15', explanation: '5 units of wall, 3 stones each: 5 x 3 = 15.' },
      { input: 'stonesForLength(0)', output: '0', explanation: 'A wall of length 0 needs no stones.' },
      { input: 'stonesForLength(12)', output: '36', explanation: '12 x 3 = 36.' },
    ],
    constraints: ['length is an integer from 0 to 100'],
    functionName: 'stonesForLength',
    starterCode: 'function stonesForLength(length) {\n  // Return the stones needed for a wall of this length.\n  return 0;\n}',
    visibleTests: [
      { args: [5], expected: 15 },
      { args: [0], expected: 0 },
      { args: [12], expected: 36 },
    ],
    hiddenTests: [
      { args: [1], expected: 3 },
      { args: [20], expected: 60 },
    ],
    hint: 'Multiply the length by 3.',
  },
  {
    id: 'wall-2',
    kind: 'wall',
    title: 'Tall Walls Cost More',
    difficulty: 'Easy',
    story: 'A taller wall needs more stone in every row.',
    description: 'A wall needs 1 stone per unit of length for each unit of height. Write stonesForWall(length, height) to return the total stones needed.',
    examples: [
      { input: 'stonesForWall(4, 3)', output: '12', explanation: '4 long and 3 high: 4 x 3 = 12.' },
      { input: 'stonesForWall(10, 1)', output: '10', explanation: 'A low wall one unit high needs 10 stones.' },
      { input: 'stonesForWall(0, 5)', output: '0', explanation: 'No length means no wall, however tall.' },
    ],
    constraints: ['length and height are integers from 0 to 50'],
    functionName: 'stonesForWall',
    starterCode: 'function stonesForWall(length, height) {\n  // Return length times height.\n  return 0;\n}',
    visibleTests: [
      { args: [4, 3], expected: 12 },
      { args: [10, 1], expected: 10 },
      { args: [0, 5], expected: 0 },
    ],
    hiddenTests: [
      { args: [7, 7], expected: 49 },
      { args: [3, 9], expected: 27 },
    ],
    hint: 'Total stones = length times height.',
  },
  {
    id: 'wall-3',
    kind: 'wall',
    title: 'Stone Left Over',
    difficulty: 'Easy',
    story: 'The quarry master wants to know what stone is left after the wall.',
    description: 'Each unit of wall length uses 3 stones. Write stoneLeft(stone, length) to return how many stones remain after building a wall of the given length. The answer is never below 0: if the wall needs more stone than you have, return 0.',
    examples: [
      { input: 'stoneLeft(50, 10)', output: '20', explanation: 'The wall needs 30 stones, so 50 - 30 = 20 remain.' },
      { input: 'stoneLeft(10, 5)', output: '0', explanation: 'The wall needs 15 stones but only 10 are there, so nothing is left.' },
      { input: 'stoneLeft(100, 7)', output: '79', explanation: '100 - 21 = 79.' },
    ],
    constraints: ['stone is an integer from 0 to 500', 'length is an integer from 0 to 100'],
    functionName: 'stoneLeft',
    starterCode: 'function stoneLeft(stone, length) {\n  // Subtract the wall cost, but never go below 0.\n  return 0;\n}',
    visibleTests: [
      { args: [50, 10], expected: 20 },
      { args: [10, 5], expected: 0 },
      { args: [100, 7], expected: 79 },
    ],
    hiddenTests: [
      { args: [30, 10], expected: 0 },
      { args: [25, 4], expected: 13 },
    ],
    hint: 'Work out length x 3, subtract it from stone, and use Math.max(0, ...) so the result never goes below 0.',
  },
  // ---------------------------------------------------------------- house
  {
    id: 'house-1',
    kind: 'house',
    title: 'Room for the Family',
    difficulty: 'Easy',
    story: 'A family moves into the castle grounds. Does the house fit them?',
    description: 'Each room sleeps 2 people. Write canHouse(family, rooms) to return true when the rooms can sleep the whole family, and false otherwise.',
    examples: [
      { input: 'canHouse(5, 3)', output: 'true', explanation: '3 rooms sleep 6 people, and the family has 5.' },
      { input: 'canHouse(7, 3)', output: 'false', explanation: '3 rooms sleep only 6 people, but the family has 7.' },
      { input: 'canHouse(4, 2)', output: 'true', explanation: '2 rooms sleep exactly 4 people.' },
    ],
    constraints: ['family is an integer from 0 to 20', 'rooms is an integer from 0 to 10'],
    functionName: 'canHouse',
    starterCode: 'function canHouse(family, rooms) {\n  // Return true when rooms x 2 can sleep the whole family.\n  return false;\n}',
    visibleTests: [
      { args: [5, 3], expected: true },
      { args: [7, 3], expected: false },
      { args: [4, 2], expected: true },
    ],
    hiddenTests: [
      { args: [1, 1], expected: true },
      { args: [9, 4], expected: false },
    ],
    hint: 'Compare rooms * 2 with family using >=.',
  },
  {
    id: 'house-2',
    kind: 'house',
    title: 'Taxes from Houses',
    difficulty: 'Easy',
    story: 'Every house pays tax to the keep. A market nearby brings in extra gold.',
    description: 'Each house pays 3 gold in tax. If the village has a market, the keep gains 5 extra gold on top. Write taxIncome(houses, hasMarket) to return the total gold.',
    examples: [
      { input: 'taxIncome(4, false)', output: '12', explanation: '4 houses x 3 gold = 12, no market bonus.' },
      { input: 'taxIncome(4, true)', output: '17', explanation: '12 gold in tax plus the 5 gold market bonus.' },
      { input: 'taxIncome(0, false)', output: '0', explanation: 'No houses, no tax.' },
    ],
    constraints: ['houses is an integer from 0 to 50', 'hasMarket is true or false'],
    functionName: 'taxIncome',
    starterCode: 'function taxIncome(houses, hasMarket) {\n  // 3 gold per house, plus 5 extra gold when hasMarket is true.\n  return 0;\n}',
    visibleTests: [
      { args: [4, false], expected: 12 },
      { args: [4, true], expected: 17 },
      { args: [0, false], expected: 0 },
    ],
    hiddenTests: [
      { args: [2, true], expected: 11 },
      { args: [10, false], expected: 30 },
    ],
    hint: 'Start with houses * 3, then add 5 only when hasMarket is true.',
  },
  {
    id: 'house-3',
    kind: 'house',
    title: 'Does the House Need Repair?',
    difficulty: 'Easy',
    story: 'Old walls and cracked roofs will not survive the winter siege.',
    description: 'A house needs repair when it is older than 20 years OR its damage is above 50. Write needsRepair(age, damage) to return true when the house needs repair, and false otherwise.',
    examples: [
      { input: 'needsRepair(25, 10)', output: 'true', explanation: '25 years old is older than 20, so it needs repair.' },
      { input: 'needsRepair(10, 60)', output: 'true', explanation: 'Damage of 60 is above 50, so it needs repair.' },
      { input: 'needsRepair(5, 10)', output: 'false', explanation: 'Young and barely damaged, no repair needed.' },
    ],
    constraints: ['age is an integer from 0 to 100', 'damage is an integer from 0 to 100'],
    functionName: 'needsRepair',
    starterCode: 'function needsRepair(age, damage) {\n  // Return true when age is over 20 or damage is over 50.\n  return false;\n}',
    visibleTests: [
      { args: [25, 10], expected: true },
      { args: [10, 60], expected: true },
      { args: [5, 10], expected: false },
    ],
    hiddenTests: [
      { args: [20, 50], expected: false },
      { args: [21, 0], expected: true },
    ],
    hint: 'Use || to combine the two checks. Exactly 20 years or exactly 50 damage does not count.',
  },
  // ---------------------------------------------------------------- farm
  {
    id: 'farm-1',
    kind: 'farm',
    title: 'Can We Plant?',
    difficulty: 'Easy',
    story: 'The fields are ready, but seeds need water and sun.',
    description: 'A crop can be planted when there are at least 4 units of water AND the day is sunny. Write canPlant(water, sunny) to return true when planting is possible, and false otherwise.',
    examples: [
      { input: 'canPlant(5, true)', output: 'true', explanation: 'Enough water and a sunny day.' },
      { input: 'canPlant(3, true)', output: 'false', explanation: 'Only 3 water, but 4 are needed.' },
      { input: 'canPlant(6, false)', output: 'false', explanation: 'Plenty of water, but no sun.' },
    ],
    constraints: ['water is an integer from 0 to 20', 'sunny is true or false'],
    functionName: 'canPlant',
    starterCode: 'function canPlant(water, sunny) {\n  // Return true when water is at least 4 and sunny is true.\n  return false;\n}',
    visibleTests: [
      { args: [5, true], expected: true },
      { args: [3, true], expected: false },
      { args: [6, false], expected: false },
    ],
    hiddenTests: [
      { args: [4, true], expected: true },
      { args: [10, false], expected: false },
    ],
    hint: 'Use && to require both conditions at once.',
  },
  {
    id: 'farm-2',
    kind: 'farm',
    title: 'Harvest Yield',
    difficulty: 'Easy',
    story: 'Rain makes the fields generous. Count the harvest before winter.',
    description: 'Each farm plot yields 4 food. When it rains, each plot yields 2 extra food. Write harvestYield(plots, rain) to return the total food harvested.',
    examples: [
      { input: 'harvestYield(3, false)', output: '12', explanation: '3 plots x 4 food = 12, no rain bonus.' },
      { input: 'harvestYield(3, true)', output: '18', explanation: '12 food plus 3 plots x 2 extra = 18.' },
      { input: 'harvestYield(0, true)', output: '0', explanation: 'No plots, no harvest.' },
    ],
    constraints: ['plots is an integer from 0 to 50', 'rain is true or false'],
    functionName: 'harvestYield',
    starterCode: 'function harvestYield(plots, rain) {\n  // 4 food per plot, plus 2 extra per plot when rain is true.\n  return 0;\n}',
    visibleTests: [
      { args: [3, false], expected: 12 },
      { args: [3, true], expected: 18 },
      { args: [0, true], expected: 0 },
    ],
    hiddenTests: [
      { args: [5, true], expected: 30 },
      { args: [2, false], expected: 8 },
    ],
    hint: 'Add the rain bonus only when rain is true: plots * 4 + (rain ? plots * 2 : 0).',
  },
  {
    id: 'farm-3',
    kind: 'farm',
    title: 'Food for Winter',
    difficulty: 'Easy',
    story: 'Winter is coming. The granary must feed everyone until spring.',
    description: 'Each person needs 5 food to survive the winter. Write foodForWinter(food, people) to return true when the stored food is enough for everyone, and false otherwise.',
    examples: [
      { input: 'foodForWinter(30, 5)', output: 'true', explanation: '5 people need 25 food, and 30 are stored.' },
      { input: 'foodForWinter(20, 5)', output: 'false', explanation: '5 people need 25 food, but only 20 are stored.' },
      { input: 'foodForWinter(25, 5)', output: 'true', explanation: 'Exactly enough food.' },
    ],
    constraints: ['food is an integer from 0 to 500', 'people is an integer from 0 to 100'],
    functionName: 'foodForWinter',
    starterCode: 'function foodForWinter(food, people) {\n  // Return true when food covers people x 5.\n  return false;\n}',
    visibleTests: [
      { args: [30, 5], expected: true },
      { args: [20, 5], expected: false },
      { args: [25, 5], expected: true },
    ],
    hiddenTests: [
      { args: [0, 1], expected: false },
      { args: [100, 20], expected: true },
    ],
    hint: 'Compare food with people * 5 using >=.',
  },
  // ---------------------------------------------------------------- tower
  {
    id: 'tower-1',
    kind: 'tower',
    title: 'Arrows for the Waves',
    difficulty: 'Easy-Medium',
    story: 'The tower keeper stocks arrows before each wave of attackers.',
    description: 'Each enemy takes 3 arrows to bring down. waves is a list with the number of enemies in each wave. Write totalArrows(waves) to return the total arrows needed for all waves.',
    examples: [
      { input: 'totalArrows([2, 3])', output: '15', explanation: '5 enemies in total, 3 arrows each: 5 x 3 = 15.' },
      { input: 'totalArrows([0])', output: '0', explanation: 'No enemies, no arrows.' },
      { input: 'totalArrows([5, 5, 5])', output: '45', explanation: '15 enemies x 3 arrows = 45.' },
    ],
    constraints: ['waves is a list of integers from 0 to 50', 'waves has at most 10 entries'],
    functionName: 'totalArrows',
    starterCode: 'function totalArrows(waves) {\n  // Add up the enemies in all waves, then multiply by 3.\n  return 0;\n}',
    visibleTests: [
      { args: [[2, 3]], expected: 15 },
      { args: [[0]], expected: 0 },
      { args: [[5, 5, 5]], expected: 45 },
    ],
    hiddenTests: [
      { args: [[1, 1, 1, 1]], expected: 12 },
      { args: [[]], expected: 0 },
    ],
    hint: 'Loop over the list, add every count to a total, then return total * 3.',
  },
  {
    id: 'tower-2',
    kind: 'tower',
    title: 'Count the Goblins',
    difficulty: 'Easy-Medium',
    story: 'The lookout calls out what is coming. Goblins are fast, so they get counted first.',
    description: 'types is a list of enemy types, like "goblin" and "orc". Write countGoblins(types) to return how many entries are "goblin".',
    examples: [
      { input: 'countGoblins(["goblin", "orc", "goblin"])', output: '2', explanation: 'Two of the three entries are goblins.' },
      { input: 'countGoblins([])', output: '0', explanation: 'An empty list has no goblins.' },
      { input: 'countGoblins(["orc"])', output: '0', explanation: 'Only an orc, no goblins.' },
    ],
    constraints: ['types is a list of strings', 'types has at most 20 entries'],
    functionName: 'countGoblins',
    starterCode: 'function countGoblins(types) {\n  // Count how many entries equal "goblin".\n  return 0;\n}',
    visibleTests: [
      { args: [['goblin', 'orc', 'goblin']], expected: 2 },
      { args: [[]], expected: 0 },
      { args: [['orc']], expected: 0 },
    ],
    hiddenTests: [
      { args: [['goblin']], expected: 1 },
      { args: [['orc', 'orc']], expected: 0 },
    ],
    hint: 'Loop over the list and add 1 to a counter each time the entry equals "goblin".',
  },
  {
    id: 'tower-3',
    kind: 'tower',
    title: 'Enemies in Range',
    difficulty: 'Easy-Medium',
    story: 'A tower can only shoot as far as its range. The archers need a count.',
    description: 'distances is a list of how far away each enemy is. Write enemiesInRange(range, distances) to return how many enemies are at a distance of range or closer.',
    examples: [
      { input: 'enemiesInRange(10, [5, 12, 8])', output: '2', explanation: 'Enemies at 5 and 8 are within range 10; the one at 12 is not.' },
      { input: 'enemiesInRange(5, [6, 7])', output: '0', explanation: 'Both enemies are out of range.' },
      { input: 'enemiesInRange(20, [1, 2, 3])', output: '3', explanation: 'All three are within range.' },
    ],
    constraints: ['range is an integer from 0 to 100', 'distances is a list of integers from 0 to 100'],
    functionName: 'enemiesInRange',
    starterCode: 'function enemiesInRange(range, distances) {\n  // Count the distances that are less than or equal to range.\n  return 0;\n}',
    visibleTests: [
      { args: [10, [5, 12, 8]], expected: 2 },
      { args: [5, [6, 7]], expected: 0 },
      { args: [20, [1, 2, 3]], expected: 3 },
    ],
    hiddenTests: [
      { args: [0, [0]], expected: 1 },
      { args: [3, [3, 4]], expected: 1 },
    ],
    hint: 'Loop over distances and count each one where distance <= range.',
  },
  // ---------------------------------------------------------------- factory
  {
    id: 'factory-1',
    kind: 'factory',
    title: 'Total Stone Output',
    difficulty: 'Medium',
    story: 'The quarries report their stone. The keep needs the grand total.',
    description: 'outputs is a list of how much stone each factory produced. Write totalStone(outputs) to return the sum of all outputs.',
    examples: [
      { input: 'totalStone([10, 20, 5])', output: '35', explanation: '10 + 20 + 5 = 35.' },
      { input: 'totalStone([])', output: '0', explanation: 'No factories, no stone.' },
      { input: 'totalStone([7])', output: '7', explanation: 'A single factory produced 7.' },
    ],
    constraints: ['outputs is a list of integers from 0 to 100', 'outputs has at most 20 entries'],
    functionName: 'totalStone',
    starterCode: 'function totalStone(outputs) {\n  // Add up every number in the list.\n  return 0;\n}',
    visibleTests: [
      { args: [[10, 20, 5]], expected: 35 },
      { args: [[]], expected: 0 },
      { args: [[7]], expected: 7 },
    ],
    hiddenTests: [
      { args: [[1, 2, 3, 4]], expected: 10 },
      { args: [[100, 0]], expected: 100 },
    ],
    hint: 'Start a total at 0, loop over the list, and add each value.',
  },
  {
    id: 'factory-2',
    kind: 'factory',
    title: 'Best Factory',
    difficulty: 'Medium',
    story: 'The king rewards the hardest working factory. Find the top producer.',
    description: 'outputs is a list of how much stone each factory produced. Write bestFactory(outputs) to return the largest output. When the list is empty, return 0.',
    examples: [
      { input: 'bestFactory([3, 9, 4])', output: '9', explanation: '9 is the largest output.' },
      { input: 'bestFactory([])', output: '0', explanation: 'No factories, so the best output is 0.' },
      { input: 'bestFactory([5])', output: '5', explanation: 'Only one factory, it is the best.' },
    ],
    constraints: ['outputs is a list of integers from -10 to 100', 'outputs has at most 20 entries'],
    functionName: 'bestFactory',
    starterCode: 'function bestFactory(outputs) {\n  // Return the largest number, or 0 when the list is empty.\n  return 0;\n}',
    visibleTests: [
      { args: [[3, 9, 4]], expected: 9 },
      { args: [[]], expected: 0 },
      { args: [[5]], expected: 5 },
    ],
    hiddenTests: [
      { args: [[8, 8]], expected: 8 },
      { args: [[-3, -1]], expected: -1 },
    ],
    hint: 'Keep a best value, start it at the first entry, and replace it whenever a larger one appears. Handle the empty list first.',
  },
  {
    id: 'factory-3',
    kind: 'factory',
    title: 'Factories Above Target',
    difficulty: 'Medium',
    story: 'The keep sets a production target. Which factories beat it?',
    description: 'outputs is a list of factory outputs and min is the target. Write factoriesAbove(outputs, min) to return how many factories produced more than min.',
    examples: [
      { input: 'factoriesAbove([4, 9, 2, 7], 5)', output: '2', explanation: '9 and 7 are above 5; 4 and 2 are not.' },
      { input: 'factoriesAbove([1, 2], 10)', output: '0', explanation: 'No factory reaches 10.' },
      { input: 'factoriesAbove([6, 6, 6], 5)', output: '3', explanation: 'All three factories beat 5.' },
    ],
    constraints: ['outputs is a list of integers from 0 to 100', 'min is an integer from 0 to 100'],
    functionName: 'factoriesAbove',
    starterCode: 'function factoriesAbove(outputs, min) {\n  // Count the outputs that are greater than min.\n  return 0;\n}',
    visibleTests: [
      { args: [[4, 9, 2, 7], 5], expected: 2 },
      { args: [[1, 2], 10], expected: 0 },
      { args: [[6, 6, 6], 5], expected: 3 },
    ],
    hiddenTests: [
      { args: [[10], 9], expected: 1 },
      { args: [[], 0], expected: 0 },
    ],
    hint: 'Loop over outputs and count each value where value > min. Exactly equal to min does not count.',
  },
  // ---------------------------------------------------------------- soldier
  {
    id: 'soldier-1',
    kind: 'soldier',
    title: 'Soldiers Needed',
    difficulty: 'Medium',
    story: 'One soldier can hold back two enemies. How many must march out?',
    description: 'Each soldier can hold 2 enemies. Write soldiersNeeded(enemies) to return how many soldiers are needed to hold all the enemies. A leftover enemy still needs a whole soldier, so round up.',
    examples: [
      { input: 'soldiersNeeded(7)', output: '4', explanation: '7 enemies need 3.5 soldiers, rounded up to 4.' },
      { input: 'soldiersNeeded(6)', output: '3', explanation: '6 enemies divide evenly: 3 soldiers.' },
      { input: 'soldiersNeeded(0)', output: '0', explanation: 'No enemies, no soldiers needed.' },
    ],
    constraints: ['enemies is an integer from 0 to 100'],
    functionName: 'soldiersNeeded',
    starterCode: 'function soldiersNeeded(enemies) {\n  // Each soldier holds 2 enemies. Round up.\n  return 0;\n}',
    visibleTests: [
      { args: [7], expected: 4 },
      { args: [6], expected: 3 },
      { args: [0], expected: 0 },
    ],
    hiddenTests: [
      { args: [1], expected: 1 },
      { args: [9], expected: 5 },
    ],
    hint: 'Use Math.ceil(enemies / 2).',
  },
  {
    id: 'soldier-2',
    kind: 'soldier',
    title: 'Can the Line Hold?',
    difficulty: 'Medium',
    story: 'The captain looks at the line of soldiers and the horde beyond it.',
    description: 'Each soldier can hold 2 enemies. Write canHold(soldiers, enemies) to return true when the soldiers can hold all the enemies, and false otherwise.',
    examples: [
      { input: 'canHold(3, 6)', output: 'true', explanation: '3 soldiers hold 6 enemies, exactly enough.' },
      { input: 'canHold(2, 6)', output: 'false', explanation: '2 soldiers hold only 4 enemies, but 6 are coming.' },
      { input: 'canHold(0, 0)', output: 'true', explanation: 'No soldiers and no enemies: the line holds.' },
    ],
    constraints: ['soldiers is an integer from 0 to 50', 'enemies is an integer from 0 to 100'],
    functionName: 'canHold',
    starterCode: 'function canHold(soldiers, enemies) {\n  // Return true when soldiers x 2 covers the enemies.\n  return false;\n}',
    visibleTests: [
      { args: [3, 6], expected: true },
      { args: [2, 6], expected: false },
      { args: [0, 0], expected: true },
    ],
    hiddenTests: [
      { args: [5, 11], expected: false },
      { args: [5, 10], expected: true },
    ],
    hint: 'Compare soldiers * 2 with enemies using >=.',
  },
  {
    id: 'soldier-3',
    kind: 'soldier',
    title: 'Survivors After Battle',
    difficulty: 'Medium',
    story: 'Wave after wave, the losses add up. Count who is still standing.',
    description: 'losses is a list of how many soldiers fell in each wave. Write survivors(soldiers, losses) to return how many soldiers are left. The answer is never below 0.',
    examples: [
      { input: 'survivors(10, [2, 3])', output: '5', explanation: '10 soldiers lost 2 then 3, leaving 5.' },
      { input: 'survivors(3, [5])', output: '0', explanation: 'More fell than were there, so 0 remain.' },
      { input: 'survivors(5, [])', output: '5', explanation: 'No losses, all 5 remain.' },
    ],
    constraints: ['soldiers is an integer from 0 to 100', 'losses is a list of integers from 0 to 50'],
    functionName: 'survivors',
    starterCode: 'function survivors(soldiers, losses) {\n  // Subtract every loss, but never go below 0.\n  return 0;\n}',
    visibleTests: [
      { args: [10, [2, 3]], expected: 5 },
      { args: [3, [5]], expected: 0 },
      { args: [5, []], expected: 5 },
    ],
    hiddenTests: [
      { args: [8, [1, 1, 1, 1]], expected: 4 },
      { args: [2, [2]], expected: 0 },
    ],
    hint: 'Loop over losses and subtract each one, then use Math.max(0, ...) so the result never goes below 0.',
  },
  // ---------------------------------------------------------------- barracks
  {
    id: 'barracks-1',
    kind: 'barracks',
    title: 'Strongest Soldier',
    difficulty: 'Hard',
    story: 'The barracks master picks a champion to lead the next charge.',
    description: 'soldiers is a list of objects like { name: "Asha", strength: 8 }. Write strongestSoldier(soldiers) to return the name of the soldier with the highest strength. When two soldiers tie, return the first one. When the list is empty, return null.',
    examples: [
      { input: 'strongestSoldier([{name: "Asha", strength: 5}, {name: "Bram", strength: 9}])', output: '"Bram"', explanation: 'Bram has strength 9, the highest.' },
      { input: 'strongestSoldier([{name: "Solo", strength: 3}])', output: '"Solo"', explanation: 'Only one soldier, so Solo is the strongest.' },
      { input: 'strongestSoldier([])', output: 'null', explanation: 'No soldiers, no champion.' },
    ],
    constraints: ['soldiers is a list of objects with a name string and a strength integer from 0 to 100', 'soldiers has at most 20 entries'],
    functionName: 'strongestSoldier',
    starterCode: 'function strongestSoldier(soldiers) {\n  // Return the name of the soldier with the highest strength, or null when the list is empty.\n  return null;\n}',
    visibleTests: [
      { args: [[{ name: 'Asha', strength: 5 }, { name: 'Bram', strength: 9 }]], expected: 'Bram' },
      { args: [[{ name: 'Solo', strength: 3 }]], expected: 'Solo' },
      { args: [[]], expected: null },
    ],
    hiddenTests: [
      { args: [[{ name: 'Xara', strength: 2 }, { name: 'Yusuf', strength: 2 }]], expected: 'Xara' },
      { args: [[{ name: 'Zed', strength: 0 }]], expected: 'Zed' },
    ],
    hint: 'Track the best soldier seen so far. Only replace it when a soldier has a strictly greater strength, so ties keep the first one.',
  },
  {
    id: 'barracks-2',
    kind: 'barracks',
    title: 'Total Strength',
    difficulty: 'Hard',
    story: 'The war council wants one number: the combined strength of the garrison.',
    description: 'soldiers is a list of objects like { name: "Asha", strength: 8 }. Write totalStrength(soldiers) to return the sum of every soldier’s strength. An empty list totals 0.',
    examples: [
      { input: 'totalStrength([{name: "Asha", strength: 4}, {name: "Bram", strength: 6}])', output: '10', explanation: '4 + 6 = 10.' },
      { input: 'totalStrength([])', output: '0', explanation: 'No soldiers, no strength.' },
      { input: 'totalStrength([{name: "Asha", strength: 0}])', output: '0', explanation: 'One soldier with no strength yet.' },
    ],
    constraints: ['soldiers is a list of objects with a name string and a strength integer from 0 to 100', 'soldiers has at most 20 entries'],
    functionName: 'totalStrength',
    starterCode: 'function totalStrength(soldiers) {\n  // Add up the strength of every soldier.\n  return 0;\n}',
    visibleTests: [
      { args: [[{ name: 'Asha', strength: 4 }, { name: 'Bram', strength: 6 }]], expected: 10 },
      { args: [[]], expected: 0 },
      { args: [[{ name: 'Asha', strength: 0 }]], expected: 0 },
    ],
    hiddenTests: [
      { args: [[{ name: 'Asha', strength: 7 }]], expected: 7 },
      { args: [[{ name: 'A', strength: 1 }, { name: 'B', strength: 2 }, { name: 'C', strength: 3 }]], expected: 6 },
    ],
    hint: 'Use reduce to add up soldier.strength, starting from 0.',
  },
  {
    id: 'barracks-3',
    kind: 'barracks',
    title: 'Ready for Battle',
    difficulty: 'Hard',
    story: 'Only soldiers strong enough may join the front line. Pick the squad.',
    description: 'soldiers is a list of objects like { name: "Asha", strength: 8 } and minStrength is the lowest strength allowed. Write readyForBattle(soldiers, minStrength) to return a list with the names of the soldiers whose strength is at least minStrength, in their original order.',
    examples: [
      { input: 'readyForBattle([{name: "Asha", strength: 8}, {name: "Bram", strength: 3}, {name: "Cleo", strength: 6}], 5)', output: '["Asha", "Cleo"]', explanation: 'Asha and Cleo are at least 5; Bram is not.' },
      { input: 'readyForBattle([{name: "Asha", strength: 8}], 10)', output: '[]', explanation: 'Nobody reaches 10.' },
      { input: 'readyForBattle([{name: "Dara", strength: 5}], 5)', output: '["Dara"]', explanation: 'Exactly 5 is strong enough.' },
    ],
    constraints: ['soldiers is a list of objects with a name string and a strength integer from 0 to 100', 'minStrength is an integer from 0 to 100'],
    functionName: 'readyForBattle',
    starterCode: 'function readyForBattle(soldiers, minStrength) {\n  // Keep the soldiers with strength at least minStrength, and return their names.\n  return [];\n}',
    visibleTests: [
      { args: [[{ name: 'Asha', strength: 8 }, { name: 'Bram', strength: 3 }, { name: 'Cleo', strength: 6 }], 5], expected: ['Asha', 'Cleo'] },
      { args: [[{ name: 'Asha', strength: 8 }], 10], expected: [] },
      { args: [[{ name: 'Dara', strength: 5 }], 5], expected: ['Dara'] },
    ],
    hiddenTests: [
      { args: [[{ name: 'Elif', strength: 1 }], 1], expected: ['Elif'] },
      { args: [[], 0], expected: [] },
    ],
    hint: 'Filter the soldiers by strength >= minStrength, then map the survivors to their names.',
  },
];

export const CHALLENGES_BY_KIND = {};
for (const challenge of CHALLENGES) {
  if (!CHALLENGES_BY_KIND[challenge.kind]) CHALLENGES_BY_KIND[challenge.kind] = [];
  CHALLENGES_BY_KIND[challenge.kind].push(challenge);
}

const lastPickedByKind = {};

// Pick a random variant for a kind, avoiding an immediate repeat of the
// last variant picked for that kind (when more than one variant exists).
export function pickChallenge(kind) {
  const pool = CHALLENGES_BY_KIND[kind];
  if (!pool || pool.length === 0) return null;
  let options = pool;
  if (pool.length > 1 && lastPickedByKind[kind]) {
    options = pool.filter((c) => c.id !== lastPickedByKind[kind]);
  }
  const picked = options[Math.floor(Math.random() * options.length)];
  lastPickedByKind[kind] = picked.id;
  return picked;
}

export function getChallenge(id) {
  return CHALLENGES.find((c) => c.id === id) || null;
}
