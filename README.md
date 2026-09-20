# Family Rummy --- Project Context & Design

> **Purpose of this document**
>
> This is the canonical context document for the Family Rummy project.
> It is intended to be readable by the project owner and detailed enough
> for any AI (or another developer) to reconstruct the project's
> architecture, rules, design decisions, current state, and next steps
> without relying on previous conversations.
>
> **Keep this file updated when:** game rules change, the state model
> changes, a new client/server action is added, the round/match
> lifecycle changes, or an important UI/architecture decision is made.

------------------------------------------------------------------------

## 1. Project overview

**Family Rummy** is a lightweight browser-based multiplayer
implementation of a family Rummy / Rummy 500-like card game.

The primary use case is playing with family from phones and laptops.
Players open the same web application, join a room, and play
synchronously.

### Main goals

-   Simple enough to maintain without a large web framework.
-   Python backend with game rules kept independent from networking/UI.
-   Server-authoritative multiplayer state.
-   Usable from both desktop and mobile browsers.
-   No accounts or database required for the initial version.
-   Pleasant card-table UI rather than a debug-style web interface.
-   Easy local-network play now and straightforward internet deployment
    later.

### Current technology

-   **Backend:** Python + FastAPI
-   **Realtime communication:** WebSocket
-   **Frontend:** plain HTML + CSS + JavaScript
-   **State:** in-memory Python objects
-   **Tests:** pytest
-   **Card artwork:** SVG files served from `static/`
-   **Deployment target:** later, e.g. Render or Railway
-   **Source control:** GitHub

Deliberately **not** used for the MVP:

-   React
-   TypeScript
-   Node/npm frontend toolchain
-   PostgreSQL
-   Redis
-   Docker
-   user accounts/authentication

------------------------------------------------------------------------

## 2. High-level architecture

The server is authoritative.

``` text
┌──────────────────┐
│ Browser: Alice   │
│ HTML/CSS/JS      │
└────────┬─────────┘
         │ WebSocket actions/state
         │
┌────────▼─────────────────────────────┐
│ FastAPI                              │
│                                     │
│ main.py       HTTP + WS interface    │
│ manager.py    rooms/connections      │
│ game.py       game state/lifecycle   │
│ rules.py      pure rule validation   │
│ models.py     domain data classes    │
└────────┬─────────────────────────────┘
         │
         │ tailored state broadcast
         │
┌────────▼─────────┐
│ Browser: Bob     │
│ HTML/CSS/JS      │
└──────────────────┘
```

The browser does **not** decide whether an action is legal. It sends an
intent such as `draw_deck`, `create_meld`, or `discard`. The backend
validates and mutates the game. It then broadcasts the resulting
authoritative state.

Each connected player receives a **personalized view**:

-   their own hand is visible;
-   other players' hands are represented only by `card_count`;
-   discard, melds, scores, turn and round state are shared.

This prevents one client from receiving hidden cards belonging to
another player.

------------------------------------------------------------------------

## 3. Project structure

``` text
family-rummy/
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── models.py
│   ├── rules.py
│   ├── game.py
│   └── manager.py
│
├── static/
│   ├── index.html
│   ├── game.js
│   ├── style.css
│   ├── icon.svg
│   └── cards/
│       ├── C2.svg
│       ├── ...
│       ├── CA.svg
│       ├── ...
│       └── SQ.svg
│
├── tests/
│   ├── test_rules.py
│   └── test_game.py
│
├── requirements.txt
└── README.md
```

This document should live at the project root as `README.md`.

------------------------------------------------------------------------

## 4. Responsibilities by file

### `app/models.py`

Domain model only. Contains the fundamental game entities and enums.

Important concepts:

-   `Suit`
-   `Rank`
-   `MeldType`
-   `TurnPhase`
-   `Card`
-   `Player`
-   `PlayedCard`
-   `Meld`

A particularly important design choice is:

``` python
@dataclass(frozen=True)
class PlayedCard:
    card: Card
    owner_id: str
```

`owner_id` means **the player who put that particular card on the
table**.

