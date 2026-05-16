import type { ActionMode, GameSnapshot, MoveHistoryEntry, MoveOutcome } from "../api/types";

const PIECE_SYMBOLS: Record<string, string> = {
  P: "♙", N: "♘", B: "♗", R: "♖", Q: "♕", K: "♔",
  p: "♟", n: "♞", b: "♝", r: "♜", q: "♛", k: "♚",
};

function formatNotation(mode: ActionMode, squares: string[]): string {
  if (mode === "split") return `${squares[0]}→${squares[1]}/${squares[2]}`;
  if (mode === "merge") return `${squares[0]}+${squares[1]}→${squares[2]}`;
  return `${squares[0]}→${squares[1]}`;
}

function OutcomeTag({ outcome }: { outcome: MoveOutcome | null }) {
  if (outcome === "success") return <span className="move-outcome-ok">✓</span>;
  if (outcome === "capture_failed") return <span className="move-outcome-fail">✗</span>;
  return null;
}

function MoveRow({ entry }: { entry: MoveHistoryEntry }) {
  return (
    <div className="move-row">
      <span className={`side-pip side-pip-${entry.side}`} />
      <span className="move-piece">{PIECE_SYMBOLS[entry.piece] ?? entry.piece}</span>
      <span className="move-notation">{formatNotation(entry.mode, entry.squares)}</span>
      <OutcomeTag outcome={entry.outcome} />
    </div>
  );
}

interface MoveHistoryProps {
  snapshot: GameSnapshot | null;
}

export function MoveHistory({ snapshot }: MoveHistoryProps) {
  const history = snapshot?.move_history ?? [];

  return (
    <section className="panel">
      <p className="panel-title">Moves</p>
      {history.length === 0 ? (
        <p className="moves-empty">no moves yet</p>
      ) : (
        <div className="moves-list">
          {history.map((entry, i) => (
            <MoveRow key={i} entry={entry} />
          ))}
        </div>
      )}
    </section>
  );
}
