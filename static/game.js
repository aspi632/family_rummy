let roomCode = null;
let playerId = null;
let socket = null;
let currentState = null;

const SESSION_KEY = "family_rummy_session";

function saveSession() {
    localStorage.setItem(
        SESSION_KEY,
        JSON.stringify({
            roomCode: roomCode,
            playerId: playerId,
        })
    );
}

function clearSession() {
    localStorage.removeItem(SESSION_KEY);
}

function loadSession() {
    const raw =
        localStorage.getItem(SESSION_KEY);

    if (!raw) {
        return false;
    }

    try {
        const session = JSON.parse(raw);

        if (
            !session.roomCode ||
            !session.playerId
        ) {
            clearSession();
            return false;
        }

        roomCode = session.roomCode;
        playerId = session.playerId;

        return true;

    } catch {
        clearSession();
        return false;
    }
}

let selectedHandIndices = new Set();
let selectedDiscardIndices = new Set();
let selectedMeldId = null;


const welcome = document.getElementById(
    "welcome"
);

const roomSection = document.getElementById(
    "room"
);

const hostControls = document.getElementById(
    "host-controls"
);

const gameSection = document.getElementById(
    "game"
);


document.getElementById(
    "create-room"
).onclick = async () => {

    const name = getPlayerName();

    if (!name) {
        return;
    }

    const response = await fetch(
        "/api/rooms",
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json",
            },

            body: JSON.stringify({
                name,
            }),
        }
    );

    const data = await response.json();

    enterRoom(
        data.room_code,
        data.player_id,
    );
};


document.getElementById(
    "join-room"
).onclick = async () => {

    const name = getPlayerName();

    if (!name) {
        return;
    }

    const code = (
        document.getElementById(
            "room-code"
        ).value
    )
        .trim()
        .toUpperCase();

    if (!code) {
        return;
    }

    const response = await fetch(
        `/api/rooms/${code}/join`,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json",
            },

            body: JSON.stringify({
                name,
            }),
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail);
        return;
    }

    enterRoom(
        data.room_code,
        data.player_id,
    );
};


document.getElementById(
    "start-game"
).onclick = async () => {

    const targetScoreValue =
        document.getElementById(
            "target-score"
        ).value;

    const maxRoundsValue =
        document.getElementById(
            "max-rounds"
        ).value;

    const targetScore =
        targetScoreValue
            ? Number(targetScoreValue)
            : null;

    const maxRounds =
        maxRoundsValue
            ? Number(maxRoundsValue)
            : null;

    const response = await fetch(
        `/api/rooms/${roomCode}/start`,
        {
            method: "POST",

            headers: {
                "Content-Type":
                    "application/json",
            },

            body: JSON.stringify({
                player_id: playerId,
                target_score: targetScore,
                max_rounds: maxRounds,
            }),
        }
    );

    const data = await response.json();

    if (!response.ok) {
        alert(data.detail);
    }
};


function getPlayerName() {

    const name = (
        document.getElementById(
            "player-name"
        ).value
    ).trim();

    if (!name) {
        alert("Введите имя");
        return null;
    }

    return name;
}


function enterRoom(
    code,
    id,
) {
    roomCode = code;
    playerId = id;

    saveSession();

    welcome.classList.add(
        "hidden"
    );

    roomSection.classList.remove(
        "hidden"
    );

    document.getElementById(
        "room-code-display"
    ).textContent = roomCode;

    connectWebSocket();
}


function connectWebSocket() {

    const protocol =
        location.protocol === "https:"
            ? "wss"
            : "ws";

    socket = new WebSocket(
        `${protocol}://${location.host}` +
        `/ws/${roomCode}/${playerId}`
    );

    socket.onmessage = event => {
        const message = JSON.parse(
            event.data
        );

        if (message.type === "error") {
            showError(message.message);
            return;
        }

        if (message.type === "state") {
            currentState = message;

            clearSelection();

            renderState(message);
        }
    };

    socket.onclose = event => {

        console.log(
            "WebSocket disconnected",
            event.code
        );

        if (event.code !== 4001) {
            return;
        }

        clearSession();

        roomCode = null;
        playerId = null;
        currentState = null;

        roomSection.classList.add(
            "hidden"
        );

        gameSection.classList.add(
            "hidden"
        );

        welcome.classList.remove(
            "hidden"
        );

        alert(
            "Старая игровая сессия больше " +
            "не существует. Создайте новую " +
            "комнату или присоединитесь к другой."
        );
    };
}


function sendAction(action) {

    if (
        !socket ||
        socket.readyState !== WebSocket.OPEN
    ) {
        showError(
            "Нет соединения с сервером"
        );
        return;
    }

    showError("");

    socket.send(
        JSON.stringify(action)
    );
}