This is essential because scoring and visual placement are based on who
played each card, even when several players contribute to the same
logical meld.

### `app/rules.py`

Pure rule-validation functions.

Examples:

-   `is_valid_set`
-   `is_valid_run`
-   `get_meld_type`
-   `is_valid_meld`
-   `can_extend_meld`

These functions should ideally remain independent of rooms, WebSockets,
UI, and turn state.

### `app/game.py`

The core state machine.

`Game` owns:

-   players
-   deck
-   discard
-   melds
-   current player
-   turn phase
-   round number
-   previous round winner
-   round winner
-   accumulated scores
-   last-round scores
-   match-over state

It performs legal state transitions such as:

-   start round
-   draw from deck
-   draw from discard
-   create meld
-   extend meld
-   discard
-   finish round
-   start next round

The core game logic must remain usable without FastAPI.

### `app/manager.py`

Multiplayer/session layer.

Responsibilities:

-   create rooms;
-   join rooms;
-   identify host;
-   start games;
-   map players to WebSocket connections;
-   serialize game state;
-   send each player a tailored view;
-   broadcast updates.

It should **not** implement card-game rules.

### `app/main.py`

Transport/API layer.

Responsibilities:

-   FastAPI app;
-   HTTP endpoints for create/join/start;
-   WebSocket endpoint;
-   parsing client actions;
-   translating JSON card representations back into `Card`;
-   invoking `Game`;
-   returning errors to the acting client;
-   broadcasting successful changes.

### `static/game.js`

Browser controller/view logic.

Responsibilities:

-   create/join room requests;
-   WebSocket connection;
-   send actions;
-   render lobby/game state;
-   card selection;
-   meld selection;
-   screen switching;
-   round-over overlay;
-   rendering SVG cards.

It should not be trusted to enforce game rules.

### `static/style.css`

Visual design and responsive layout.

The intended style is a green physical card table with:

-   individual player areas;
-   central deck/discard area;
-   realistic SVG playing cards;
-   responsive mobile layout;
-   visual current-player indication;
-   card-back indicators for opponents' hand sizes.

------------------------------------------------------------------------

# 5. Game rules

This section is the canonical rules summary.

## 5.1 Deck and players

-   Standard 52-card deck.
-   No Jokers.
-   Supported player count: **2--7**.
-   At the start of every round, the deck is shuffled.
-   Each player receives **5 cards**.
-   After dealing, the top remaining card is immediately placed face-up
    as the first discard card.

## 5.2 Turn order

Players act clockwise.

For the first round, the first player is selected randomly.

For every later round, the winner of the previous round goes first.

## 5.3 Turn phases

A normal turn has two phases:

``` text
DRAW → PLAY
```

### DRAW

The player must either:

1.  draw one card from the deck; or
2.  take cards from the discard.

### PLAY

After drawing, the player may:

-   create one or more new melds;
-   add cards to existing melds;
-   eventually discard one card to finish the turn.

If the player gets rid of every card by laying/adding cards, the round
ends immediately and no final discard is required.

A player can also finish the round by discarding their final card.

------------------------------------------------------------------------

# 6. Meld rules

A new meld contains **at least 3 cards**.

There are two types.

## 6.1 Set

3 or 4 cards of the same rank with different suits.

Example:

``` text
8♣ 8♦ 8♥
```

or:

``` text
K♣ K♦ K♥ K♠
```

## 6.2 Run

3 or more consecutive ranks of the same suit.

Examples:

``` text
3♣ 4♣ 5♣
10♥ J♥ Q♥ K♥
Q♠ K♠ A♠
```

Rank ordering is:

``` text
2 3 4 5 6 7 8 9 10 J Q K A
```

Ace is high only for runs.

Therefore:

``` text
Q K A   valid
2 3 4   valid
A 2 3   invalid
K A 2   invalid
```

There is no Ace wrap-around.

------------------------------------------------------------------------

# 7. Drawing from the discard

The discard is a **visible horizontal sequence**, ordered
chronologically.

If it contains:

