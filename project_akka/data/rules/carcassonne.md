# Carcassonne Rules Database (Base Game)

## 1. Global Configuration
### 1.1 Components & Setup
* **Tiles**:
    * Total: 72 Land tiles.
    * **Start Tile**: The tile with a dark back (depicts city, road, and field). Placed face-up in the center first.
* **Meeples (Followers)**:
    * Supply: 8 per player.
    * **Score Track**: 1 meeple is placed on the scoreboard to track points.
    * **Available**: 7 meeples remain in the player's personal supply for gameplay.

## 2. Turn Structure
Turns proceed clockwise. A player's turn consists of **3 distinct phases** that must be performed in sequential order:

### Phase A: Place a Tile (Mandatory)
* **Action**: Draw 1 tile from the stack.
* **Logic**: Place it adjacent to at least one existing tile on the board.
* **Constraint (Matching)**: All touching edges must match the terrain of adjacent tiles (Road to Road, City to City, Field to Field).
* **Exception**: If a tile simply cannot be placed legally anywhere, discard it and draw a new one (Repeat until a playable tile is drawn or stack is empty).

### Phase B: Place a Meeple (Optional)
* **Action**: The player *may* place **1 meeple** from their supply onto the **tile just placed**.
* **Constraint 1 (Location)**: Must choose a specific feature on that tile:
    * **Road** (becomes a Thief).
    * **City** (becomes a Knight).
    * **Monastery** (becomes a Monk).
    * **Field** (becomes a Farmer) -> *Farmer is laid flat and stays until game end.*
* **Constraint 2 (Occupancy)**: A meeple **CANNOT** be placed on a feature that is already occupied by any meeple (including the player's own).
    * *Check*: Trace the entire connected road, city, or field. If *any* meeple is found, placement is illegal.

### Phase C: Score & Return (Conditional)
* **Check**: Did the placed tile complete any Road, City, or Monastery? (Fields are never scored mid-game).
* **Execution**:
    1.  Calculate points for the completed feature.
    2.  Update score on the track.
    3.  **Return Meeple**: The meeple on the completed feature is returned to the player's supply immediately.
    * *Note*: Farmers (on fields) are **never** returned during the game.

## 3. Scoring Mechanics

### 3.1 Roads
* **Completion**: Both ends terminate at a village, city, monastery, or loop onto itself.
* **Scoring**: **1 point** per tile in the road.
* **End Game**: **1 point** per tile.

### 3.2 Cities
* **Completion**: The city walls are completely closed with no gaps.
* **Scoring (During Game)**:
    * **2 points** per tile.
    * **+2 points** per Pennant (Shield icon) inside the city.
    * *Exception*: A city consisting of only 2 tiles is worth **4 points** (Standard Rules).
* **Scoring (End Game)**:
    * **1 point** per tile. (Half value).
    * **+1 point** per Pennant. (Half value).

### 3.3 Monasteries
* **Completion**: The monastery tile is surrounded by 8 other tiles (3x3 grid filled).
* **Scoring**: **9 points** (1 for monastery + 8 neighbors).
* **End Game**: **1 point** for the monastery + **1 point** for each existing neighbor.

### 3.4 Fields / Farmers (Game End Only)
* **Completion**: Never completed during the game. Scored **ONLY** at Game End.
* **Definition**: A field is a continuous green area bounded by roads, cities, or the edge of the map.
* **Scoring Logic**:
    1.  Identify a specific connected Field.
    2.  Identify all **Completed Cities** that touch this Field.
    3.  Score **3 points** for each unique Completed City.
* **Constraint**: Uncompleted cities provide 0 points to farmers.
* **Multiple Fields**: A single city can border multiple separate fields. If a player has farmers in different fields touching the same city, they are scored separately (logic varies by edition, but this is the standard "International" rule).

## 4. Conflict & Majority Rules (Sharing Features)
* **Scenario**: Two separate features (each with a meeple) are connected by a later tile placement.
* **Result**: The feature is now shared.
* **Scoring Logic**:
    * Count total meeples for each player on the completed feature.
    * **Majority**: The player with the **most** meeples takes **Full Points**.
    * **Tie**: All tied players take **Full Points**.
    * **Loser**: Players with fewer meeples get **0 points**.

## 5. End Game Condition
* **Trigger**: The last tile is placed (Phase A, B, and C are resolved).
* **Final Scoring Steps**:
    1.  Score all **incomplete** Roads, Cities, and Monasteries (using "End Game" values).
    2.  Score all **Fields** (Farmers).
* **Winner**: Highest total score.

## 6. FAQ & Edge Cases (Anti-Hallucination)
1.  **Q: Can I place a meeple if I don't have any in my supply?**
    * **A: NO.** You cannot move a meeple already on the board. You must use one from your supply.
2.  **Q: Can I place a meeple on a feature if it connects to an occupied one?**
    * **A: NO.** If the road/city/field you are extending already has a meeple anywhere on it, you cannot place a new one. You must place on an isolated feature and connect them later.
3.  **Q: Do empty fields score points?**
    * **A: NO.** Only fields with Farmers score points.
4.  **Q: Does a farmer score for an incomplete city?**
    * **A: NO.** Only completed cities count for farmers.
5.  **Q: Can I return a Farmer to my hand?**
    * **A: NO.** Farmers remain on the board until the end of the game.