function showError(message) {
    document.getElementById(
        "game-error"
    ).textContent = message;
}


function renderState(state) {

    renderPlayers(state);

    if (
        state.host_id === playerId &&
        !state.game_started
    ) {
        hostControls.classList.remove(
            "hidden"
        );
    } else {
        hostControls.classList.add(
            "hidden"
        );
    }

    if (!state.game_started) {
        return;
    }

    gameSection.classList.remove(
        "hidden"
    );

    renderGame(state);
}


function renderPlayers(state) {

    const container =
        document.getElementById(
            "players"
        );

    container.innerHTML = "";

    for (const player of state.players) {

        const div =
            document.createElement(
                "div"
            );

        div.className = "player";

        let text =
            `${player.name}` +
            ` — ${player.score} очков`;

        if (state.game_started) {
            text +=
                ` — карт: ${player.card_count}`;
        }

        if (player.id === state.host_id) {
            text += " (host)";
        }

        container.appendChild(div);

        div.textContent = text;
    }
}


function renderGame(state) {

    const game = state.game;

    document.getElementById(
        "round-number"
    ).textContent =
        game.round_number;

    document.getElementById(
        "phase"
    ).textContent =
        game.phase;

    const currentPlayer =
        state.players.find(
            player =>
                player.id ===
                game.current_player_id
        );

    document.getElementById(
        "current-player"
    ).textContent =
        currentPlayer
            ? currentPlayer.name
            : "?";

    document.getElementById(
        "deck"
    ).textContent =
        `${game.deck_size} карт`;

    renderDiscard(
        game.discard
    );

    renderHand(
        game.hand
    );

    renderPlayerTables(
        state
    );

    renderRoundOver(
        state
    );
}

function renderRoundOver(state) {

    const overlay =
        document.getElementById(
            "round-over-overlay"
        );

    const newGameButton =
        document.getElementById(
            "new-game"
        );

    if (state.game.match_over) {
        newGameButton.classList.remove(
            "hidden"
        );
    } else {
        newGameButton.classList.add(
            "hidden"
        );
    }


    if (
        state.game.phase !==
        "round_over"
    ) {
        overlay.classList.add(
            "hidden"
        );

        return;
    }


    overlay.classList.remove(
        "hidden"
    );


    const winner =
        state.players.find(
            player =>
                player.id ===
                state.game.round_winner_id
        );


    document.getElementById(
        "round-winner"
    ).textContent =
        winner
            ? `🏆 ${winner.name} выиграл(а) раунд!`
            : "Раунд окончен";


    const scoresContainer =
        document.getElementById(
            "round-scores"
        );

    scoresContainer.innerHTML = "";


    const sortedPlayers = [
        ...state.players
    ].sort(
        (a, b) => b.score - a.score
    );

    for (
        const player
        of state.players
    ) {
        const delta =
            state.game.last_round_scores[
                player.id
            ] ?? 0;

        const row =
            document.createElement("div");

        row.className = "score-row";

        const sign =
            delta > 0 ? "+" : "";

        const place =
            sortedPlayers.findIndex(
                p => p.id === player.id
            ) + 1;

        const placeIcon =
            place === 1
                ? "🥇"
                : place === 2
                    ? "🥈"
                    : place === 3
                        ? "🥉"
                        : "";

        row.innerHTML = `
            <span>
                ${player.name}
            </span>

            <span>
                ${sign}${delta}
            </span>

            <strong>
                ${placeIcon}
                ${player.score}
            </strong>
        `;

        scoresContainer.appendChild(row);
    }


    const nextButton =
        document.getElementById(
            "next-round"
        );


    if (
        state.host_id === playerId &&
        !state.game.match_over
    ) {
        nextButton.classList.remove(
            "hidden"
        );
    } else {
        nextButton.classList.add(
            "hidden"
        );
    }
}


function renderHand(cards) {

    const container =
        document.getElementById(
            "hand"
        );

    container.innerHTML = "";

    cards.forEach(
        (card, index) => {

            const div =
                createCardElement(card);

            if (
                selectedHandIndices.has(
                    index
                )
            ) {
                div.classList.add(
                    "selected"
                );
            }

            div.onclick = () => {

                if (
                    selectedHandIndices.has(
                        index
                    )
                ) {
                    selectedHandIndices.delete(
                        index
                    );
                } else {
                    selectedHandIndices.add(
                        index
                    );
                }

                renderGame(
                    currentState
                );
            };

            container.appendChild(div);
        }
    );
}


