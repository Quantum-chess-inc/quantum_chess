from dataclasses import dataclass, field
from typing import Iterable, Optional

from engine.board_state import BoardState, BasisState, parse_square, square_name
from engine.quantum_ops import merge_move, observe_square, split_move


def _piece_color(piece: str) -> str:
    return "white" if piece.isupper() else "black"


def _same_square(src_idx: int, tgt_idx: int) -> bool:
    return src_idx == tgt_idx


def _delta(src_idx: int, tgt_idx: int) -> tuple[int, int]:
    src_file = src_idx % 8
    src_rank = src_idx // 8
    tgt_file = tgt_idx % 8
    tgt_rank = tgt_idx // 8
    return tgt_file - src_file, tgt_rank - src_rank


def _path_is_clear(basis: BasisState, src_idx: int, tgt_idx: int) -> bool:
    file_delta, rank_delta = _delta(src_idx, tgt_idx)
    step_file = 0 if file_delta == 0 else file_delta // abs(file_delta)
    step_rank = 0 if rank_delta == 0 else rank_delta // abs(rank_delta)

    src_file = src_idx % 8
    src_rank = src_idx // 8
    tgt_file = tgt_idx % 8
    tgt_rank = tgt_idx // 8

    current_file = src_file + step_file
    current_rank = src_rank + step_rank
    while (current_file, current_rank) != (tgt_file, tgt_rank):
        current_idx = current_file + 8 * current_rank
        if basis[current_idx] is not None:
            return False
        current_file += step_file
        current_rank += step_rank

    return True


