import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from engine.board_state import BoardState, parse_square
from engine.game_state import QuantumGame, _would_move_in_basis, game_status, legal_moves_for, validate_move_on_basis


class MoveValidationTest(unittest.TestCase):
    def test_validate_move_on_basis_allows_clear_knight_move(self):
        basis = BoardState._board_to_tuple({"b1": "N"})

        piece = validate_move_on_basis(basis, "b1", "c3")

        self.assertEqual(piece, "N")

    def test_validate_move_on_basis_rejects_blocked_bishop(self):
        basis = BoardState._board_to_tuple({"c1": "B", "d2": "P"})

        with self.assertRaisesRegex(ValueError, "illegal move"):
            validate_move_on_basis(basis, "c1", "g5")

    def test_validate_move_on_basis_rejects_same_color_capture(self):
        basis = BoardState._board_to_tuple({"a1": "R", "a3": "P"})

        with self.assertRaisesRegex(ValueError, "illegal move"):
            validate_move_on_basis(basis, "a1", "a3")

    def test_validate_move_on_basis_allows_pawn_two_step_from_start(self):
        basis = BoardState._board_to_tuple({"e2": "P"})

        piece = validate_move_on_basis(basis, "e2", "e4")

        self.assertEqual(piece, "P")


class QuantumGameTest(unittest.TestCase):
    def test_initial_game_starts_with_white_to_move(self):
        game = QuantumGame.initial()

        self.assertEqual(game.side_to_move, "white")
        self.assertEqual(game.fullmove_number, 1)
        self.assertEqual(game.piece_at("e1"), "K")
        self.assertEqual(game.piece_at("e8"), "k")

    def test_apply_classical_move_updates_board_and_turn(self):
        game = QuantumGame(
            board_state=BoardState(amplitudes={BoardState._board_to_tuple({"b1": "N"}): 1 + 0j})
        )

        game.apply_classical_move("b1", "c3")

        self.assertIsNone(game.piece_at("b1"))
        self.assertEqual(game.piece_at("c3"), "N")
        self.assertEqual(game.side_to_move, "black")
        self.assertEqual(game.fullmove_number, 1)

    def test_apply_classical_move_rejects_wrong_side_to_move(self):
        game = QuantumGame(
            board_state=BoardState(amplitudes={BoardState._board_to_tuple({"b8": "n"}): 1 + 0j})
        )

        with self.assertRaisesRegex(ValueError, "white's turn"):
            game.apply_classical_move("b8", "c6")

    def test_apply_classical_move_advances_fullmove_after_black_turn(self):
        white_basis = BoardState._board_to_tuple({"b1": "N", "b8": "n"})
        game = QuantumGame(board_state=BoardState(amplitudes={white_basis: 1 + 0j}))

        game.apply_classical_move("b1", "c3")
        game.apply_classical_move("b8", "c6")

        self.assertEqual(game.side_to_move, "white")
        self.assertEqual(game.fullmove_number, 2)

    def test_apply_split_move_requires_legal_targets(self):
        game = QuantumGame(
            board_state=BoardState(amplitudes={BoardState._board_to_tuple({"c1": "B", "d2": "P"}): 1 + 0j})
        )

        with self.assertRaisesRegex(ValueError, "illegal move"):
            game.apply_split_move("c1", "g5", "h6")

    def test_apply_split_move_updates_board_state(self):
        game = QuantumGame(
            board_state=BoardState(amplitudes={BoardState._board_to_tuple({"b1": "N"}): 1 + 0j})
        )

        game.apply_split_move("b1", "a3", "c3")

        self.assertAlmostEqual(game.board_state.probability("a3"), 0.5)
        self.assertAlmostEqual(game.board_state.probability("c3"), 0.5)
        self.assertEqual(game.side_to_move, "black")

    def test_apply_merge_move_rejects_different_piece_identities(self):
        basis_a = BoardState._board_to_tuple({"a3": "N"})
        basis_b = BoardState._board_to_tuple({"c3": "B"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis_a: 0.5 + 0j, basis_b: 0.5 + 0j}))

        with self.assertRaisesRegex(ValueError, "matching piece identities"):
            game.apply_merge_move("a3", "c3", "b1")

    def test_apply_merge_move_round_trips_split_knight(self):
        game = QuantumGame(
            board_state=BoardState(amplitudes={BoardState._board_to_tuple({"b1": "N"}): 1 + 0j})
        )

        game.apply_split_move("b1", "a3", "c3")
        game.side_to_move = "white"
        game.apply_merge_move("a3", "c3", "b1")

        self.assertEqual(list(game.board_state.amplitudes.keys()), [BoardState._board_to_tuple({"b1": "N"})])
        self.assertAlmostEqual(abs(next(iter(game.board_state.amplitudes.values()))) ** 2, 1.0)