``` text
2♠ | 4♣ | 6♣ | K♥
```

and a player selects `4♣`, they take:

``` text
4♣ 6♣ K♥
```

Everything from the selected card to the right is picked up.

## Mandatory immediate meld rule

The **selected/earliest discard card must immediately participate in a
NEW valid meld**.

It is not legal to take cards from the discard merely to:

-   keep them in hand; or
-   extend an already existing meld.

However, the immediate new meld may use:

-   cards already in the player's hand;
-   the selected discard card;
-   any later discard cards automatically picked up with it.

Example:

``` text
Hand:
5♣

Discard:
4♣ 6♣
```

The player may select `4♣`, automatically take `4♣` and `6♣`, and
immediately create:

``` text
4♣ 5♣ 6♣
```

Any trailing cards picked up from the discard that are **not** used in
the mandatory new meld are added to the player's hand.

------------------------------------------------------------------------

# 8. Extending existing melds

Any player may add a card to an existing logical meld if the resulting
full meld remains valid.

Example:

``` text
Alice creates:
3♣ 4♣ 5♣

Bob later adds:
6♣
```

The logical meld is:

``` text
3♣ 4♣ 5♣ 6♣
```

but ownership remains:

``` text
3♣ → Alice
4♣ → Alice
5♣ → Alice
6♣ → Bob
```

This ownership is important for both scoring and UI.

------------------------------------------------------------------------

# 9. Logical meld vs visual placement

This is one of the project's most important design decisions.

A meld is a **single logical object** used for validation.

But cards are visually placed **in front of the player who played
them**.

Therefore, if Alice creates:

``` text
3♣ 4♣ 5♣
```

and Bob adds:

``` text
6♣
```

the UI shows approximately:

``` text
Alice:
3♣ 4♣ 5♣

Bob:
6♣
```

Both visual fragments still refer to the same `meld.id`.

Clicking either fragment can therefore select the same logical meld for
extension.

The backend representation is effectively:

``` text
Meld ABC
├── 3♣ owner=Alice
├── 4♣ owner=Alice
├── 5♣ owner=Alice
└── 6♣ owner=Bob
```

`renderPlayerTables()` groups the cards visually by `owner_id`.

------------------------------------------------------------------------

# 10. Meld ordering

Logical run melds are stored in canonical sorted rank order.

For example, if the player clicks:

``` text
4♣ 3♣ 5♣
```

the resulting meld is stored/displayed as:

``` text
3♣ 4♣ 5♣
```

The same normalization is performed after extending a run.

Example:

``` text
existing: 6♣ 7♣ 8♣
added:    5♣
```

must become:

``` text
5♣ 6♣ 7♣ 8♣
```

rather than:

``` text
6♣ 7♣ 8♣ 5♣
```

The helper lives in `Game`, conceptually:

``` python
_sort_meld_cards(cards, meld_type)
```

Runs are sorted by `card.rank`.

Sets do not require meaningful rank ordering because all ranks are
identical.

------------------------------------------------------------------------

# 11. Scoring

At the end of a round:

-   every card a player placed on the table contributes **positive**
    points to that player;
-   every card remaining in the player's hand contributes **negative**
    points.

Card values:

  Cards           Points
  ------------- --------
  2--9                 5
  10, J, Q, K         10
  Ace                 15

Example:

Alice laid:

``` text
5♣ 6♣ 7♣
```

and has `K♥` left in hand.

Score:

``` text
+5 +5 +5 -10 = +5
```

If Bob added a card to Alice's meld, the added card scores for **Bob**,
because its `PlayedCard.owner_id` is Bob.

Round scores are added to accumulated match scores.

The game should preserve `last_round_scores` so the UI can show the
result of the completed round.

------------------------------------------------------------------------

# 12. Round and match lifecycle

Conceptual lifecycle:

``` text
Lobby
  │
  ▼
Start match
  │
  ▼
Round 1
  │
  ▼
ROUND_OVER
  │
  ├── show winner
  ├── show round score deltas
  ├── show accumulated scores
  │
  ▼
Next round
  │
  ▼
Round N
  │
  ▼
Match over
```