def _castling_path_is_clear(basis: BasisState, src_idx: int, file_delta: int) -> bool:
    rook_src = (src_idx // 8) * 8 + (7 if file_delta > 0 else 0)
    return _path_is_clear(basis, src_idx, rook_src)


def _would_move_in_basis(basis: BasisState, src_idx: int, tgt_idx: int, piece: str) -> bool:
    """True when piece can physically move src→tgt in this basis:
    path to target is clear of any piece, AND the target is either empty,
    occupied by an enemy piece, or occupied by the same piece type (quantum merge).
    Does not check piece movement geometry — that is _is_legal_piece_move's job.
    """
    target_piece = basis[tgt_idx]
    if target_piece is not None and _piece_color(target_piece) == _piece_color(piece) and target_piece != piece:
        return False
    lower = piece.lower()
    if lower in ("b", "r", "q"):
        return _path_is_clear(basis, src_idx, tgt_idx)
    if lower == "k":
        file_delta = (tgt_idx % 8) - (src_idx % 8)
        if abs(file_delta) == 2:
            return _castling_path_is_clear(basis, src_idx, file_delta)
    return True  # knights, pawns, non-castling kings have no intermediate squares to block


def _is_legal_piece_move(
    piece: str,
    src_idx: int,
    tgt_idx: int,
    basis: BasisState,
    *,
    allow_empty_target_for_pawn_diagonal: bool = False,
    en_passant_idx: Optional[int] = None,
) -> bool:
    if _same_square(src_idx, tgt_idx):
        return False

    target_piece = basis[tgt_idx]
    if target_piece is not None and _piece_color(target_piece) == _piece_color(piece):
        # Allow moving to own copy's square (merge) — block only if different piece type
        if target_piece != piece:
            return False
        # Same piece type at target: allowed (merges the two copies)

    file_delta, rank_delta = _delta(src_idx, tgt_idx)
    abs_file = abs(file_delta)
    abs_rank = abs(rank_delta)
    lower_piece = piece.lower()

    if lower_piece == "n":
        return (abs_file, abs_rank) in {(1, 2), (2, 1)}

    if lower_piece == "k":
        if max(abs_file, abs_rank) == 1:
            return True
        # Castling: king moves 2 squares horizontally from starting position
        if rank_delta == 0 and abs_file == 2:
            src_rank = src_idx // 8
            expected_rank = 0 if piece.isupper() else 7
            if src_rank != expected_rank or src_idx % 8 != 4:
                return False
            rook_piece = "R" if piece.isupper() else "r"
            rook_src = src_rank * 8 + (7 if file_delta > 0 else 0)
            if basis[rook_src] != rook_piece:
                return False
            return _castling_path_is_clear(basis, src_idx, file_delta)
        return False

    if lower_piece == "b":
        return abs_file == abs_rank and _path_is_clear(basis, src_idx, tgt_idx)

    if lower_piece == "r":
        return (file_delta == 0 or rank_delta == 0) and _path_is_clear(basis, src_idx, tgt_idx)

    if lower_piece == "q":
        diagonal = abs_file == abs_rank
        straight = file_delta == 0 or rank_delta == 0
        return (diagonal or straight) and _path_is_clear(basis, src_idx, tgt_idx)

    if lower_piece == "p":
        direction = 1 if piece.isupper() else -1
        src_rank = src_idx // 8
        start_rank = 1 if piece.isupper() else 6
        one_step = file_delta == 0 and rank_delta == direction and target_piece is None
        two_step = (
            file_delta == 0
            and rank_delta == 2 * direction
            and src_rank == start_rank
            and target_piece is None
            and _path_is_clear(basis, src_idx, tgt_idx)
        )
        diagonal_capture = abs_file == 1 and rank_delta == direction and (
            (target_piece is not None and _piece_color(target_piece) != _piece_color(piece))
            or allow_empty_target_for_pawn_diagonal
            or (en_passant_idx is not None and tgt_idx == en_passant_idx)
        )
        return one_step or two_step or diagonal_capture

    return False


def _apply_move_to_basis(
    basis: list,
    src_idx: int,
    tgt_idx: int,
    en_passant_idx: Optional[int],
) -> None:
    """Apply a move with its implicit side-effects to a mutable basis list in-place."""
    piece = basis[src_idx]
    basis[tgt_idx] = piece
    basis[src_idx] = None

    if piece is None:
        return

    # En passant: remove captured pawn from its actual square (adjacent to landing square)
    if piece.lower() == "p" and en_passant_idx is not None and tgt_idx == en_passant_idx:
        direction = 1 if piece.isupper() else -1
        captured_rank = (en_passant_idx // 8) - direction
        basis[captured_rank * 8 + (en_passant_idx % 8)] = None

    # Castling: move rook alongside the king
    if piece.lower() == "k":
        file_delta = (tgt_idx % 8) - (src_idx % 8)
        if abs(file_delta) == 2:
            rank = src_idx // 8
            if file_delta > 0:  # kingside: rook h→f
                basis[rank * 8 + 5] = basis[rank * 8 + 7]
                basis[rank * 8 + 7] = None
            else:              # queenside: rook a→d
                basis[rank * 8 + 3] = basis[rank * 8 + 0]
                basis[rank * 8 + 0] = None


def validate_move_on_basis(
    basis: BasisState,
    src: str,
    target: str,
    *,
    allow_empty_target_for_pawn_diagonal: bool = False,
    en_passant_idx: Optional[int] = None,
    castling_rights: Optional[dict] = None,
) -> str:
    src_idx = parse_square(src)
    tgt_idx = parse_square(target)
    piece = basis[src_idx]
    if piece is None:
        raise ValueError(f"no piece at source square {src}")

    # Check castling rights before the board-geometry test
    if piece.lower() == "k" and castling_rights is not None:
        file_delta = (tgt_idx % 8) - (src_idx % 8)
        if abs(file_delta) == 2:
            side = "white" if piece.isupper() else "black"
            flank = "kingside" if file_delta > 0 else "queenside"
            if not castling_rights.get(f"{side}_{flank}", False):
                raise ValueError(f"castling rights lost: {side} {flank}")

    if not _is_legal_piece_move(
        piece,
        src_idx,
        tgt_idx,
        basis,
        allow_empty_target_for_pawn_diagonal=allow_empty_target_for_pawn_diagonal,
        en_passant_idx=en_passant_idx,
    ):
        raise ValueError(f"illegal move for {piece} from {src} to {target}")

    return piece


def _occupied_basis_states(state: BoardState, src: str) -> Iterable[BasisState]:
    src_idx = parse_square(src)
    for basis in state.amplitudes:
        if basis[src_idx] is not None:
            yield basis


def _piece_for_quantum_source(state: BoardState, src: str) -> str:
    piece = state.occupied_piece(src)
    if piece is None:
        raise ValueError(f"no piece present at {src}")
    return piece


def _king_square(basis: BasisState, color: str) -> Optional[int]:
    king_piece = "K" if color == "white" else "k"
    for idx, piece in enumerate(basis):
        if piece == king_piece:
            return idx
    return None


_ALL_SQUARES: list[str] = [square_name(idx) for idx in range(64)]


def _basis_allows_move(
    basis: BasisState,
    src: str,
    target: str,
    ep_idx: Optional[int],
    castling_rights: Optional[dict],
    *,
    allow_empty_target_for_pawn_diagonal: bool = False,
) -> bool:
    try:
        validate_move_on_basis(
            basis, src, target,
            en_passant_idx=ep_idx,
            castling_rights=castling_rights,
            allow_empty_target_for_pawn_diagonal=allow_empty_target_for_pawn_diagonal,
        )
        return True
    except ValueError:
        return False


def legal_moves_for(
    state: BoardState,
    color: str,
    *,
    castling_rights: Optional[dict] = None,
    en_passant_target: Optional[str] = None,
) -> list[tuple[str, str]]:
    """Return all legal (src, target) move pairs for the given color.

    A move is legal if the color has a piece at src in at least one basis state
    AND validate_move_on_basis succeeds on at least one occupied basis state for src.
    This allows moves through squares occupied only in some branches (implicit
    entanglement: the piece moves in clear-path branches, stays in blocked ones).

    Note: No self-check filtering; check/checkmate is not a concept in this
    quantum chess variant.
    """
    ep_idx = parse_square(en_passant_target) if en_passant_target else None

    src_squares: set[str] = set()
    for basis in state.amplitudes:
        for idx, piece in enumerate(basis):
            if piece is not None and _piece_color(piece) == color:
                src_squares.add(square_name(idx))

    if not src_squares:
        return []

    result: list[tuple[str, str]] = []

    for src in src_squares:
        src_idx = parse_square(src)
        occupied_bases = [
            (basis, amp)
            for basis, amp in state.amplitudes.items()
            if basis[src_idx] is not None
        ]

        for target in _ALL_SQUARES:
            if target == src:
                continue

            if not any(
                _basis_allows_move(b, src, target, ep_idx, castling_rights)
                for b, _ in occupied_bases
            ):
                continue

            result.append((src, target))

    return result


def _king_probability(state: BoardState, color: str) -> float:
    king_piece = "K" if color == "white" else "k"
    return sum(
        abs(amp) ** 2
        for basis, amp in state.amplitudes.items()
        if any(p == king_piece for p in basis)
    )


def game_status(state: BoardState) -> str:
    """Return 'ongoing', 'white_wins', or 'black_wins'."""
    white_alive = _king_probability(state, "white") > 0
    black_alive = _king_probability(state, "black") > 0
    if not white_alive:
        return "black_wins"
    if not black_alive:
        return "white_wins"
    return "ongoing"


_CASTLING_INITIAL = {
    "white_kingside": True,
    "white_queenside": True,
    "black_kingside": True,
    "black_queenside": True,
}

# Squares whose occupant moving revokes the associated castling right(s)
_CASTLING_REVOKE_MAP: dict[int, list[str]] = {
    parse_square("e1"): ["white_kingside", "white_queenside"],
    parse_square("h1"): ["white_kingside"],
    parse_square("a1"): ["white_queenside"],
    parse_square("e8"): ["black_kingside", "black_queenside"],
    parse_square("h8"): ["black_kingside"],
    parse_square("a8"): ["black_queenside"],
}


@dataclass
class QuantumGame:
    board_state: BoardState
    side_to_move: str = "white"
    fullmove_number: int = 1
    castling_rights: dict = field(default_factory=lambda: dict(_CASTLING_INITIAL))
    en_passant_target: Optional[str] = None
    last_move_outcome: Optional[str] = None  # "success" | "capture_failed"

    @classmethod
    def initial(cls) -> "QuantumGame":
        return cls(board_state=BoardState.initial())

    def piece_at(self, square: str) -> Optional[str]:
        return self.board_state.occupied_piece(square)

    def _assert_side_to_move(self, piece: str):
        if _piece_color(piece) != self.side_to_move:
            raise ValueError(f"it is {self.side_to_move}'s turn, not {_piece_color(piece)}'s")

    def _advance_turn(self):
        if self.side_to_move == "white":
            self.side_to_move = "black"
            return
        self.side_to_move = "white"
        self.fullmove_number += 1

    def _revoke_castling_rights(self, square_idx: int) -> None:
        for right in _CASTLING_REVOKE_MAP.get(square_idx, []):
            self.castling_rights[right] = False

    def _execute_move(self, src_idx: int, tgt_idx: int, piece: str, ep_idx: Optional[int]):
        """Apply the physical move to branches where the path is clear; leave blocked branches
        unmodified (implicit entanglement). Handle rook for castling, handle en passant removal."""
        modified: dict = {}
        unmodified: dict = {}
        for basis, amplitude in self.board_state.amplitudes.items():
            if basis[src_idx] is None:
                unmodified[basis] = amplitude
                continue
            if not _would_move_in_basis(basis, src_idx, tgt_idx, piece):
                # Path blocked in this branch: piece stays, creating entanglement
                unmodified[basis] = amplitude
                continue
            moved = list(basis)
            _apply_move_to_basis(moved, src_idx, tgt_idx, ep_idx)
            moved_t = tuple(moved)
            modified[moved_t] = modified.get(moved_t, 0j) + amplitude

        result_amps = dict(modified)
        for basis, amp in unmodified.items():
            result_amps[basis] = result_amps.get(basis, 0j) + amp
        self.board_state = BoardState(amplitudes=result_amps)
        self.board_state.normalize()

        self._revoke_castling_rights(src_idx)
        self._revoke_castling_rights(tgt_idx)

        if piece.lower() == "p" and abs(tgt_idx - src_idx) == 16:
            self.en_passant_target = square_name((src_idx + tgt_idx) // 2)
        else:
            self.en_passant_target = None

        if (piece == "P" and tgt_idx // 8 == 7) or (piece == "p" and tgt_idx // 8 == 0):
            queen = "Q" if piece.isupper() else "q"
            new_amps = {}
            for basis, amp in self.board_state.amplitudes.items():
                lst = list(basis)
                if lst[tgt_idx] == piece:
                    lst[tgt_idx] = queen
                new_amps[tuple(lst)] = amp
            self.board_state = BoardState(amplitudes=new_amps)

        self._advance_turn()

    def apply_classical_move(self, src: str, target: str):
        occupied_bases = list(_occupied_basis_states(self.board_state, src))
        if not occupied_bases:
            raise ValueError(f"no piece present at {src}")

        piece = self.board_state.occupied_piece(src)
        if piece is None:
            raise ValueError(f"no piece present at {src}")

        self._assert_side_to_move(piece)

        ep_idx = parse_square(self.en_passant_target) if self.en_passant_target else None

        src_idx = parse_square(src)
        tgt_idx = parse_square(target)

        is_pawn = piece.lower() == "p"
        is_pawn_diagonal = is_pawn and abs((tgt_idx % 8) - (src_idx % 8)) == 1

        is_ep = ep_idx is not None and tgt_idx == ep_idx
        is_capture = any(
            basis[tgt_idx] is not None and _piece_color(basis[tgt_idx]) != _piece_color(piece)
            for basis in self.board_state.amplitudes
            if basis[src_idx] is not None
        )

        # ANY-basis check: move must be geometrically valid in at least one occupied branch.
        # Branches where the path is blocked will be left unmodified by _execute_move,
        # creating implicit entanglement between the moving piece and the blocker.
        any_valid = any(
            _basis_allows_move(
                basis, src, target,
                ep_idx,
                self.castling_rights,
                allow_empty_target_for_pawn_diagonal=is_pawn_diagonal and (is_capture or is_ep),
            )
            for basis in occupied_bases
        )
        if not any_valid:
            # Raise error from the first basis so the caller sees a meaningful message
            validate_move_on_basis(
                occupied_bases[0], src, target,
                allow_empty_target_for_pawn_diagonal=is_pawn_diagonal and (is_capture or is_ep),
                en_passant_idx=ep_idx,
                castling_rights=self.castling_rights,
            )

        needs_src_observation = (is_capture or is_pawn_diagonal or is_ep) and \
                                self.board_state.probability(src) < 1.0 - 1e-9

        src_present_after_src_obs = True

        # En passant: observe captured pawn first.
        # This matches rules/examples where a failed target observation can abort
        # before the attacking pawn is observed.
        if is_ep:
            direction = 1 if piece.isupper() else -1
            captured_rank = (ep_idx // 8) - direction
            captured_sq = square_name(captured_rank * 8 + (ep_idx % 8))
            cap_prob = self.board_state.probability(captured_sq)
            if cap_prob < 1.0 - 1e-9:
                cap_present, self.board_state = observe_square(self.board_state, captured_sq)
                if not cap_present:
                    self.last_move_outcome = "capture_failed"
                    self.en_passant_target = None
                    self._advance_turn()
                    return
            if needs_src_observation:
                src_present, self.board_state = observe_square(self.board_state, src)
                src_present_after_src_obs = src_present
                if not src_present:
                    self.last_move_outcome = "capture_failed"
                    self.en_passant_target = None
                    self._advance_turn()
                    return
        else:
            if needs_src_observation:
                src_present, self.board_state = observe_square(self.board_state, src)
                src_present_after_src_obs = src_present
                if not src_present:
                    self.last_move_outcome = "capture_failed"
                    self._revoke_castling_rights(src_idx)
                    self.en_passant_target = None
                    self._advance_turn()
                    return

            # Pawn diagonal capture: also observe the target
            if src_present_after_src_obs and is_pawn_diagonal:
                tgt_prob = self.board_state.probability(target)
                if tgt_prob < 1.0 - 1e-9:
                    tgt_present, self.board_state = observe_square(self.board_state, target)
                    if not tgt_present:
                        self.last_move_outcome = "capture_failed"
                        self.en_passant_target = None
                        self._advance_turn()
                        return

        self._execute_move(src_idx, tgt_idx, piece, ep_idx)
        self.last_move_outcome = "success"

    def apply_split_move(self, src: str, target_a: str, target_b: str):
        self.last_move_outcome = None
        if target_a == target_b:
            raise ValueError("split move targets must differ")

        piece = _piece_for_quantum_source(self.board_state, src)
        self._assert_side_to_move(piece)

        # Pawn-specific geometry check must come before the empty-target check so that
        # the promotion-rank error is raised even when the target squares are occupied.
        if piece.lower() == "p":
            back_rank = 7 if piece.isupper() else 0
            if parse_square(target_a) // 8 == back_rank or parse_square(target_b) // 8 == back_rank:
                raise ValueError("pawn cannot split to promotion rank")

        # Split moves are non-capturing: both targets must be empty across all basis states
        for sq in (target_a, target_b):
            if self.board_state.probability(sq) > 1e-9:
                raise ValueError(f"split target {sq} must be empty (split moves cannot capture)")

        occupied_bases = list(_occupied_basis_states(self.board_state, src))
        # ANY-basis: valid if at least one branch allows both split targets
        any_valid = any(
            _basis_allows_move(b, src, target_a, None, self.castling_rights) and
            _basis_allows_move(b, src, target_b, None, self.castling_rights)
            for b in occupied_bases
        )
        if not any_valid:
            # Raise a meaningful error from the first basis
            validate_move_on_basis(occupied_bases[0], src, target_a, castling_rights=self.castling_rights)
            validate_move_on_basis(occupied_bases[0], src, target_b, castling_rights=self.castling_rights)

        self._revoke_castling_rights(parse_square(src))
        self.en_passant_target = None

        self.board_state = split_move(self.board_state, src, target_a, target_b)
        self.board_state.normalize()

        # If king split to a castling destination, move the rook in those branches
        if piece.lower() == "k":
            src_idx_local = parse_square(src)
            for target in (target_a, target_b):
                tgt_idx = parse_square(target)
                file_delta = (tgt_idx % 8) - (src_idx_local % 8)
                if abs(file_delta) == 2:
                    rank = src_idx_local // 8
                    if file_delta > 0:
                        rook_from = rank * 8 + 7
                        rook_to = rank * 8 + 5
                    else:
                        rook_from = rank * 8 + 0
                        rook_to = rank * 8 + 3
                    new_amps = {}
                    for basis, amp in self.board_state.amplitudes.items():
                        if basis[tgt_idx] == piece:
                            lst = list(basis)
                            lst[rook_to] = lst[rook_from]
                            lst[rook_from] = None
                            new_amps[tuple(lst)] = amp
                        else:
                            new_amps[basis] = amp
                    self.board_state = BoardState(amplitudes=new_amps)

        self._advance_turn()

    def apply_merge_move(self, src_a: str, src_b: str, target: str):
        self.last_move_outcome = None
        if src_a == src_b:
            raise ValueError("merge move requires two distinct source squares")

        piece_a = _piece_for_quantum_source(self.board_state, src_a)
        piece_b = _piece_for_quantum_source(self.board_state, src_b)
        if piece_a != piece_b:
            raise ValueError("merge move requires matching piece identities")

        if self.board_state.probability(target) > 1e-9:
            raise ValueError("merge target must be empty (merge moves cannot capture)")

        self._assert_side_to_move(piece_a)

        src_a_idx = parse_square(src_a)
        src_b_idx = parse_square(src_b)

        occupied_a = list(_occupied_basis_states(self.board_state, src_a))
        occupied_b = list(_occupied_basis_states(self.board_state, src_b))
        if not occupied_a or not occupied_b:
            raise ValueError("merge move requires occupied branches at both source squares")

        # Two independent pieces of the same type can coexist in one basis.
        # A legal merge requires two copies of one original piece, which are
        # mutually exclusive across branches.
        if any(basis[src_a_idx] is not None and basis[src_b_idx] is not None for basis in self.board_state.amplitudes):
            raise ValueError("merge move requires two copies of the same original piece")

        # ANY-basis: each source must be able to reach target in at least one branch
        any_valid_a = any(
            _basis_allows_move(
                b, src_a, target, None, self.castling_rights,
            )
            for b in occupied_a
        )
        any_valid_b = any(
            _basis_allows_move(
                b, src_b, target, None, self.castling_rights,
            )
            for b in occupied_b
        )
        if not any_valid_a:
            validate_move_on_basis(
                list(occupied_a)[0], src_a, target,
                castling_rights=self.castling_rights,
            )
        if not any_valid_b:
            validate_move_on_basis(
                list(occupied_b)[0], src_b, target,
                castling_rights=self.castling_rights,
            )

        self._revoke_castling_rights(parse_square(src_a))
        self._revoke_castling_rights(parse_square(src_b))
        self.en_passant_target = None

        self.board_state = merge_move(self.board_state, src_a, src_b, target)
        self._advance_turn()

    def board_summary(self) -> dict[str, Optional[str]]:
        summary = {}
        for idx in range(64):
            square = square_name(idx)
            try:
                summary[square] = self.piece_at(square)
            except ValueError:
                summary[square] = None
        return summary
