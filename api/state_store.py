from threading import Lock
from typing import Optional

from engine.board_state import square_name
from engine.game_state import QuantumGame
from engine.game_state import game_status as compute_game_status, legal_moves_for

from api.schemas import GameSnapshot, MoveHistoryEntry


class GameStateStore:
    def __init__(self):
        self._lock = Lock()
        self._game = QuantumGame.initial()
        self._move_history: list[MoveHistoryEntry] = []

    def get_game(self) -> QuantumGame:
        with self._lock:
            return self._game

    def get_history(self) -> list[MoveHistoryEntry]:
        with self._lock:
            return list(self._move_history)

    def get_snapshot_data(self) -> tuple[QuantumGame, list[MoveHistoryEntry]]:
        with self._lock:
            return self._game, list(self._move_history)

    def reset(self) -> QuantumGame:
        with self._lock:
            self._game = QuantumGame.initial()
            self._move_history = []
            return self._game

    def apply_classical_move(self, src: str, target: str) -> QuantumGame:
        with self._lock:
            game = self._game
            move_number = game.fullmove_number
            side = game.side_to_move
            piece = game.piece_at(src) or "?"
            game.apply_classical_move(src, target)
            self._move_history.append(MoveHistoryEntry(
                move_number=move_number,
                side=side,
                mode="classical",
                piece=piece,
                squares=[src, target],
                outcome=game.last_move_outcome,
            ))
            return game

    def apply_split_move(self, src: str, target_a: str, target_b: str) -> QuantumGame:
        with self._lock:
            game = self._game
            move_number = game.fullmove_number
            side = game.side_to_move
            piece = game.piece_at(src) or "?"
            game.apply_split_move(src, target_a, target_b)
            self._move_history.append(MoveHistoryEntry(
                move_number=move_number,
                side=side,
                mode="split",
                piece=piece,
                squares=[src, target_a, target_b],
                outcome=None,
            ))
            return game

    def apply_merge_move(self, src_a: str, src_b: str, target: str) -> QuantumGame:
        with self._lock:
            game = self._game
            move_number = game.fullmove_number
            side = game.side_to_move
            piece = game.piece_at(src_a) or "?"
            game.apply_merge_move(src_a, src_b, target)
            self._move_history.append(MoveHistoryEntry(
                move_number=move_number,
                side=side,
                mode="merge",
                piece=piece,
                squares=[src_a, src_b, target],
                outcome=None,
            ))
            return game


store = GameStateStore()


def snapshot_game(game: QuantumGame, history: Optional[list[MoveHistoryEntry]] = None) -> GameSnapshot:
    board = game.board_summary()
    probabilities = {
        square_name(index): game.board_state.probability(square_name(index))
        for index in range(64)
    }
    cr = game.castling_rights
    ep = game.en_passant_target
    return GameSnapshot(
        board=board,
        probabilities=probabilities,
        side_to_move=game.side_to_move,
        fullmove_number=game.fullmove_number,
        game_status=compute_game_status(game.board_state),
        legal_moves=legal_moves_for(
            game.board_state, game.side_to_move,
            castling_rights=cr, en_passant_target=ep,
        ),
        last_move_outcome=game.last_move_outcome,
        move_history=history or [],
    )