A match ends when either configured condition is reached:

-   a player reaches `target_score`; or
-   `max_rounds` is reached.

At round end:

-   `round_winner_id` is stored;
-   `previous_winner_id` is set;
-   round scores are calculated;
-   `last_round_scores` is stored;
-   accumulated scores are updated;
-   `phase = ROUND_OVER`;
-   match-ending conditions are checked.

The previous round winner starts the next round.

Only the room host currently controls starting the game and starting the
next round.

### Current tie behavior

Tie handling at match end is not yet fully specified. The current/simple
implementation may select `max(players, key=score)`, which is not
sufficient for a true tie. This remains a design item.

### Empty deck

Behavior when the draw deck becomes empty is not yet fully specified.
The MVP currently treats it as an error (`Deck is empty`). A proper
reshuffle/end-round rule can be added later.

------------------------------------------------------------------------

# 13. Core data model

Conceptually:

``` python
class Suit:
    CLUBS
    DIAMONDS
    HEARTS
    SPADES


class Rank:
    TWO = 2
    ...
    KING = 13
    ACE = 14


class MeldType:
    RUN
    SET


class TurnPhase:
    DRAW
    PLAY
    ROUND_OVER
```

Cards are immutable:

``` python
@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: Rank
```

Players:

``` python
@dataclass
class Player:
    id: str
    name: str
    hand: list[Card]
    score: int
```

Played cards preserve ownership:

``` python
@dataclass(frozen=True)
class PlayedCard:
    card: Card
    owner_id: str
```

Melds:

``` python
@dataclass
class Meld:
    id: str
    type: MeldType
    cards: list[PlayedCard]
```

------------------------------------------------------------------------

# 14. Important `Game` operations

The core public interface is approximately:

``` python
Game.start_round()

Game.draw_from_deck(player_id)

Game.draw_from_discard(
    player_id,
    discard_index,
    hand_cards_for_meld,
    discard_cards_for_meld,
)

Game.create_meld(
    player_id,
    cards,
)

Game.extend_meld(
    player_id,
    meld_id,
    card,
)

Game.discard_card(
    player_id,
    card,
)

Game.calculate_round_scores()

Game.start_next_round()

Game.get_match_winner()
```

`draw_from_discard()` deserves special attention because its parameters
distinguish:

``` text
hand_cards_for_meld
discard_cards_for_meld
```

The selected discard index determines the entire suffix that is picked
up. `discard_cards_for_meld` identifies which picked-up discard cards
participate in the mandatory immediate new meld.

------------------------------------------------------------------------

# 15. Client/server actions

The browser sends JSON messages through the WebSocket.

## Draw from deck

``` json
{
  "action": "draw_deck"
}
```

## Draw from discard

Conceptually:

``` json
{
  "action": "draw_discard",
  "discard_index": 1,
  "hand_cards": [...],
  "discard_cards": [...]
}
```

`discard_index` is the earliest selected discard card and determines the
suffix that is taken.

## Create meld

``` json
{
  "action": "create_meld",
  "cards": [...]
}
```

## Extend meld

``` json
{
  "action": "extend_meld",
  "meld_id": "...",
  "card": {...}
}
```

## Discard

``` json
{
  "action": "discard",
  "card": {...}
}
```

## Next round

``` json
{
  "action": "next_round"
}
```

The backend catches `GameError` / validation errors and sends an error
message only to the acting client.

After a successful mutation, `RoomManager.broadcast()` sends fresh state
to all connected players.

------------------------------------------------------------------------

# 16. Room and lobby model

A `Room` contains approximately:

``` text
code
host_id
players
game
connections
```

Room codes are short uppercase codes.

Flow:

``` text
Welcome
   │
   ├── Create room
   │      └── creator becomes host
   │
   └── Join room
          └── enter room code
                │
                ▼
              Lobby
                │
                ├── list players
                └── host-only game settings/start
                        │
                        ▼
                       Game
```

Host-only controls are determined by:

``` javascript
state.viewer_id === state.host_id
```

Screen visibility and permissions are separate concerns:

-   `showScreen("room")` decides which page section is visible;
-   host checks decide which controls inside the room are visible.

------------------------------------------------------------------------

# 17. Screen switching

The frontend should show exactly one major screen at a time:

``` text
welcome
room
game
```

`showScreen(screenId)` hides the other two.

The `.hidden` utility should reliably override component display styles:

``` css
.hidden {
    display: none !important;
}
```

This avoids the previous behavior where the game/lobby appeared *below*
the full-height welcome screen and required scrolling.

The state-driven behavior is:

``` text
Initial page              → welcome
Create/join successful    → room
game_started == false     → room
game_started == true      → game
```

------------------------------------------------------------------------

# 18. Current table UI

The game screen consists of:

1.  game header;
2.  green card table;
3.  individual player areas;
4.  central deck + discard;
5.  current user's hand and actions;
6.  round-result overlay.

### Player area

Each player area shows:

-   name;
-   accumulated score;
-   whether they are the current player;
-   visual card-back indicators for number of cards in hand;
-   table cards played by that player.

The current player should have a clear visual highlight.

### Opponent hand size

Other players' cards are never revealed.

Instead, `card_count` is rendered as overlapping mini card backs,
optionally with a numeric count.

### Deck

The deck is directly clickable.

Clicking its card-back icon sends:

``` json
{"action": "draw_deck"}
```

There is no need for a separate "Draw from deck" button.

### Discard

The discard is chronological from left to right.

Cards have fixed dimensions and **must not shrink** as the discard
grows.

The discard may wrap onto a second/third row rather than compressing
cards or forcing horizontal scrolling.

Conceptually CSS uses:

``` css
.discard-cards {
    display: flex;
    flex-wrap: wrap;
}

.playing-card {
    flex-shrink: 0;
}
```

### Selection

Clicking a card selects it.

Clicking the same card again deselects it.

There is intentionally **no "Clear selection" button** because it is
redundant.

Selections are also cleared after authoritative state updates where
appropriate.

------------------------------------------------------------------------

# 19. Card rendering

Cards use SVG artwork rather than dynamically constructing pips and face
cards with CSS.

Reasoning:

-   proper J/Q/K artwork;
-   correct pip placement for 2--10;
-   consistent appearance;
-   easier responsive scaling;
-   simpler JavaScript;
-   no CSS special cases for each rank.

Expected naming convention:

``` text
AC.svg
2C.svg
...
KC.svg

AD.svg
...
KD.svg

AH.svg
...
KH.svg

AS.svg
...
KS.svg

BACK.svg
```

Suit abbreviations:

``` text
C = clubs
D = diamonds
H = hearts
S = spades
```

`createCardElement()` creates an `<img>` pointing to the appropriate
SVG.

### Important SVG/CSS design detail

The SVG itself owns:

-   card border;
-   rounded corners;
-   artwork.

The `.playing-card` wrapper should primarily own:

-   dimensions;
-   positioning;
-   hover/selection transform;
-   click behavior.

Do **not** add a second rounded white card background around the SVG.
This previously caused visibly mismatched double corner radii.

For hover shadows, `filter: drop-shadow(...)` on the SVG image is
preferable to a rectangular `box-shadow` on the wrapper because it
follows the rendered card shape.

------------------------------------------------------------------------

# 20. Responsive layout

The app is expected to work on:

-   desktop/laptop browsers;
-   phones on the same Wi-Fi;
-   later, phones over the public internet.

The main desktop content should use most of the available browser width
while retaining modest white margins.

A target maximum width around **1400 px** is appropriate rather than a
narrow \~900 px content column.

Conceptually:

``` css
.page-container {
    width: min(1400px, calc(100% - 48px));
    margin: 0 auto;
}
```

On mobile, margins become smaller.

The central table layout should place the deck somewhat left of center
because the chronological discard grows to the right.

------------------------------------------------------------------------

# 21. Welcome screen