function renderDiscard(cards) {

    const container =
        document.getElementById(
            "discard"
        );

    container.innerHTML = "";

    cards.forEach(
        (card, index) => {

            const div =
                createCardElement(card);

            if (
                selectedDiscardIndices.has(index)
            ) {
                div.classList.add(
                    "selected"
                );
            }

            div.onclick = () => {

                if (
                    selectedDiscardIndices.has(index)
                ) {
                    selectedDiscardIndices.delete(index);
                } else {
                    selectedDiscardIndices.add(index);
                }

                renderGame(
                    currentState
                );
            };

            container.appendChild(div);
        }
    );
}


function createCardElement(card) {

    const div =
        document.createElement(
            "div"
        );

    div.className =
        "playing-card";


    const image =
        document.createElement(
            "img"
        );

    image.src =
        "/cards/" +
        cardImageName(card);

    image.alt =
        cardRankText(card) +
        cardSuitText(card);

    image.draggable = false;


    div.appendChild(
        image
    );

    return div;
}


function cardRankText(card) {

    const ranks = {
        TWO: "2",
        THREE: "3",
        FOUR: "4",
        FIVE: "5",
        SIX: "6",
        SEVEN: "7",
        EIGHT: "8",
        NINE: "9",
        TEN: "10",
        JACK: "J",
        QUEEN: "Q",
        KING: "K",
        ACE: "A",
    };

    return ranks[card.rank];
}


function cardSuitText(card) {

    const suits = {
        clubs: "♣",
        diamonds: "♦",
        hearts: "♥",
        spades: "♠",
    };

    return suits[card.suit];
}

function renderPlayerTables(state) {

    const container =
        document.getElementById(
            "player-tables"
        );

    container.innerHTML = "";


    for (const player of state.players) {

        const playerArea =
            document.createElement(
                "div"
            );

        playerArea.className =
            "player-table";


        if (
            player.id ===
            state.game.current_player_id
        ) {
            playerArea.classList.add(
                "current-player-table"
            );
        }


        if (
            player.id === playerId
        ) {
            playerArea.classList.add(
                "my-player-table"
            );
        }


        // Header конкретного игрока.
        const header =
            document.createElement(
                "div"
            );

        header.className =
            "player-table-header";


        let playerLabel =
            `${player.name} — ${player.score}`;

        if (player.id === playerId) {
            playerLabel += " (вы)";
        }


        header.textContent =
            playerLabel;

        playerArea.appendChild(
            header
        );

        const handIndicator =
            document.createElement(
                "div"
            );

        handIndicator.className =
            "player-hand-indicator";


        for (
            let i = 0;
            i < player.card_count;
            i++
        ) {

            const back =
                document.createElement(
                    "div"
                );

            back.className =
                "mini-card-back";

            handIndicator.appendChild(
                back
            );
        }


        const cardCount =
            document.createElement(
                "span"
            );

        cardCount.className =
            "player-card-count";

        cardCount.textContent =
            `${player.card_count}`;

        handIndicator.appendChild(
            cardCount
        );


        playerArea.appendChild(
            handIndicator
        );


        const meldContainer =
            document.createElement(
                "div"
            );

        meldContainer.className =
            "player-melds";


        // Проходим по всем логическим meld.
        for (
            const meld
            of state.game.melds
        ) {

            // Но рисуем перед этим игроком
            // только карты, которые выложил ОН.
            const ownedCards =
                meld.cards.filter(
                    card =>
                        card.owner_id ===
                        player.id
                );


            if (
                ownedCards.length === 0
            ) {
                continue;
            }


            const fragment =
                document.createElement(
                    "div"
                );

            fragment.className =
                "meld-fragment";


            // Важно:
            // хотя перед игроком может лежать
            // только часть комбинации,
            // fragment всё ещё знает настоящий meld.id.
            if (
                selectedMeldId ===
                meld.id
            ) {
                fragment.classList.add(
                    "selected"
                );
            }


            fragment.onclick = () => {

                selectedMeldId =
                    selectedMeldId === meld.id
                        ? null
                        : meld.id;

                renderGame(
                    currentState
                );
            };


            // Первый владелец карты в meld -
            // тот, кто создал комбинацию.
            const creatorId =
                meld.cards[0].owner_id;


            const label =
                document.createElement(
                    "div"
                );

            label.className =
                "meld-label";


            if (
                player.id === creatorId
            ) {
                label.textContent =
                    meld.type === "run"
                        ? "Ряд"
                        : "Набор";
            } else {
                label.textContent =
                    "Добавлено";
            }


            fragment.appendChild(
                label
            );


            const cardsDiv =
                document.createElement(
                    "div"
                );

            cardsDiv.className =
                "cards meld-cards";


            for (
                const card
                of ownedCards
            ) {

                const cardDiv =
                    createCardElement(
                        card
                    );

                cardsDiv.appendChild(
                    cardDiv
                );
            }


            fragment.appendChild(
                cardsDiv
            );

            meldContainer.appendChild(
                fragment
            );
        }


        if (
            meldContainer.children.length === 0
        ) {

            const empty =
                document.createElement(
                    "div"
                );

            empty.className =
                "empty-table";

            empty.textContent =
                "Нет выложенных карт";

            meldContainer.appendChild(
                empty
            );
        }


        playerArea.appendChild(
            meldContainer
        );

        container.appendChild(
            playerArea
        );
    }
}


