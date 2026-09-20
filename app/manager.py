from __future__ import annotations

import random
import string
from dataclasses import dataclass, field
from uuid import uuid4

from fastapi import WebSocket

from app.game import Game
from app.models import Card, Player, Rank, Suit

@dataclass
class Room:
    code: str
    host_id: str

    players: list[Player] = field(default_factory=list)

    game: Game | None = None

    connections: dict[str, WebSocket] = field(
        default_factory=dict
    )


class RoomManager:
    def __init__(self):
        self.rooms: dict[str, Room] = {}

    def create_room(
        self,
        player_name: str,
    ) -> tuple[Room, Player]:
        code = self._generate_room_code()

        player = Player(
            id=str(uuid4()),
            name=player_name,
        )

        room = Room(
            code=code,
            host_id=player.id,
            players=[player],
        )

        self.rooms[code] = room

        return room, player

    def join_room(
        self,
        code: str,
        player_name: str,
    ) -> Player:
        room = self.get_room(code)

        if room.game is not None:
            raise ValueError(
                "Game has already started"
            )

        if len(room.players) >= 7:
            raise ValueError(
                "Room is full"
            )

        player = Player(
            id=str(uuid4()),
            name=player_name,
        )

        room.players.append(player)

        return player

    @staticmethod
    def deserialize_card(data: dict) -> Card:
        try:
            return Card(
                suit=Suit(data["suit"]),
                rank=Rank[data["rank"]],
            )
        except (KeyError, ValueError):
            raise ValueError("Invalid card")

    def start_game(
        self,
        code: str,
        host_id: str,
        target_score: int | None,
        max_rounds: int | None,
    ) -> Game:
        room = self.get_room(code)

        if room.host_id != host_id:
            raise ValueError(
                "Only the host can start the game"
            )

        if len(room.players) < 2:
            raise ValueError(
                "At least 2 players are required"
            )

        if room.game is not None:
            raise ValueError(
                "Game already started"
            )

        room.game = Game(
            players=room.players,
            target_score=target_score,
            max_rounds=max_rounds,
        )

        room.game.start_round()

        return room.game

    def get_room(
        self,
        code: str,
    ) -> Room:
        code = code.upper()

        if code not in self.rooms:
            raise ValueError(
                "Room not found"
            )

        return self.rooms[code]

    def get_player(
        self,
        room: Room,
        player_id: str,
    ) -> Player:
        for player in room.players:
            if player.id == player_id:
                return player

        raise ValueError(
            "Player not found"
        )

    async def connect(
        self,
        code: str,
        player_id: str,
        websocket: WebSocket,
    ) -> None:
        room = self.get_room(code)

        self.get_player(
            room,
            player_id,
        )

        await websocket.accept()

        room.connections[player_id] = websocket

    def disconnect(
        self,
        code: str,
        player_id: str,
        websocket: WebSocket,
    ) -> None:
        try:
            room = self.get_room(code)
        except ValueError:
            return

        current_socket = (
            room.connections.get(
                player_id
            )
        )

        if current_socket is websocket:
            room.connections.pop(
                player_id,
                None,
            )

    async def broadcast(
        self,
        code: str,
    ) -> None:
        room = self.get_room(code)

        disconnected = []

        for player_id, websocket in (
            room.connections.items()
        ):
            try:
                state = self.serialize_room(
                    room,
                    viewer_id=player_id,
                )

                await websocket.send_json(
                    state
                )

            except Exception:
                disconnected.append(
                    player_id
                )

        for player_id in disconnected:
            room.connections.pop(
                player_id,
                None,
            )

    def serialize_room(
        self,
        room: Room,
        viewer_id: str,
    ) -> dict:
        result = {
            "type": "state",
            "room_code": room.code,
            "host_id": room.host_id,
            "viewer_id": viewer_id,
            "players": [
                {
                    "id": player.id,
                    "name": player.name,
                    "score": player.score,
                    "card_count": len(
                        player.hand
                    ),
                }
                for player in room.players
            ],
            "game_started": (
                room.game is not None
            ),
        }

        if room.game is None:
            return result

        game = room.game

        viewer = self.get_player(
            room,
            viewer_id,
        )

        result["game"] = {
            "round_number": (
                game.round_number
            ),
            "phase": (
                game.phase.value
            ),
            "current_player_id": (
                game.current_player.id
            ),
            "deck_size": len(
                game.deck
            ),
            "discard": [
                self._serialize_card(card)
                for card in game.discard
            ],
            "hand": [
                self._serialize_card(card)
                for card in viewer.hand
            ],
            "melds": [
                {
                    "id": meld.id,
                    "type": (
                        meld.type.value
                    ),
                    "cards": [
                        {
                            **self._serialize_card(
                                played.card
                            ),
                            "owner_id": (
                                played.owner_id
                            ),
                        }
                        for played
                        in meld.cards
                    ],
                }
                for meld in game.melds
            ],
            "round_winner_id": (
                game.round_winner_id
            ),
            "last_round_scores":
                game.last_round_scores,
            "match_over": (
                game.match_over
            ),
        }

        return result

    @staticmethod
    def _serialize_card(card) -> dict:
        return {
            "rank": card.rank.name,
            "suit": card.suit.value,
        }

    def _generate_room_code(
        self,
    ) -> str:
        while True:
            code = "".join(
                random.choices(
                    string.digits,
                    k=4,
                )
            )

            if code not in self.rooms:
                return code