class MergeMoveRulesTest(unittest.TestCase):
    def test_merge_move_rejects_occupied_target_square(self):
        import math
        amp = 1 / math.sqrt(2)
        basis_a = BoardState._board_to_tuple({"a3": "N", "b1": "p", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"c3": "N", "b1": "p", "e1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j}))

        with self.assertRaisesRegex(ValueError, "merge target must be empty"):
            game.apply_merge_move("a3", "c3", "b1")

    def test_merge_move_rejects_independent_same_type_pieces(self):
        basis = BoardState._board_to_tuple({"a3": "N", "c3": "N", "e1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))

        with self.assertRaisesRegex(ValueError, "same original piece"):
            game.apply_merge_move("a3", "c3", "b1")




class LegalMovesTest(unittest.TestCase):
    def test_initial_position_white_has_20_moves(self):
        state = BoardState.initial()
        moves = legal_moves_for(state, "white")
        self.assertEqual(len(moves), 20)

    def test_initial_position_black_also_has_20_moves(self):
        # legal_moves_for doesn't enforce turn — it returns moves regardless of whose turn it is
        state = BoardState.initial()
        moves = legal_moves_for(state, "black")
        self.assertEqual(len(moves), 20)

    def test_returns_empty_when_color_has_no_pieces(self):
        basis = BoardState._board_to_tuple({"e1": "K"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        moves = legal_moves_for(state, "black")
        self.assertEqual(moves, [])

    def test_superposition_allows_move_legal_in_at_least_one_branch(self):
        import math
        # Knight in superposition at b1: in branch A target c3 is empty (valid),
        # in branch B a white pawn occupies c3 (same-color capture, invalid in that branch).
        # Under "any basis" semantics the move b1->c3 IS legal: the knight moves in branch A
        # and stays in branch B (creating entanglement). Only if it's illegal in ALL branches
        # would it be excluded.
        basis_a = BoardState._board_to_tuple({"b1": "N", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"b1": "N", "c3": "P", "e1": "K", "e8": "k"})
        amp = 1 / math.sqrt(2)
        state = BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        moves = legal_moves_for(state, "white")
        self.assertIn(("b1", "c3"), moves)
        # a3 is free in both branches, so b1->a3 must also be legal
        self.assertIn(("b1", "a3"), moves)


class GameStatusTest(unittest.TestCase):
    def test_ongoing_when_legal_moves_exist(self):
        basis = BoardState._board_to_tuple({"e1": "K", "e8": "k"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        self.assertEqual(game_status(state), "ongoing")


class PromotionTest(unittest.TestCase):
    def test_split_move_to_promotion_rank_raises(self):
        basis = BoardState._board_to_tuple({"e7": "P", "d8": "r", "f8": "r", "a1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        with self.assertRaisesRegex(ValueError, "pawn cannot split to promotion rank"):
            game.apply_split_move("e7", "d8", "f8")


class AutoPromotionTest(unittest.TestCase):
    def test_pawn_auto_promotes_to_queen_on_back_rank(self):
        basis = BoardState._board_to_tuple({"e7": "P", "a1": "K", "a8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        game.apply_classical_move("e7", "e8")
        self.assertEqual(game.piece_at("e8"), "Q")
        self.assertEqual(game.side_to_move, "black")

    def test_black_pawn_auto_promotes_to_queen(self):
        basis = BoardState._board_to_tuple({"e2": "p", "h1": "K", "h8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}), side_to_move="black")
        game.apply_classical_move("e2", "e1")
        self.assertEqual(game.piece_at("e1"), "q")
        self.assertEqual(game.side_to_move, "white")

    def test_pawn_in_superposition_auto_promotes_in_branch(self):
        import math
        basis_a = BoardState._board_to_tuple({"e7": "P", "a1": "K", "a8": "k"})
        basis_b = BoardState._board_to_tuple({"d7": "P", "a1": "K", "a8": "k"})
        amp = 1 / math.sqrt(2)
        game = QuantumGame(board_state=BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j}))
        game.apply_classical_move("e7", "e8")
        e8_prob = game.board_state.probability("e8")
        self.assertAlmostEqual(e8_prob, 0.5)


class CastlingTest(unittest.TestCase):
    def _kingside_setup(self, color: str) -> QuantumGame:
        """King and kingside rook only — path already clear."""
        if color == "white":
            basis = BoardState._board_to_tuple({"e1": "K", "h1": "R", "e8": "k"})
        else:
            basis = BoardState._board_to_tuple({"e8": "k", "h8": "r", "e1": "K"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis: 1 + 0j}),
            side_to_move=color,
        )
        return game

    def _queenside_setup(self, color: str) -> QuantumGame:
        if color == "white":
            basis = BoardState._board_to_tuple({"e1": "K", "a1": "R", "e8": "k"})
        else:
            basis = BoardState._board_to_tuple({"e8": "k", "a8": "r", "e1": "K"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis: 1 + 0j}),
            side_to_move=color,
        )
        return game

    def test_white_kingside_castle_moves_king_and_rook(self):
        game = self._kingside_setup("white")
        game.apply_classical_move("e1", "g1")
        self.assertEqual(game.piece_at("g1"), "K")
        self.assertEqual(game.piece_at("f1"), "R")
        self.assertIsNone(game.piece_at("e1"))
        self.assertIsNone(game.piece_at("h1"))

    def test_white_queenside_castle_moves_king_and_rook(self):
        game = self._queenside_setup("white")
        game.apply_classical_move("e1", "c1")
        self.assertEqual(game.piece_at("c1"), "K")
        self.assertEqual(game.piece_at("d1"), "R")
        self.assertIsNone(game.piece_at("e1"))
        self.assertIsNone(game.piece_at("a1"))

    def test_black_kingside_castle_moves_king_and_rook(self):
        game = self._kingside_setup("black")
        game.apply_classical_move("e8", "g8")
        self.assertEqual(game.piece_at("g8"), "k")
        self.assertEqual(game.piece_at("f8"), "r")
        self.assertIsNone(game.piece_at("e8"))
        self.assertIsNone(game.piece_at("h8"))

    def test_black_queenside_castle_moves_king_and_rook(self):
        game = self._queenside_setup("black")
        game.apply_classical_move("e8", "c8")
        self.assertEqual(game.piece_at("c8"), "k")
        self.assertEqual(game.piece_at("d8"), "r")
        self.assertIsNone(game.piece_at("e8"))
        self.assertIsNone(game.piece_at("a8"))

    def test_castle_blocked_by_piece_in_path(self):
        basis = BoardState._board_to_tuple({"e1": "K", "h1": "R", "f1": "B", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        with self.assertRaisesRegex(ValueError, "illegal move"):
            game.apply_classical_move("e1", "g1")

    def test_castling_rights_revoked_after_king_moves(self):
        game = self._kingside_setup("white")
        game.apply_classical_move("e1", "f1")  # normal king move
        # Now try to move back and castle — rights should be gone
        game.side_to_move = "white"
        game.apply_classical_move("f1", "e1")
        game.side_to_move = "white"
        self.assertFalse(game.castling_rights["white_kingside"])
        with self.assertRaisesRegex(ValueError, "castling rights lost"):
            game.apply_classical_move("e1", "g1")

    def test_castling_rights_revoked_after_rook_moves(self):
        game = self._kingside_setup("white")
        game.apply_classical_move("h1", "g1")  # rook moves
        game.side_to_move = "white"
        game.apply_classical_move("g1", "h1")  # rook returns
        game.side_to_move = "white"
        self.assertFalse(game.castling_rights["white_kingside"])
        with self.assertRaisesRegex(ValueError, "castling rights lost"):
            game.apply_classical_move("e1", "g1")

    def test_castling_rights_revoked_for_king_after_split(self):
        basis = BoardState._board_to_tuple({"e1": "K", "h1": "R", "e8": "k", "f1": None, "d1": None})
        # Give king squares to split to
        basis2 = BoardState._board_to_tuple({"e1": "K", "h1": "R", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis2: 1 + 0j}))
        # Split king to d1 and f1 — both must be reachable
        game.apply_split_move("e1", "d1", "f1")
        self.assertFalse(game.castling_rights["white_kingside"])
        self.assertFalse(game.castling_rights["white_queenside"])

    def test_kingside_castle_entangles_with_superposed_piece_in_path(self):
        import math
        # Bishop 50% at f1 (blocks kingside castle path), 50% at g5 (path clear).
        # King at e1, rook at h1. King attempts to castle kingside (e1->g1).
        # Expected after fix:
        #   clear branch  -> king castles to g1, rook moves to f1
        #   blocked branch -> king stays at e1, rook stays at h1, bishop stays at f1
        basis_blocked = BoardState._board_to_tuple({"e1": "K", "h1": "R", "f1": "B", "e8": "k"})
        basis_clear   = BoardState._board_to_tuple({"e1": "K", "h1": "R", "g5": "B", "e8": "k"})
        amp = 1 / math.sqrt(2)
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis_blocked: amp + 0j, basis_clear: amp + 0j}),
            side_to_move="white",
        )
        game.apply_classical_move("e1", "g1")

        # King should be split between e1 (blocked branch) and g1 (castled branch)
        self.assertAlmostEqual(game.board_state.probability("g1"), 0.5, places=3)
        self.assertAlmostEqual(game.board_state.probability("e1"), 0.5, places=3)
        # Rook stays at h1 in blocked branch, moves to f1 in castled branch
        self.assertAlmostEqual(game.board_state.probability("h1"), 0.5, places=3)
        # Bishop at f1 survives in blocked branch (not overwritten by rook)
        e1_idx = parse_square("e1")
        f1_idx = parse_square("f1")
        blocked_bases = [b for b in game.board_state.amplitudes if b[e1_idx] == "K"]
        for b in blocked_bases:
            self.assertEqual(b[f1_idx], "B",
                "Bishop at f1 must not be overwritten by rook in the blocked branch")


class EnPassantTest(unittest.TestCase):
    def test_en_passant_target_set_after_two_step_pawn_move(self):
        basis = BoardState._board_to_tuple({"e2": "P", "e1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        game.apply_classical_move("e2", "e4")
        self.assertEqual(game.en_passant_target, "e3")

    def test_en_passant_target_cleared_after_non_two_step_move(self):
        basis = BoardState._board_to_tuple({"e4": "P", "e1": "K", "e8": "k"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis: 1 + 0j}),
            en_passant_target="e3",
        )
        game.apply_classical_move("e4", "e5")
        self.assertIsNone(game.en_passant_target)

    def test_white_captures_en_passant(self):
        # Black pawn just moved d7→d5; white pawn at e5 can capture en passant to d6
        basis = BoardState._board_to_tuple({"e5": "P", "d5": "p", "e1": "K", "e8": "k"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis: 1 + 0j}),
            en_passant_target="d6",
        )
        game.apply_classical_move("e5", "d6")
        self.assertEqual(game.piece_at("d6"), "P")
        self.assertIsNone(game.piece_at("e5"))
        self.assertIsNone(game.piece_at("d5"))  # captured pawn removed

    def test_black_captures_en_passant(self):
        # White pawn just moved e2→e4; black pawn at d4 can capture en passant to e3
        basis = BoardState._board_to_tuple({"d4": "p", "e4": "P", "e1": "K", "e8": "k"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis: 1 + 0j}),
            side_to_move="black",
            en_passant_target="e3",
        )
        game.apply_classical_move("d4", "e3")
        self.assertEqual(game.piece_at("e3"), "p")
        self.assertIsNone(game.piece_at("d4"))
        self.assertIsNone(game.piece_at("e4"))  # captured white pawn removed

    def test_en_passant_appears_in_legal_moves(self):
        basis = BoardState._board_to_tuple({"e5": "P", "d5": "p", "e1": "K", "e8": "k"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        moves = legal_moves_for(state, "white", en_passant_target="d6")
        self.assertIn(("e5", "d6"), moves)

    def test_en_passant_not_in_legal_moves_without_target(self):
        basis = BoardState._board_to_tuple({"e5": "P", "d5": "p", "e1": "K", "e8": "k"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        moves = legal_moves_for(state, "white")  # no en_passant_target
        self.assertNotIn(("e5", "d6"), moves)

    def test_en_passant_target_cleared_after_split_move(self):
        basis = BoardState._board_to_tuple({"b1": "N", "e1": "K", "e8": "k"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis: 1 + 0j}),
            en_passant_target="e3",
        )
        game.apply_split_move("b1", "a3", "c3")
        self.assertIsNone(game.en_passant_target)

    def test_en_passant_target_observed_before_attacker(self):
        # Four equally likely branches:
        # - white pawn at c4 or c3
        # - black pawn at d4 or d3
        # EP capture is c4xd5 with captured pawn on d4.
        basis_a = BoardState._board_to_tuple({"c4": "P", "d4": "p", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"c3": "P", "d4": "p", "e1": "K", "e8": "k"})
        basis_c = BoardState._board_to_tuple({"c4": "P", "d3": "p", "e1": "K", "e8": "k"})
        basis_d = BoardState._board_to_tuple({"c3": "P", "d3": "p", "e1": "K", "e8": "k"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={
                basis_a: 0.5 + 0j,
                basis_b: 0.5 + 0j,
                basis_c: 0.5 + 0j,
                basis_d: 0.5 + 0j,
            }),
            en_passant_target="d5",
        )

        with patch("engine.quantum_ops.random.choices", return_value=[False]) as mocked:
            game.apply_classical_move("c4", "d5")

        self.assertEqual(game.last_move_outcome, "capture_failed")
        self.assertEqual(mocked.call_count, 1)
        # Attacker wasn't observed after target failed; white pawn stays superposed.
        self.assertAlmostEqual(game.board_state.probability("c4"), 0.5, places=5)
        self.assertAlmostEqual(game.board_state.probability("c3"), 0.5, places=5)

    def test_en_passant_can_fail_after_target_present_if_attacker_absent(self):
        basis_a = BoardState._board_to_tuple({"c4": "P", "d4": "p", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"c3": "P", "d4": "p", "e1": "K", "e8": "k"})
        basis_c = BoardState._board_to_tuple({"c4": "P", "d3": "p", "e1": "K", "e8": "k"})
        basis_d = BoardState._board_to_tuple({"c3": "P", "d3": "p", "e1": "K", "e8": "k"})
        game = QuantumGame(
            board_state=BoardState(amplitudes={
                basis_a: 0.5 + 0j,
                basis_b: 0.5 + 0j,
                basis_c: 0.5 + 0j,
                basis_d: 0.5 + 0j,
            }),
            en_passant_target="d5",
        )

        with patch("engine.quantum_ops.random.choices", side_effect=[[True], [False]]) as mocked:
            game.apply_classical_move("c4", "d5")

        self.assertEqual(game.last_move_outcome, "capture_failed")
        self.assertEqual(mocked.call_count, 2)
        # Target observed present first; then attacker observed absent and removed from c4.
        self.assertAlmostEqual(game.board_state.probability("d4"), 1.0, places=5)
        self.assertAlmostEqual(game.board_state.probability("c4"), 0.0, places=5)
        self.assertAlmostEqual(game.board_state.probability("c3"), 1.0, places=5)


class WinConditionTest(unittest.TestCase):
    def test_ongoing_when_both_kings_present(self):
        basis = BoardState._board_to_tuple({"e1": "K", "e8": "k"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        self.assertEqual(game_status(state), "ongoing")

    def test_black_wins_when_white_king_gone(self):
        basis = BoardState._board_to_tuple({"e8": "k"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        self.assertEqual(game_status(state), "black_wins")

    def test_white_wins_when_black_king_gone(self):
        basis = BoardState._board_to_tuple({"e1": "K"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        self.assertEqual(game_status(state), "white_wins")

    def test_ongoing_when_king_in_superposition_not_zero(self):
        import math
        basis_a = BoardState._board_to_tuple({"e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"g1": "K", "e8": "k"})
        amp = 1 / math.sqrt(2)
        state = BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        self.assertEqual(game_status(state), "ongoing")

    def test_king_can_move_into_attacked_square(self):
        # No self-check restriction: king is free to move anywhere geometrically valid
        basis = BoardState._board_to_tuple({"e1": "K", "e8": "r", "a8": "k"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        # e2 is attacked by the black rook on e8 — but in quantum chess this is legal
        moves = legal_moves_for(state, "white")
        self.assertIn(("e1", "e2"), moves)


class CaptureObservationTest(unittest.TestCase):
    def _capture_setup(self) -> QuantumGame:
        """Knight in superposition a3/c3, enemy pawn at d5."""
        import math
        basis_a = BoardState._board_to_tuple({"a3": "N", "d5": "p", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"c3": "N", "d5": "p", "e1": "K", "e8": "k"})
        amp = 1 / math.sqrt(2)
        return QuantumGame(
            board_state=BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        )

    def test_definite_piece_captures_without_observation(self):
        basis = BoardState._board_to_tuple({"e4": "N", "d6": "p", "e1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        game.apply_classical_move("e4", "d6")
        self.assertEqual(game.piece_at("d6"), "N")
        self.assertIsNone(game.piece_at("e4"))
        self.assertEqual(game.last_move_outcome, "success")

    @patch("engine.quantum_ops.random.choices", return_value=[True])
    def test_superposition_capture_succeeds_when_observed_present(self, _):
        game = self._capture_setup()
        # c3→d5 is a valid knight move (file_delta=1, rank_delta=2)
        game.apply_classical_move("c3", "d5")
        self.assertEqual(game.last_move_outcome, "success")
        self.assertEqual(game.piece_at("d5"), "N")
        self.assertAlmostEqual(game.board_state.probability("d5"), 1.0)

    @patch("engine.quantum_ops.random.choices", return_value=[False])
    def test_superposition_capture_fails_when_observed_absent(self, _):
        game = self._capture_setup()
        game.apply_classical_move("c3", "d5")
        self.assertEqual(game.last_move_outcome, "capture_failed")
        # Pawn untouched
        self.assertEqual(game.piece_at("d5"), "p")
        # Turn advanced (failed capture still costs the turn)
        self.assertEqual(game.side_to_move, "black")


class PawnCaptureObservationTest(unittest.TestCase):
    def _pawn_setup(self) -> QuantumGame:
        """White pawn in superposition c4/e4; black pawn at d5."""
        import math
        basis_a = BoardState._board_to_tuple({"c4": "P", "d5": "p", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"e4": "P", "d5": "p", "e1": "K", "e8": "k"})
        amp = 1 / math.sqrt(2)
        return QuantumGame(
            board_state=BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        )

    @patch("engine.quantum_ops.random.choices", return_value=[True])
    def test_pawn_capture_succeeds_when_both_observed_present(self, _):
        game = self._pawn_setup()
        game.apply_classical_move("c4", "d5")
        self.assertEqual(game.last_move_outcome, "success")
        self.assertEqual(game.piece_at("d5"), "P")

    @patch("engine.quantum_ops.random.choices", return_value=[False])
    def test_pawn_capture_fails_pawn_not_found(self, _):
        game = self._pawn_setup()
        game.apply_classical_move("c4", "d5")
        self.assertEqual(game.last_move_outcome, "capture_failed")
        self.assertEqual(game.piece_at("d5"), "p")
        self.assertEqual(game.side_to_move, "black")

    def test_pawn_capture_definite_pawn_definite_target_always_succeeds(self):
        basis = BoardState._board_to_tuple({"c4": "P", "d5": "p", "e1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        game.apply_classical_move("c4", "d5")
        self.assertEqual(game.last_move_outcome, "success")
        self.assertEqual(game.piece_at("d5"), "P")

    def test_pawn_capture_fails_when_target_not_found(self):
        """Pawn is 100%, target pawn in superposition — target not found on second observe."""
        import math
        basis_a = BoardState._board_to_tuple({"c4": "P", "d5": "p", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"c4": "P", "d6": "p", "e1": "K", "e8": "k"})
        amp = 1 / math.sqrt(2)
        game = QuantumGame(
            board_state=BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        )
        # First call (src observation — skipped since pawn is 100%)
        # Only call: target observation at d5. side_effect makes first call return [False] → absent
        with patch("engine.quantum_ops.random.choices", return_value=[False]):
            game.apply_classical_move("c4", "d5")
        self.assertEqual(game.last_move_outcome, "capture_failed")
        self.assertEqual(game.side_to_move, "black")


    def test_pawn_cannot_move_diagonal_to_empty_non_ep_square(self):
        basis = BoardState._board_to_tuple({"d4": "P", "e1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        with self.assertRaises(ValueError):
            game.apply_classical_move("d4", "e5")  # e5 is empty, not en passant


class CastlingSplitTest(unittest.TestCase):
    def test_king_can_split_to_castle_and_regular_move(self):
        # King at e1, rook at h1, path clear, g1 empty, d1 empty
        basis = BoardState._board_to_tuple({"e1": "K", "h1": "R", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        # Split: king goes to d1 (regular) and g1 (kingside castle)
        game.apply_split_move("e1", "d1", "g1")
        # In the d1 branch: king at d1, rook still at h1
        # In the g1 branch: king at g1, rook at f1 (castled)
        rook_at_h1 = game.board_state.probability("h1")
        rook_at_f1 = game.board_state.probability("f1")
        self.assertAlmostEqual(rook_at_h1, 0.5, places=3)
        self.assertAlmostEqual(rook_at_f1, 0.5, places=3)
        self.assertEqual(game.side_to_move, "black")

    def test_king_split_both_regular_moves_rook_unchanged(self):
        basis = BoardState._board_to_tuple({"e1": "K", "h1": "R", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        game.apply_split_move("e1", "d1", "f1")
        # Neither target is a 2-square move — rook stays at h1 in all branches
        self.assertAlmostEqual(game.board_state.probability("h1"), 1.0, places=3)
        self.assertEqual(game.side_to_move, "black")


class MergeViaRegularMoveTest(unittest.TestCase):
    def test_piece_can_move_to_own_copy_square(self):
        import math
        # Bishop in superposition at c1 (50%) and e3 (50%)
        basis_a = BoardState._board_to_tuple({"c1": "B", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"e3": "B", "e1": "K", "e8": "k"})
        amp = 1 / math.sqrt(2)
        game = QuantumGame(board_state=BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j}))
        # Move bishop from c1 to e3:
        # - In basis_a: normal move c1→e3
        # - In basis_b: bishop already at e3, this branch gets merged
        game.apply_classical_move("c1", "e3")
        # Result: bishop definitely at e3 (both branches collapsed there)
        self.assertAlmostEqual(game.board_state.probability("e3"), 1.0, places=3)
        self.assertAlmostEqual(game.board_state.probability("c1"), 0.0, places=3)

    def test_piece_cannot_move_to_different_friendly_piece(self):
        # Bishop cannot merge with a knight
        basis = BoardState._board_to_tuple({"c1": "B", "e3": "N", "e1": "K", "e8": "k"})
        game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        with self.assertRaises(ValueError):
            game.apply_classical_move("c1", "e3")

    def test_merge_preserves_unrelated_branch_probability(self):
        """Three-branch state: unrelated branch must not lose amplitude during merge."""
        import math
        # 3 branches: 25% bishop@c1, 25% bishop@e3, 50% unrelated (bishop@g5)
        basis_a = BoardState._board_to_tuple({"c1": "B", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"e3": "B", "e1": "K", "e8": "k"})
        basis_c = BoardState._board_to_tuple({"g5": "B", "e1": "K", "e8": "k"})
        amp_a = 0.5 + 0j        # |0.5|^2 = 0.25
        amp_b = 0.5 + 0j        # |0.5|^2 = 0.25
        amp_c = (1 / math.sqrt(2)) + 0j  # |1/√2|^2 = 0.50
        game = QuantumGame(board_state=BoardState(amplitudes={
            basis_a: amp_a,
            basis_b: amp_b,
            basis_c: amp_c,
        }))
        # Move bishop from c1 to e3 (merge):
        # - basis_a: bishop moves c1→e3 (modified)
        # - basis_b: bishop already at e3, stays (unmodified, same key as modified)
        # - basis_c: bishop at g5, no piece at c1, stays (unmodified, different key)
        game.apply_classical_move("c1", "e3")
        # After summing amplitudes: e3 branch = 0.5+0.5=1.0, g5 branch = 1/√2
        # After normalize: e3_prob = 1.0/1.5 ≈ 0.667, g5_prob = 0.5/1.5 ≈ 0.333
        e3_prob = game.board_state.probability("e3")
        g5_prob = game.board_state.probability("g5")
        self.assertAlmostEqual(e3_prob, 2 / 3, places=3)
        self.assertAlmostEqual(g5_prob, 1 / 3, places=3)

    def test_legal_moves_includes_own_copy_square(self):
        import math
        basis_a = BoardState._board_to_tuple({"c1": "B", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"e3": "B", "e1": "K", "e8": "k"})
        amp = 1 / math.sqrt(2)
        state = BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        moves = legal_moves_for(state, "white")
        self.assertIn(("c1", "e3"), moves)


class LegalMovesAnyBasisTest(unittest.TestCase):
    def test_queen_move_through_superposition_piece_is_legal(self):
        """Queen at h5 can move to e8 even when g6 is in superposition (50% pawn)."""
        amp = (1 / 2 ** 0.5) + 0j
        basis_blocked = BoardState._board_to_tuple({"h5": "Q", "g6": "p", "e1": "K", "e8": "k"})
        basis_clear   = BoardState._board_to_tuple({"h5": "Q", "e1": "K", "e8": "k"})

        state = BoardState(amplitudes={
            basis_blocked: amp,
            basis_clear:   amp,
        })

        moves = legal_moves_for(state, "white")
        self.assertIn(("h5", "e8"), moves)

    def test_rook_move_through_superposition_friendly_is_legal(self):
        """Rook at a1 can move to a7 even when a friendly piece is in superposition at a4."""
        amp = (1 / 2 ** 0.5) + 0j
        basis_blocked = BoardState._board_to_tuple({"a1": "R", "a4": "P", "e1": "K", "e8": "k"})
        basis_clear   = BoardState._board_to_tuple({"a1": "R", "e1": "K", "e8": "k"})

        state = BoardState(amplitudes={
            basis_blocked: amp,
            basis_clear:   amp,
        })

        moves = legal_moves_for(state, "white")
        self.assertIn(("a1", "a7"), moves)


class WouldMoveInBasisTest(unittest.TestCase):
    def test_queen_clear_path_returns_true(self):
        basis = BoardState._board_to_tuple({"h5": "Q"})
        self.assertTrue(_would_move_in_basis(basis, parse_square("h5"), parse_square("e8"), "Q"))

    def test_queen_blocked_path_returns_false(self):
        basis = BoardState._board_to_tuple({"h5": "Q", "g6": "p"})
        self.assertFalse(_would_move_in_basis(basis, parse_square("h5"), parse_square("e8"), "Q"))

    def test_knight_ignores_intermediate_pieces(self):
        # Knight on b1 surrounded by pieces — still can jump to c3
        basis = BoardState._board_to_tuple({"b1": "N", "b2": "P", "c2": "P"})
        self.assertTrue(_would_move_in_basis(basis, parse_square("b1"), parse_square("c3"), "N"))

    def test_friendly_different_piece_at_target_returns_false(self):
        basis = BoardState._board_to_tuple({"a1": "R", "a5": "P"})
        self.assertFalse(_would_move_in_basis(basis, parse_square("a1"), parse_square("a5"), "R"))

    def test_enemy_piece_at_target_returns_true(self):
        # Enemy at target is a capture, not a block — function must return True
        basis = BoardState._board_to_tuple({"a1": "R", "a5": "p"})
        self.assertTrue(_would_move_in_basis(basis, parse_square("a1"), parse_square("a5"), "R"))


class EntanglementTest(unittest.TestCase):
    def test_queen_entangles_with_superposition_pawn(self):
        """Queen moving diagonally through a 50% pawn creates entanglement:
        queen is at destination only in branches where path was clear."""
        amp = (1 / 2 ** 0.5) + 0j
        basis_blocked = BoardState._board_to_tuple({"h5": "Q", "g6": "p", "a1": "K", "a8": "k"})
        basis_clear   = BoardState._board_to_tuple({"h5": "Q", "a1": "K", "a8": "k"})

        game = QuantumGame(
            board_state=BoardState(amplitudes={basis_blocked: amp, basis_clear: amp}),
            side_to_move="white",
        )
        game.apply_classical_move("h5", "e8")

        prob_e8 = game.board_state.probability("e8")
        prob_h5 = game.board_state.probability("h5")
        self.assertAlmostEqual(prob_e8, 0.5, places=5)
        self.assertAlmostEqual(prob_h5, 0.5, places=5)

        # Verify correlated structure: in branches where queen is at e8, g6 must be empty;
        # in branches where queen is at h5, g6 must still have the pawn
        amps = game.board_state.amplitudes
        e8_idx = parse_square("e8")
        h5_idx = parse_square("h5")
        g6_idx = parse_square("g6")
        e8_bases = [b for b in amps if b[e8_idx] == "Q"]
        h5_bases = [b for b in amps if b[h5_idx] == "Q"]
        for b in e8_bases:
            self.assertIsNone(b[g6_idx])
        for b in h5_bases:
            self.assertEqual(b[g6_idx], "p")

    def test_rook_entangles_with_superposition_blocker(self):
        """Rook moving through a 50% superposition piece moves in clear branches only."""
        amp = (1 / 2 ** 0.5) + 0j
        basis_blocked = BoardState._board_to_tuple({"a1": "R", "a4": "P", "e1": "K", "e8": "k"})
        basis_clear   = BoardState._board_to_tuple({"a1": "R", "e1": "K", "e8": "k"})

        game = QuantumGame(
            board_state=BoardState(amplitudes={basis_blocked: amp, basis_clear: amp}),
            side_to_move="white",
        )
        game.apply_classical_move("a1", "a7")

        prob_a7 = game.board_state.probability("a7")
        prob_a1 = game.board_state.probability("a1")
        self.assertAlmostEqual(prob_a7, 0.5, places=5)
        self.assertAlmostEqual(prob_a1, 0.5, places=5)

    def test_non_sliding_piece_moves_in_all_branches(self):
        """A knight's move ignores intermediate squares — it moves in all branches."""
        amp = (1 / 2 ** 0.5) + 0j
        basis_a = BoardState._board_to_tuple({"b1": "N", "c2": "P", "e1": "K", "e8": "k"})
        basis_b = BoardState._board_to_tuple({"b1": "N", "e1": "K", "e8": "k"})

        game = QuantumGame(
            board_state=BoardState(amplitudes={basis_a: amp, basis_b: amp}),
            side_to_move="white",
        )
        game.apply_classical_move("b1", "c3")

        prob_c3 = game.board_state.probability("c3")
        self.assertAlmostEqual(prob_c3, 1.0, places=5)


if __name__ == "__main__":
    unittest.main()