function getSelectedHandCards() {

    const hand =
        currentState.game.hand;

    return Array.from(
        selectedHandIndices
    )
        .sort((a, b) => a - b)
        .map(index => hand[index]);
}


document.getElementById(
    "draw-discard"
).onclick = () => {

    if (
        selectedDiscardIndices.size === 0
    ) {
        showError(
            "Выберите карты из сброса для комбинации"
        );
        return;
    }

    const handCards =
        getSelectedHandCards();

    const discardIndices =
        Array.from(
            selectedDiscardIndices
        ).sort((a, b) => a - b);

    const discardCards =
        discardIndices.map(
            index =>
                currentState.game.discard[index]
        );

    sendAction({
        action: "draw_discard",

        // Самая ранняя выбранная карта.
        // Отсюда забираем весь остаток сброса.
        discard_index:
            discardIndices[0],

        // Какие карты руки непосредственно
        // участвуют в новой комбинации.
        hand_cards:
            handCards,

        // Какие карты из забираемой части сброса
        // непосредственно участвуют в комбинации.
        discard_cards:
            discardCards,
    });
};


// 14. Выложить новую комбинацию
document.getElementById(
    "create-meld"
).onclick = () => {

    const cards =
        getSelectedHandCards();

    if (cards.length < 3) {
        showError(
            "Для комбинации нужно минимум 3 карты"
        );
        return;
    }

    sendAction({
        action: "create_meld",
        cards: cards,
    });
};


// 15. Добавить одну карту к существующей комбинации
document.getElementById(
    "extend-meld"
).onclick = () => {

    const cards =
        getSelectedHandCards();

    // Для продолжения комбинации пока разрешаем
    // только одну карту за одно действие.
    if (cards.length !== 1) {
        showError(
            "Выберите ровно одну карту"
        );
        return;
    }

    // Перед этим игрок должен кликнуть
    // на одну из комбинаций на столе.
    if (!selectedMeldId) {
        showError(
            "Выберите комбинацию на столе"
        );
        return;
    }

    sendAction({
        action: "extend_meld",
        meld_id: selectedMeldId,
        card: cards[0],
    });
};


// 16. Сбросить карту и закончить ход
document.getElementById(
    "discard-card"
).onclick = () => {

    const cards =
        getSelectedHandCards();

    if (cards.length !== 1) {
        showError(
            "Для сброса выберите одну карту"
        );
        return;
    }

    sendAction({
        action: "discard",
        card: cards[0],
    });
};

function clearSelection() {
    selectedHandIndices.clear();
    selectedDiscardIndices.clear();
    selectedMeldId = null;
}

document.getElementById(
    "deck-card"
).onclick = () => {

    sendAction({
        action: "draw_deck",
    });
};

document.getElementById(
    "next-round"
).onclick = () => {

    sendAction({
        action: "next_round",
    });
};

document.getElementById(
    "new-game"
).onclick = () => {
    leaveRoom();
};

function cardImageName(card) {

    const ranks = {
        TWO: "2",
        THREE: "3",
        FOUR: "4",
        FIVE: "5",
        SIX: "6",
        SEVEN: "7",
        EIGHT: "8",
        NINE: "9",
        TEN: "10",
        JACK: "J",
        QUEEN: "Q",
        KING: "K",
        ACE: "A",
    };


    const suits = {
        clubs: "C",     // Крести
        diamonds: "D",  // Бубны
        hearts: "H",    // Черви
        spades: "S",    // Пики
    };


    return (
        suits[card.suit] +
        ranks[card.rank] +
        ".svg"
    );
}


function leaveRoom() {

    clearSession();

    if (socket) {
        socket.close();
        socket = null;
    }

    roomCode = null;
    playerId = null;
    currentState = null;

    clearSelection();

    gameSection.classList.add(
        "hidden"
    );

    roomSection.classList.add(
        "hidden"
    );

    welcome.classList.remove(
        "hidden"
    );
}


if (loadSession()) {

    welcome.classList.add(
        "hidden"
    );

    roomSection.classList.remove(
        "hidden"
    );

    document.getElementById(
        "room-code-display"
    ).textContent = roomCode;

    connectWebSocket();
}