from pathlib import Path

from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.manager import RoomManager
from app.game import GameError


app = FastAPI()

manager = RoomManager()


class CreateRoomRequest(BaseModel):
    name: str


class JoinRoomRequest(BaseModel):
    name: str


class StartGameRequest(BaseModel):
    player_id: str
    target_score: int = None
    max_rounds: int = None


@app.post("/api/rooms")
async def create_room(
    request: CreateRoomRequest,
):
    room, player = (
        manager.create_room(
            request.name
        )
    )

    return {
        "room_code": room.code,
        "player_id": player.id,
    }


@app.post(
    "/api/rooms/{code}/join"
)
async def join_room(
    code: str,
    request: JoinRoomRequest,
):
    try:
        player = manager.join_room(
            code.upper(),
            request.name,
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    await manager.broadcast(
        code.upper()
    )

    return {
        "room_code": code.upper(),
        "player_id": player.id,
    }


@app.post(
    "/api/rooms/{code}/start"
)
async def start_game(
    code: str,
    request: StartGameRequest,
):
    try:
        manager.start_game(
            code=code.upper(),
            host_id=request.player_id,
            target_score=(
                request.target_score
            ),
            max_rounds=(
                request.max_rounds
            ),
        )

    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e),
        )

    await manager.broadcast(
        code.upper()
    )

    return {
        "ok": True,
    }


@app.websocket(
    "/ws/{code}/{player_id}"
)
async def websocket_endpoint(
    websocket: WebSocket,
    code: str,
    player_id: str,
):
    code = code.upper()

    try:
        await manager.connect(
            code,
            player_id,
            websocket,
        )

        await manager.broadcast(code)

        while True:
            message = await websocket.receive_json()

            try:
                await handle_action(
                    code=code,
                    player_id=player_id,
                    message=message,
                )

            except (GameError, ValueError) as e:
                await websocket.send_json({
                    "type": "error",
                    "message": str(e),
                })

    except WebSocketDisconnect:
        manager.disconnect(
            code,
            player_id,
        )

    except ValueError:
        await websocket.close(
            code=1008
        )

static_dir = (
    Path(__file__).parent.parent
    / "static"
)

async def handle_action(
    code: str,
    player_id: str,
    message: dict,
) -> None:
    room = manager.get_room(code)

    if room.game is None:
        raise ValueError(
            "Game has not started"
        )

    game = room.game

    action = message.get("action")

    if action == "draw_deck":
        game.draw_from_deck(
            player_id
        )

    elif action == "draw_discard":
        discard_index = message.get(
            "discard_index"
        )

        hand_cards = [
            manager.deserialize_card(card)
            for card in message.get(
                "hand_cards", []
            )
        ]

        discard_cards = [
            manager.deserialize_card(card)
            for card in message.get(
                "discard_cards", []
            )
        ]

        game.draw_from_discard(
            player_id=player_id,
            discard_index=discard_index,
            hand_cards_for_meld=hand_cards,
            discard_cards_for_meld=discard_cards,
        )

    elif action == "create_meld":
        cards = [
            manager.deserialize_card(card)
            for card in message.get(
                "cards", []
            )
        ]

        game.create_meld(
            player_id,
            cards,
        )

    elif action == "extend_meld":
        meld_id = message.get(
            "meld_id"
        )

        card = manager.deserialize_card(
            message["card"]
        )

        game.extend_meld(
            player_id=player_id,
            meld_id=meld_id,
            card=card,
        )

    elif action == "discard":
        card = manager.deserialize_card(
            message["card"]
        )

        game.discard_card(
            player_id,
            card,
        )

    elif action == "next_round":
        if room.host_id != player_id:
            raise GameError(
                "Only host can start next round"
            )

        game.start_next_round()

    else:
        raise ValueError(
            f"Unknown action: {action}"
        )

    await manager.broadcast(code)

app.mount(
    "/",
    StaticFiles(
        directory=static_dir,
        html=True,
    ),
    name="static",
)