from typing import Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel


class MoveHistoryEntry(BaseModel):
    move_number: int
    side: Literal["white", "black"]
    mode: Literal["classical", "split", "merge"]
    piece: str
    squares: List[str]
    outcome: Optional[Literal["success", "capture_failed"]] = None


class GameSnapshot(BaseModel):
    board: Dict[str, Optional[str]]
    probabilities: Dict[str, float]
    side_to_move: Literal["white", "black"]
    fullmove_number: int
    game_status: Literal["ongoing", "white_wins", "black_wins"]
    legal_moves: List[Tuple[str, str]]
    last_move_outcome: Optional[Literal["success", "capture_failed"]] = None
    move_history: List[MoveHistoryEntry] = []


class ClassicalMoveRequest(BaseModel):
    src: str
    target: str


class SplitMoveRequest(BaseModel):
    src: str
    target_a: str
    target_b: str


class MergeMoveRequest(BaseModel):
    src_a: str
    src_b: str
    target: str
