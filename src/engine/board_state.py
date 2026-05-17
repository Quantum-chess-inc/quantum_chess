from dataclasses import dataclass, field
import math
from typing import Dict, Tuple, Optional

# A BasisState is a hashable representation of a single classical board configuration.
# We use a tuple of 64 strings (or None) corresponding to squares A1 through H8.
BasisState = Tuple[Optional[str], ...]

FILES = "abcdefgh"
RANKS = "12345678"


def parse_square(square_name: str) -> int:
    """Convert algebraic square notation like 'a1' into a zero-based index."""
    if len(square_name) != 2:
        raise ValueError(f"invalid square name: {square_name!r}")

    file_name, rank_name = square_name[0], square_name[1]
    if file_name not in FILES or rank_name not in RANKS:
        raise ValueError(f"invalid square name: {square_name!r}")

    return FILES.index(file_name) + 8 * (int(rank_name) - 1)


def square_name(square_index: int) -> str:
    """Convert a zero-based square index into algebraic notation like 'a1'."""
    if square_index < 0 or square_index >= 64:
        raise ValueError(f"invalid square index: {square_index!r}")

    file_name = FILES[square_index % 8]
    rank_name = RANKS[square_index // 8]
    return f"{file_name}{rank_name}"


def _initial_basis_state() -> BasisState:
    """Build the standard chess starting position as a basis-state tuple."""
    squares = [None] * 64

    white_back_rank = ("R", "N", "B", "Q", "K", "B", "N", "R")
    black_back_rank = tuple(piece.lower() for piece in white_back_rank)

    for file_idx, piece in enumerate(white_back_rank):
        squares[file_idx] = piece
        squares[8 + file_idx] = "P"
        squares[48 + file_idx] = "p"
        squares[56 + file_idx] = black_back_rank[file_idx]

    return tuple(squares)

@dataclass
class BoardState:
    """
    Represents the quantum state of the chess board as a superposition of classical states.
    """
    # Maps a classical board configuration (basis state) to its complex probability amplitude
    # This tracks only reachable basis states instead of a full 2^64 state vector
    amplitudes: Dict[BasisState, complex] = field(default_factory=dict)

    @classmethod
    def initial(cls) -> 'BoardState':
        """
        Creates the initial classical chess board state with a single basis state 
        having an amplitude of 1.0 + 0j.
        """
        initial_tuple = _initial_basis_state()
        
        # The game starts entirely classical: 100% probability in the starting position
        state = cls(amplitudes={initial_tuple: 1.0 + 0.0j})
        return state

    @staticmethod
    def _board_to_tuple(board: Dict[str, Optional[str]]) -> BasisState:
        """Helper to convert a square-to-piece mapping into a 64-element tuple."""
        squares = [None] * 64
        for square_name, piece in board.items():
            squares[parse_square(square_name)] = piece
        return tuple(squares)

    def amplitude(self, square_name: str) -> complex:
        """
        Returns the sum of amplitudes across all basis states where the given
        square is occupied. This is NOT the square root of the occupation
        probability; use probability() for that. Useful for testing interference
        effects where the raw amplitude sum is meaningful.
        """
        square_index = parse_square(square_name)
        total_amplitude = 0.0 + 0.0j
        
        for basis_state, amp in self.amplitudes.items():
            if basis_state[square_index] is not None:
                total_amplitude += amp
                
        return total_amplitude

    def occupied_piece(self, square_name: str) -> Optional[str]:
        """
        Returns the unique piece symbol found on this square across occupied branches.

        Raises ValueError if different piece symbols occupy the same square across
        the current superposition.
        """
        square_index = parse_square(square_name)
        piece = None

        for basis_state in self.amplitudes:
            current_piece = basis_state[square_index]
            if current_piece is None:
                continue
            if piece is None:
                piece = current_piece
                continue
            if piece != current_piece:
                raise ValueError(
                    f"inconsistent piece identity at {square_name}: {piece!r} vs {current_piece!r}"
                )

        return piece
        
    def probability(self, square_name: str) -> float:
        """Returns the total probability that a square is occupied."""
        square_index = parse_square(square_name)
        total_probability = 0.0

        for basis_state, amp in self.amplitudes.items():
            if basis_state[square_index] is not None:
                total_probability += abs(amp)**2

        return total_probability

    def prune_states(self, threshold: float = 0.001):
        """Prune basis states with probability < threshold to prevent state explosion.
        Branches containing a king are never pruned — losing a king branch prematurely
        would incorrectly end the game.
        """
        _KINGS = {"K", "k"}
        states_to_remove = [
            basis_state
            for basis_state, amp in self.amplitudes.items()
            if abs(amp) ** 2 < threshold
            and not any(p in _KINGS for p in basis_state if p is not None)
        ]
        for state in states_to_remove:
            del self.amplitudes[state]
        self.normalize()

    def normalize(self):
        """
        Ensures the sum of all probabilities (abs(amplitude)**2) across all 
        basis states equals exactly 1.0.
        """
        total_prob = sum(abs(amp)**2 for amp in self.amplitudes.values())
        if total_prob == 0:
            return
            
        # Scale amplitudes so their squared absolute values sum to 1
        scale_factor = math.sqrt(1.0 / total_prob)
        for basis_state in self.amplitudes:
            self.amplitudes[basis_state] *= scale_factor
