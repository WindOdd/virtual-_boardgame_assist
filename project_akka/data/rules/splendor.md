# Splendor Rules Database

## 1. Global Configuration
### 1.1 Components & Setup
* **Gem Tokens**:
    * **Standard**: Green (Emerald), Blue (Sapphire), Red (Ruby), White (Diamond), Black (Onyx).
    * **Wild**: Gold (Joker).
* **Setup Matrix**:
    * **2 Players**: 4 of each standard gem, 5 Gold.
    * **3 Players**: 5 of each standard gem, 5 Gold.
    * **4 Players**: 7 of each standard gem, 5 Gold.
* **Development Cards**: Level 1, 2, and 3 decks. 4 cards of each level are always face-up (12 total).
* **Nobles**: Quantity = Player Count + 1.

## 2. Turn Structure
Players take turns clockwise. On their turn, a player MUST choose exactly **ONE** of the following actions (A, B, C, or D):

### Action A: Take 3 Distinct Gems
* **Logic**: Take 1 gem of 3 **different** colors.
* **Constraint**: Cannot take Gold.
* **Exception**: If fewer than 3 colors are available in supply, take what is available (distinct colors only).

### Action B: Take 2 Identical Gems
* **Logic**: Take 2 gems of the **same** color.
* **Constraint**: The supply stack of that color must have **4 or more** gems BEFORE taking. If 3 or fewer, this action is illegal.
* **Restriction**: Cannot take Gold.

### Action C: Reserve a Card
* **Logic**: Take 1 face-up card OR draw 1 card from the deck into hand (Hidden).
* **Bonus**: Take 1 Gold token (if available).
* **Constraint**: Maximum **3 reserved cards** in hand. If a player holds 3, they cannot perform this action.
* **Note**: Taking Gold is mandatory if available, but the action is valid even if Gold is empty (player just gets the card).

### Action D: Buy a Card
* **Source**: Buy a face-up card from the table OR a reserved card from hand.
* **Cost Calculation**:
    * `Cost to Pay` = `Card Price` - `Player's Discount (Bonuses from owned cards)`
    * If `Cost to Pay` < 0, it is treated as 0.
* **Payment**:
    * Pay with standard tokens matching the required colors.
    * **Gold** can be used as any color to cover deficits.
    * Paid tokens return to the supply.
* **Effect**: Card adds to player's tableau (permanent discount) and Prestige Points.
* **Replenish**: If a face-up card is bought, immediately replace it from the deck.

## 3. Automatic Phases (Not Actions)
### Noble Visit (End of Turn)
* **Timing**: After the player's action and card replenishment.
* **Check**: Does the player's **Card Discounts** (Bonuses) meet a Noble's requirement? (Tokens do not count).
* **Execution**:
    * If yes, player **must** take the Noble.
    * Limit: Max 1 Noble per turn. If eligible for multiple, player chooses one.
    * Nobles give Prestige Points and are never lost.

### Discard Phase (End of Turn)
* **Check**: Does player have > 10 tokens total (Standard + Gold)?
* **Execution**: Player must return tokens to supply until total count is **10**. Player chooses which colors to return.

## 4. End Game Condition
1.  **Trigger**: A player reaches **15 or more Prestige Points** at the end of their turn.
2.  **Round Completion**: Continue play until all players have played the same number of turns (finish the current round).
3.  **Winning Criteria**:
    * **Priority 1**: Highest Prestige Points.
    * **Priority 2 (Tie-breaker)**: Fewest purchased Development Cards.

## 5. Constraints & Edge Cases
1.  **No Trading**: Players cannot trade tokens or cards.
2.  **Gold Usage**: Gold cannot be used to attract Nobles. Gold is only for buying cards.
3.  **Action Exclusivity**: You cannot Reserve and Buy in the same turn.
4.  **Discount Logic**: Discounts reduce cost. They do not generate tokens (no "change" given).
5.  **Taking 2 Logic**: You cannot take 2 gems if the stack has exactly 3 gems. It must be 4+.