The welcome screen is intended to feel like the entry screen of a small
polished card game rather than a raw form.

It contains:

-   Family Rummy title;
-   suit decoration;
-   player name;
-   Create Room;
-   separator;
-   room code;
-   Join Room;
-   short supporting text.

After create/join, the welcome screen disappears and the lobby replaces
it rather than appearing below it.

------------------------------------------------------------------------

# 22. Round-over UI

When a round finishes, the UI should show an animated overlay
containing:

-   "Round over";
-   round winner;
-   score delta for each player;
-   accumulated score for each player;
-   "Next round" for the host, if the match is not over.

The backend therefore needs to expose:

``` text
round_winner_id
last_round_scores
match_over
```

If `match_over == true`, the next-round action must not be available;
the UI should eventually show a dedicated match result instead.

------------------------------------------------------------------------

# 23. HTTP/WebSocket flow

Room creation and joining happen through HTTP.

Realtime game state/actions use WebSockets.

Conceptually:

``` text
POST /api/rooms
POST /api/rooms/{code}/join
POST /api/rooms/{code}/start

WS /ws/{code}/{player_id}
```

After connecting, the server broadcasts the current state.

The browser chooses `ws://` or `wss://` based on `location.protocol`,
and uses `location.host`, so the same frontend works on localhost, LAN
IP addresses, and HTTPS deployment without hard-coded hosts.

------------------------------------------------------------------------

# 24. Running locally

Create environment:

``` bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi "uvicorn[standard]" pytest
```

Run for the current computer only:

``` bash
uvicorn app.main:app --reload
```

Run so other devices on the same Wi-Fi can connect:

``` bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Find the host computer's LAN IP and open from another device:

``` text
http://<LAN-IP>:8000
```

For example:

``` text
http://192.168.1.42:8000
```

Possible LAN blockers:

-   OS firewall;
-   guest Wi-Fi/client isolation;
-   devices actually being on different networks.

------------------------------------------------------------------------

# 25. Testing strategy

The core game is deliberately independent of FastAPI so it can be tested
directly.

Tests live in:

``` text
tests/test_rules.py
tests/test_game.py
```

Run:

``` bash
pytest -v
```

Important scenarios to cover:

-   valid/invalid sets;
-   valid/invalid runs;
-   Ace behavior;
-   turn enforcement;
-   phase enforcement;
-   draw from deck;
-   discard and turn rotation;
-   creating a meld;
-   run normalization (`4,3,5 → 3,4,5`);
-   extending a run at either end;
-   discard suffix pickup;
-   selected discard card must be used immediately;
-   later picked-up discard cards may participate in the new meld;
-   unused trailing discard cards enter the hand;
-   cannot use discard pickup merely to extend an existing meld;
-   round ending when hand becomes empty;
-   scoring by `PlayedCard.owner_id`;
-   accumulated scores;
-   previous winner starts next round;
-   match-ending conditions.

A useful discard test example:

``` text
Hand:
5♣, A♥

Discard:
2♠, 4♣, 6♣, K♥

Select:
4♣

Immediate meld:
4♣ 5♣ 6♣

