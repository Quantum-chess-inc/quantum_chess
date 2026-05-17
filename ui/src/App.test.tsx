import { fireEvent, render, screen, waitFor } from "@testing-library/react";

import App, { computeFailedSquare } from "./App";

const initialBoard = {
  a1: "R", b1: "N", c1: "B", d1: "Q", e1: "K", f1: "B", g1: "N", h1: "R",
  a2: "P", b2: "P", c2: "P", d2: "P", e2: "P", f2: "P", g2: "P", h2: "P",
  a3: null, b3: null, c3: null, d3: null, e3: null, f3: null, g3: null, h3: null,
  a4: null, b4: null, c4: null, d4: null, e4: null, f4: null, g4: null, h4: null,
  a5: null, b5: null, c5: null, d5: null, e5: null, f5: null, g5: null, h5: null,
  a6: null, b6: null, c6: null, d6: null, e6: null, f6: null, g6: null, h6: null,
  a7: "p", b7: "p", c7: "p", d7: "p", e7: "p", f7: "p", g7: "p", h7: "p",
  a8: "r", b8: "n", c8: "b", d8: "q", e8: "k", f8: "b", g8: "n", h8: "r",
};

const initialSnapshot = {
  board: initialBoard,
  probabilities: Object.fromEntries(
    "abcdefgh".split("").flatMap((file) =>
      Array.from({ length: 8 }, (_, rankIndex) => {
        const square = `${file}${rankIndex + 1}` as keyof typeof initialBoard;
        return [square, initialBoard[square] ? 1 : 0];
      }),
    ),
  ),
  side_to_move: "white",
  fullmove_number: 1,
  game_status: "ongoing",
  legal_moves: [["b1", "c3"], ["b1", "a3"], ["b1", "b4"]] as [string, string][],
  last_move_outcome: null,
  move_history: [],
};

describe("computeFailedSquare", () => {
  it("returns null when outcome is not capture_failed", () => {
    expect(computeFailedSquare({ outcome: "success", squares: ["e5", "d6"], piece: "P", side: "white", mode: "classical", move_number: 1 })).toBeNull();
  });

  it("returns null for null entry", () => {
    expect(computeFailedSquare(null)).toBeNull();
  });

  it("returns the landing square for a non-pawn piece failed capture", () => {
    expect(computeFailedSquare({ outcome: "capture_failed", squares: ["e4", "d6"], piece: "N", side: "white", mode: "classical", move_number: 1 })).toBe("d6");
  });

  it("returns the captured pawn square for a white pawn en passant on rank 6", () => {
    // White pawn lands on f6 — captured pawn was at f5
    expect(computeFailedSquare({ outcome: "capture_failed", squares: ["e5", "f6"], piece: "P", side: "white", mode: "classical", move_number: 1 })).toBe("f5");
  });

  it("returns the captured pawn square for a black pawn en passant on rank 3", () => {
    // Black pawn lands on f3 — captured pawn was at f4
    expect(computeFailedSquare({ outcome: "capture_failed", squares: ["e4", "f3"], piece: "p", side: "black", mode: "classical", move_number: 1 })).toBe("f4");
  });

  it("returns the landing square for a pawn capture on a non-en-passant rank", () => {
    // White pawn on rank 5 takes diagonally — not en passant, return landing square directly
    expect(computeFailedSquare({ outcome: "capture_failed", squares: ["e4", "f5"], piece: "P", side: "white", mode: "classical", move_number: 1 })).toBe("f5");
  });
});

describe("App", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the board from the API snapshot", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify(initialSnapshot), { status: 200 }),
    );

    render(<App />);

    await screen.findByText("white to move");
    expect(screen.getAllByRole("button", { name: /Square / })).toHaveLength(64);
    expect(screen.getByRole("button", { name: "Square e1" })).toHaveTextContent("♔");
  });

  it("tracks selected squares in the action panel", async () => {
    vi.spyOn(window, "fetch").mockResolvedValue(
      new Response(JSON.stringify(initialSnapshot), { status: 200 }),
    );

    render(<App />);

    await screen.findByText("white to move");
    fireEvent.click(screen.getByRole("button", { name: "Square b1" }));
    fireEvent.click(screen.getByRole("button", { name: "Square c3" }));

    expect(screen.getByText(/b1/)).toBeInTheDocument();
    expect(screen.getByText(/c3/)).toBeInTheDocument();
  });

  it("submits a classical move and updates the board", async () => {
    const movedSnapshot = {
      ...initialSnapshot,
      board: { ...initialSnapshot.board, b1: null, c3: "N" },
      probabilities: { ...initialSnapshot.probabilities, b1: 0, c3: 1 },
      side_to_move: "black",
      legal_moves: [] as [string, string][],
    };

    const fetchMock = vi
      .spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(initialSnapshot), { status: 200 }))
      .mockResolvedValueOnce(new Response(JSON.stringify(movedSnapshot), { status: 200 }));

    render(<App />);

    await screen.findByText("white to move");
    fireEvent.click(screen.getByRole("button", { name: "Square b1" }));
    fireEvent.click(screen.getByRole("button", { name: "Square c3" }));
    fireEvent.click(screen.getByRole("button", { name: "Execute" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Square c3" })).toHaveTextContent("♘"));
    expect(fetchMock).toHaveBeenLastCalledWith(
      "/game/move/classical",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ src: "b1", target: "c3" }) }),
    );
  });

  it("shows API errors to the user", async () => {
    vi.spyOn(window, "fetch")
      .mockResolvedValueOnce(new Response(JSON.stringify(initialSnapshot), { status: 200 }))
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "illegal move for N from b1 to b4" }), { status: 400 }),
      );

    render(<App />);

    await screen.findByText("white to move");
    fireEvent.click(screen.getByRole("button", { name: "Square b1" }));
    fireEvent.click(screen.getByRole("button", { name: "Square b4" }));
    fireEvent.click(screen.getByRole("button", { name: "Execute" }));

    await screen.findByRole("alert");
    expect(screen.getByRole("alert")).toHaveTextContent("illegal move for N from b1 to b4");
  });
});
