import math
import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from engine.board_state import BoardState, parse_square
from engine.quantum_ops import _move_piece_in_tuple, merge_move, observe_square, split_move


class QuantumOpsTest(unittest.TestCase):
    def test_move_piece_in_tuple_moves_piece_between_indices(self):
        basis = BoardState._board_to_tuple({"b1": "N"})

        moved = _move_piece_in_tuple(basis, parse_square("b1"), parse_square("c3"))

        self.assertIsNone(moved[parse_square("b1")])
        self.assertEqual(moved[parse_square("c3")], "N")

    def test_split_move_splits_amplitude_between_targets(self):
        state = BoardState(amplitudes={BoardState._board_to_tuple({"b1": "N"}): 1 + 0j})

        new_state = split_move(state, "b1", "a3", "c3")

        self.assertEqual(len(new_state.amplitudes), 2)
        self.assertAlmostEqual(abs(new_state.amplitudes[BoardState._board_to_tuple({"a3": "N"})]) ** 2, 0.5)
        self.assertAlmostEqual(abs(new_state.amplitudes[BoardState._board_to_tuple({"c3": "N"})]) ** 2, 0.5)

    def test_split_move_preserves_basis_without_source_piece(self):
        basis = BoardState._board_to_tuple({"a1": "K"})
        state = BoardState(amplitudes={basis: 1 + 0j})

        new_state = split_move(state, "b1", "a3", "c3")

        self.assertEqual(new_state.amplitudes, {basis: 1 + 0j})

    def test_merge_move_combines_sources_into_target_basis(self):
        amplitude = 1 / math.sqrt(2)
        state = BoardState(
            amplitudes={
                BoardState._board_to_tuple({"a3": "N"}): amplitude + 0j,
                BoardState._board_to_tuple({"c3": "N"}): amplitude + 0j,
            }
        )

        new_state = merge_move(state, "a3", "c3", "b1")

        self.assertEqual(list(new_state.amplitudes.keys()), [BoardState._board_to_tuple({"b1": "N"})])
        self.assertAlmostEqual(abs(next(iter(new_state.amplitudes.values()))) ** 2, 1.0)



class ObserveSquareTest(unittest.TestCase):
    def test_observe_definite_occupied_always_present(self):
        basis = BoardState._board_to_tuple({"e4": "N"})
        state = BoardState(amplitudes={basis: 1 + 0j})
        for _ in range(20):
            is_present, new_state = observe_square(state, "e4")
            self.assertTrue(is_present)
            self.assertAlmostEqual(new_state.probability("e4"), 1.0)

    def test_observe_definite_empty_always_absent(self):
        basis = BoardState._board_to_tuple({})
        state = BoardState(amplitudes={basis: 1 + 0j})
        for _ in range(20):
            is_present, new_state = observe_square(state, "e4")
            self.assertFalse(is_present)

    @patch("engine.quantum_ops.random.choices", return_value=[True])
    def test_observe_superposition_collapses_to_occupied(self, _):
        basis_a = BoardState._board_to_tuple({"e4": "N"})
        basis_b = BoardState._board_to_tuple({})
        amp = 1 / math.sqrt(2)
        state = BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        is_present, new_state = observe_square(state, "e4")
        self.assertTrue(is_present)
        self.assertAlmostEqual(new_state.probability("e4"), 1.0)
        self.assertEqual(len(new_state.amplitudes), 1)

    @patch("engine.quantum_ops.random.choices", return_value=[False])
    def test_observe_superposition_collapses_to_empty(self, _):
        basis_a = BoardState._board_to_tuple({"e4": "N"})
        basis_b = BoardState._board_to_tuple({})
        amp = 1 / math.sqrt(2)
        state = BoardState(amplitudes={basis_a: amp + 0j, basis_b: amp + 0j})
        is_present, new_state = observe_square(state, "e4")
        self.assertFalse(is_present)
        self.assertAlmostEqual(new_state.probability("e4"), 0.0)
        self.assertEqual(len(new_state.amplitudes), 1)


if __name__ == "__main__":
    unittest.main()