Result:
- 4♣ and 6♣ go to meld
- 5♣ removed from hand
- K♥ enters hand
- discard becomes [2♠]
```

------------------------------------------------------------------------

# 26. Important invariants

These are assumptions future code should preserve.

### Server authority

The frontend may help UX, but backend validation is mandatory.

### Hidden information

Never serialize another player's actual hand to a client.

### Played-card ownership

Do not infer scoring ownership from the meld creator. Every table card
has its own `owner_id`.

### Logical meld identity

Visual fragments in different player areas may represent the same
`meld.id`.

### Selected discard participation

The earliest selected discard card must participate in the mandatory new
meld.

### Canonical run ordering

Valid run cards should be normalized by rank after creation/extension.

### One active screen

Welcome, lobby, and game should not be vertically stacked as active
sections.

### Fixed card proportions

Card SVGs should scale without being squeezed as table/discard size
changes.

------------------------------------------------------------------------

# 27. Known limitations / unresolved decisions

These are not necessarily bugs; they are unfinished product decisions.

1.  **Empty deck behavior**
    -   Current MVP: error.
    -   Need to decide whether to reshuffle discard, end round, etc.
2.  **Match ties**
    -   Need explicit tie semantics.
3.  **Disconnect/reconnect**
    -   In-memory rooms and current player IDs need a robust reconnect
        story before internet use is polished.
4.  **Server restart**
    -   All rooms disappear because there is no persistence.
5.  **Room cleanup**
    -   Old abandoned rooms should eventually be removed.
6.  **Match-over UI**
    -   Round-over UI exists/planned; final match result deserves a
        dedicated presentation.
7.  **Security**
    -   Player IDs are currently lightweight identity tokens rather than
        real authentication. Appropriate for family MVP, not adversarial
        public use.
8.  **Multiple server workers**
    -   In-memory room state means the application should run as a
        single process/worker unless shared state is introduced.

------------------------------------------------------------------------

# 28. Near-term roadmap

Suggested order:

### UI polish

-   finish SVG card deck integration;
-   polish desktop width and mobile table layout;
-   ensure discard wrapping is predictable;
-   polish player zones/current-player indicator;
-   finish favicon and welcome/lobby presentation.

### Round/match UX

-   verify `last_round_scores`;
-   verify next-round host action;
-   dedicated match-over overlay;
-   explicit tie handling.

### Gameplay robustness

-   empty-deck rule;
-   more tests around discard pickup;
-   normalize all run displays;
-   better error messages/disabled impossible actions.

### Multiplayer robustness

-   reconnect support;
-   host disconnect behavior;
-   room cleanup;
-   optional persistence if needed.

### Deployment

-   deploy FastAPI publicly;
-   HTTPS/WSS;
-   production process configuration;
-   later custom domain if desired.

------------------------------------------------------------------------

# 29. Guidance for future development

When changing the project:

1.  **Rule change?** Update this document first or together with
    `rules.py` / `game.py`.
2.  **New game action?** Document its client JSON shape and server
    transition.
3.  **New state field?** Document whether it is public or
    viewer-specific.
4.  **UI-only change?** Avoid duplicating legality logic that belongs on
    the server.
5.  **Meld behavior change?** Check ownership/scoring and
    visual-fragment implications.
6.  **Round lifecycle change?** Check both `Game` and WebSocket
    broadcast/rendering.
7.  **Card UI change?** Preserve SVG aspect ratio and fixed card
    dimensions.
8.  **Before refactoring networking**, remember that `Game` should
    remain independently testable.

------------------------------------------------------------------------

# 30. Quick context for an AI/developer joining the project

If you only have a few minutes, remember these points:

-   This is a **FastAPI + vanilla JS multiplayer family Rummy game**.
-   The **server is authoritative** and state is currently **in
    memory**.
-   A turn is `DRAW → PLAY`.
-   New melds are runs or sets of 3+ cards.
-   Taking from discard means taking the selected card **and everything
    after it**.
-   The selected discard card must immediately be used in a **new
    meld**.
-   Later picked-up discard cards may also be used in that same new
    meld.
-   A logical meld may contain cards played by several people.
-   Every table card stores its own `owner_id`.
-   Cards are visually displayed in front of the player who played them,
    even if they belong to somebody else's logical meld.
-   Scoring is positive for cards a player laid and negative for cards
    left in hand.
-   Runs are normalized into sorted rank order.
-   Other players' hands are never sent to the client; only hand counts
    are.
-   Cards are rendered from SVG artwork.
-   Major frontend screens are mutually exclusive: `welcome`, `room`,
    `game`.
-   Host controls match start and next-round progression.
-   Core rules belong in `rules.py` / `game.py`, not JavaScript.
-   Run `pytest -v` after gameplay changes.

------------------------------------------------------------------------

## Document maintenance

**Canonical filename:** `README.md`

When future work materially changes the project, update the relevant
section rather than appending a chronological chat log. This file should
describe the **current truth of the project**, not every historical
implementation attempt.
