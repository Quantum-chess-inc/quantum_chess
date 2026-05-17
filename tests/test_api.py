import pathlib
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

from fastapi.testclient import TestClient

from api.app import app
from api.state_store import store


class ApiTest(unittest.TestCase):
    def setUp(self):
        store.reset()
        self.client = TestClient(app)

    def test_get_game_returns_initial_snapshot(self):
        response = self.client.get("/game")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["side_to_move"], "white")
        self.assertEqual(payload["fullmove_number"], 1)
        self.assertEqual(payload["board"]["e1"], "K")
        self.assertEqual(payload["board"]["e8"], "k")
        self.assertEqual(payload["probabilities"]["e1"], 1.0)

    def test_reset_game_restores_initial_state(self):
        self.client.post("/game/move/classical", json={"src": "b1", "target": "c3"})

        response = self.client.post("/game/reset")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["board"]["b1"], "N")
        self.assertIsNone(payload["board"]["c3"])
        self.assertEqual(payload["side_to_move"], "white")

    def test_classical_move_endpoint_updates_state(self):
        response = self.client.post("/game/move/classical", json={"src": "b1", "target": "c3"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIsNone(payload["board"]["b1"])
        self.assertEqual(payload["board"]["c3"], "N")
        self.assertEqual(payload["side_to_move"], "black")

    def test_classical_move_returns_400_on_illegal_move(self):
        response = self.client.post("/game/move/classical", json={"src": "b1", "target": "b4"})

        self.assertEqual(response.status_code, 400)
        self.assertIn("illegal move", response.json()["detail"])

    def test_split_move_endpoint_returns_probabilities(self):
        response = self.client.post(
            "/game/move/split",
            json={"src": "b1", "target_a": "a3", "target_b": "c3"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertAlmostEqual(payload["probabilities"]["a3"], 0.5)
        self.assertAlmostEqual(payload["probabilities"]["c3"], 0.5)
        self.assertEqual(payload["side_to_move"], "black")

    def test_merge_move_endpoint_combines_split_branches(self):
        self.client.post("/game/move/split", json={"src": "b1", "target_a": "a3", "target_b": "c3"})
        # Force white's turn — test-only hack to skip the opponent's move
        store._game.side_to_move = "white"

        response = self.client.post(
            "/game/move/merge",
            json={"src_a": "a3", "src_b": "c3", "target": "b1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["board"]["b1"], "N")
        self.assertAlmostEqual(payload["probabilities"]["b1"], 1.0)

    def test_measure_endpoint_is_removed(self):
        response = self.client.post("/game/measure", json={"target": "d4"})
        self.assertEqual(response.status_code, 404)
        self.assertIn("detail", response.json())
        self.assertNotIn("board", response.json())

    def test_snapshot_includes_expected_fields(self):
        response = self.client.get("/game")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("game_status", payload)
        self.assertEqual(payload["game_status"], "ongoing")
        self.assertIn("last_move_outcome", payload)
        self.assertIsNone(payload["last_move_outcome"])
        self.assertIn("legal_moves", payload)
        self.assertEqual(len(payload["legal_moves"]), 20)
        # Removed fields must not be present
        self.assertNotIn("in_check", payload)
        self.assertNotIn("promotion_pending", payload)
        self.assertNotIn("promotion_square", payload)

    def test_snapshot_legal_moves_update_after_move(self):
        self.client.post("/game/move/classical", json={"src": "b1", "target": "c3"})
        response = self.client.get("/game")
        payload = response.json()
        self.assertEqual(payload["side_to_move"], "black")
        self.assertEqual(len(payload["legal_moves"]), 20)

    def test_pawn_auto_promotes_to_queen_via_api(self):
        from api.state_store import store
        from engine.board_state import BoardState
        from engine.game_state import QuantumGame
        basis = BoardState._board_to_tuple({"e7": "P", "a1": "K", "a8": "k"})
        store._game = QuantumGame(board_state=BoardState(amplitudes={basis: 1 + 0j}))
        response = self.client.post("/game/move/classical", json={"src": "e7", "target": "e8"})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["board"]["e8"], "Q")
        self.assertEqual(payload["last_move_outcome"], "success")
        self.assertEqual(payload["side_to_move"], "black")

    def test_snapshot_includes_move_history_field(self):
        response = self.client.get("/game")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn("move_history", payload)
        self.assertEqual(payload["move_history"], [])

    def test_history_empty_on_start(self):
        response = self.client.get("/game")
        self.assertEqual(response.json()["move_history"], [])

    def test_classical_move_appends_history_entry(self):
        self.client.post("/game/move/classical", json={"src": "b1", "target": "c3"})
        response = self.client.get("/game")
        history = response.json()["move_history"]
        self.assertEqual(len(history), 1)
        entry = history[0]
        self.assertEqual(entry["move_number"], 1)
        self.assertEqual(entry["side"], "white")
        self.assertEqual(entry["mode"], "classical")
        self.assertEqual(entry["piece"], "N")
        self.assertEqual(entry["squares"], ["b1", "c3"])
        self.assertEqual(entry["outcome"], "success")

    def test_split_move_appends_history_entry(self):
        self.client.post(
            "/game/move/split",
            json={"src": "b1", "target_a": "a3", "target_b": "c3"},
        )
        response = self.client.get("/game")
        history = response.json()["move_history"]
        self.assertEqual(len(history), 1)
        entry = history[0]
        self.assertEqual(entry["mode"], "split")
        self.assertEqual(entry["piece"], "N")
        self.assertEqual(entry["squares"], ["b1", "a3", "c3"])
        self.assertIsNone(entry["outcome"])

    def test_reset_clears_history(self):
        self.client.post("/game/move/classical", json={"src": "b1", "target": "c3"})
        self.client.post("/game/reset")
        response = self.client.get("/game")
        self.assertEqual(response.json()["move_history"], [])

    def test_history_included_in_move_response(self):
        response = self.client.post(
            "/game/move/classical", json={"src": "b1", "target": "c3"}
        )
        history = response.json()["move_history"]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["squares"], ["b1", "c3"])

    def test_serve_spa_path_traversal_blocked(self):
        """Path traversal must not leak files outside UI_DIST.

        TestClient normalises bare '../' sequences before they reach the server,
        so we use percent-encoded traversal (%2e%2e%2f) which the ASGI layer
        decodes to '../' and delivers to the route handler verbatim.

        ui/package.json exists one level above ui/dist/ and would be served by
        the vulnerable code (UI_DIST / '../package.json' exists).  With the
        is_relative_to guard the route must fall back to index.html instead.
        We compare response *content* rather than status code because both the
        safe fallback and a vulnerable leak return HTTP 200.
        """
        from api.app import UI_DIST

        response = self.client.get("/%2e%2e%2fpackage.json")
        index_bytes = (UI_DIST / "index.html").read_bytes()
        self.assertEqual(response.content, index_bytes,
                         "Path traversal guard failed: response body must be index.html, "
                         "not the traversed file")

    def test_merge_move_appends_history_entry(self):
        # Set up: split a knight into two squares first
        self.client.post(
            "/game/move/split",
            json={"src": "b1", "target_a": "a3", "target_b": "c3"},
        )
        # Force white's turn — test-only hack to skip the opponent's move
        store._game.side_to_move = "white"

        response = self.client.post(
            "/game/move/merge",
            json={"src_a": "a3", "src_b": "c3", "target": "b1"},
        )
        history = response.json()["move_history"]
        # 2 entries: the split + the merge
        self.assertEqual(len(history), 2)
        merge_entry = history[1]
        self.assertEqual(merge_entry["mode"], "merge")
        self.assertEqual(merge_entry["piece"], "N")
        self.assertEqual(merge_entry["squares"], ["a3", "c3", "b1"])
        self.assertIsNone(merge_entry["outcome"])


    def test_apply_move_returns_independent_snapshot(self):
        """Game object returned by apply_* must be a deep copy, not the live store instance."""
        store.reset()
        game_snap = store.apply_classical_move("e2", "e4")
        # Mutate the internal board state in-place (without replacing the object).
        # If apply_classical_move returned a reference instead of a deep copy,
        # game_snap.board_state would be the same object and this mutation would affect it.
        original_amplitudes = dict(store._game.board_state.amplitudes)
        store._game.board_state.amplitudes.clear()
        # The snapshot must still have its amplitudes intact.
        self.assertNotEqual(game_snap.board_state.amplitudes, {})
        # Restore internal state for other tests.
        store._game.board_state.amplitudes.update(original_amplitudes)


if __name__ == "__main__":
    unittest.main()
