import { render, screen } from "@testing-library/react";
import { MoveHistory } from "./MoveHistory";
import type { GameSnapshot } from "../api/types";

const baseSnapshot: GameSnapshot = {
  board: {},
  probabilities: {},
  side_to_move: "white",
  fullmove_number: 1,
  game_status: "ongoing",
  legal_moves: [],
  last_move_outcome: null,
  move_history: [],
};

describe("MoveHistory", () => {
  it("shows empty state when no moves", () => {
    render(<MoveHistory snapshot={baseSnapshot} />);
    expect(screen.getByText("no moves yet")).toBeInTheDocument();
  });

  it("renders a classical move entry", () => {
    const snapshot = {
      ...baseSnapshot,
      move_history: [
        {
          move_number: 1,
          side: "white" as const,
          mode: "classical" as const,
          piece: "N",
          squares: ["b1", "c3"],
          outcome: "success" as const,
        },
      ],
    };
    render(<MoveHistory snapshot={snapshot} />);
    expect(screen.getByText("b1→c3")).toBeInTheDocument();
    expect(screen.getByText("♘")).toBeInTheDocument();
    expect(screen.getByText("✓")).toBeInTheDocument();
  });

  it("renders a split move entry", () => {
    const snapshot = {
      ...baseSnapshot,
      move_history: [
        {
          move_number: 1,
          side: "white" as const,
          mode: "split" as const,
          piece: "N",
          squares: ["b1", "a3", "c3"],
          outcome: null,
        },
      ],
    };
    render(<MoveHistory snapshot={snapshot} />);
    expect(screen.getByText("b1→a3/c3")).toBeInTheDocument();
  });

  it("renders a merge move entry", () => {
    const snapshot = {
      ...baseSnapshot,
      move_history: [
        {
          move_number: 1,
          side: "white" as const,
          mode: "merge" as const,
          piece: "N",
          squares: ["a3", "c3", "b1"],
          outcome: null,
        },
      ],
    };
    render(<MoveHistory snapshot={snapshot} />);
    expect(screen.getByText("a3+c3→b1")).toBeInTheDocument();
  });

  it("renders capture_failed outcome", () => {
    const snapshot = {
      ...baseSnapshot,
      move_history: [
        {
          move_number: 1,
          side: "white" as const,
          mode: "classical" as const,
          piece: "P",
          squares: ["e4", "d5"],
          outcome: "capture_failed" as const,
        },
      ],
    };
    render(<MoveHistory snapshot={snapshot} />);
    expect(screen.getByText("⚛ Negative observation")).toBeInTheDocument();
  });

  it("handles null snapshot gracefully", () => {
    render(<MoveHistory snapshot={null} />);
    expect(screen.getByText("no moves yet")).toBeInTheDocument();
  });
});
