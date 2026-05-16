export type SideToMove = "white" | "black";
export type ActionMode = "classical" | "split" | "merge";
export type GameStatus = "ongoing" | "white_wins" | "black_wins";
export type MoveOutcome = "success" | "capture_failed";

export interface MoveHistoryEntry {
  move_number: number;
  side: SideToMove;
  mode: ActionMode;
  piece: string;
  squares: string[];
  outcome: MoveOutcome | null;
}

export interface GameSnapshot {
  board: Record<string, string | null>;
  probabilities: Record<string, number>;
  side_to_move: SideToMove;
  fullmove_number: number;
  game_status: GameStatus;
  legal_moves: [string, string][];
  last_move_outcome: MoveOutcome | null;
  move_history: MoveHistoryEntry[];
}

export interface ClassicalMovePayload {
  src: string;
  target: string;
}

export interface SplitMovePayload {
  src: string;
  target_a: string;
  target_b: string;
}

export interface MergeMovePayload {
  src_a: string;
  src_b: string;
  target: string;
}
