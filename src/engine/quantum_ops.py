import math
import random

# Assuming BoardState and BasisState are importable from the previous step
from engine.board_state import BoardState, BasisState, parse_square

def _move_piece_in_tuple(basis: BasisState, src_idx: int, tgt_idx: int) -> BasisState:
    """Helper to generate a new basis state tuple after moving a piece."""
    new_basis = list(basis)
    piece = new_basis[src_idx]
    new_basis[src_idx] = None
    new_basis[tgt_idx] = piece
    return tuple(new_basis)

def split_move(state: BoardState, src: str, t1: str, t2: str) -> BoardState:
    """
    Executes a quantum split move using a simulated sqrt-iSWAP gate.
    The piece at 'src' splits to exist in 't1' and 't2' simultaneously, 
    doubling the relevant basis states.
    """
    new_state = BoardState()

    src_idx = parse_square(src)
    t1_idx = parse_square(t1)
    t2_idx = parse_square(t2)
    
    # sqrt-iSWAP constants
    amp_t1_factor = 1 / math.sqrt(2) + 0j
    amp_t2_factor = 0 + 1j / math.sqrt(2) # Applies an imaginary phase
    
    for basis, amp in state.amplitudes.items():
        if basis[src_idx] is not None:
            # Branch 1: Piece moves to t1
            basis_t1 = _move_piece_in_tuple(basis, src_idx, t1_idx)
            new_state.amplitudes[basis_t1] = new_state.amplitudes.get(basis_t1, 0j) + amp * amp_t1_factor
            
            # Branch 2: Piece moves to t2
            basis_t2 = _move_piece_in_tuple(basis, src_idx, t2_idx)
            new_state.amplitudes[basis_t2] = new_state.amplitudes.get(basis_t2, 0j) + amp * amp_t2_factor
        else:
            # If the piece isn't in this universe, the basis state remains unchanged
            new_state.amplitudes[basis] = new_state.amplitudes.get(basis, 0j) + amp
            
    return new_state

def merge_move(state: BoardState, src1: str, src2: str, target: str) -> BoardState:
    """
    Combines two halves of a superposed piece back into a single square.
    Basis states will interfere, resulting in a reduced superposition.
    """
    new_state = BoardState()

    src1_idx = parse_square(src1)
    src2_idx = parse_square(src2)
    tgt_idx = parse_square(target)
    
    for basis, amp in state.amplitudes.items():
        # If the basis state has the piece at either source, move it to the target
        if basis[src1_idx] is not None:
            new_basis = _move_piece_in_tuple(basis, src1_idx, tgt_idx)
            # Amplitudes add together here, creating interference
            new_state.amplitudes[new_basis] = new_state.amplitudes.get(new_basis, 0j) + amp
        elif basis[src2_idx] is not None:
            new_basis = _move_piece_in_tuple(basis, src2_idx, tgt_idx)
            new_state.amplitudes[new_basis] = new_state.amplitudes.get(new_basis, 0j) + amp
        else:
            new_state.amplitudes[basis] = new_state.amplitudes.get(basis, 0j) + amp
            
    # Clean up near-zero amplitudes caused by destructive interference
    new_state.prune_states() 
    new_state.normalize()
    return new_state


def observe_square(state: BoardState, target_square: str) -> tuple[bool, BoardState]:
    """
    Observe whether any piece occupies target_square.
    Returns (is_present, collapsed_state).
    Unlike measure(), the caller learns the outcome.
    """
    tgt_idx = parse_square(target_square)
    prob_occupied = sum(
        abs(amp) ** 2
        for basis, amp in state.amplitudes.items()
        if basis[tgt_idx] is not None
    )
    is_present = random.choices([True, False], weights=[prob_occupied, 1.0 - prob_occupied], k=1)[0]

    new_state = BoardState()
    for basis, amp in state.amplitudes.items():
        if (basis[tgt_idx] is not None) == is_present:
            new_state.amplitudes[basis] = amp

    new_state.normalize()
    return is_present, new_state
