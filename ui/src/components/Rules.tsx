export function Rules() {
  return (
    <div className="rules-content">
      <h2 className="rules-heading">How to play Quantum Chess</h2>

      <section className="rules-section">
        <h3 className="rules-subheading">Core idea</h3>
        <p>Quantum chess is played on a standard 8×8 board. White always moves first, then players alternate turns. All standard chess piece movements apply.</p>
        <p>Unlike classical chess, a piece may occupy multiple squares at once — it is said to be in <strong>superposition</strong>. Each square a piece occupies has a probability associated with it, representing the chance the piece is actually there. All pieces start at 100% probability in their normal positions.</p>
        <p>Pieces at 100% probability behave exactly like classical chess pieces — they fully block movement for all non-jumping pieces (everyone except knights). Only pieces in superposition (below 100%) can be passed through, and doing so creates <strong>entanglement</strong>.</p>
        <p>On the board, pieces in superposition appear semi-transparent. The <span className="rules-cyan">cyan</span> glow intensity reflects the probability — brighter means higher chance of being there.</p>
      </section>

      <section className="rules-section">
        <h3 className="rules-subheading">Move types</h3>
        <p><strong>Classical move</strong>: a normal chess move. The piece moves to an empty square or captures an opponent's piece. When moving to a square occupied by your own copy of the same piece, the copies merge (see below).</p>
        <p><strong>Split move</strong>: one piece moves to two legal, non-capturing target squares simultaneously. Both targets must be empty. The piece splits into two copies, each receiving half the original probability. Any piece can split, including pawns — but pawns can only split from their starting position (where they have both a one-square and two-square advance available).</p>
        <p><strong>Merge move</strong>: two copies of the same piece move to a single common legal target square. The target must be empty — this is not a capturing move. The resulting piece's probability equals the sum of both copies' probabilities. Note: only copies of the <em>same original piece</em> can merge — two different knights of the same colour cannot merge with each other.</p>
        <p>To select moves in the interface: in <strong>Classical</strong> mode, click a piece then a target (2 clicks). In <strong>Split</strong> mode, click a piece then two targets (3 clicks). In <strong>Merge</strong> mode, click two source copies then one target (3 clicks). Press <strong>Execute</strong> to confirm, <strong>✕</strong> to clear the selection, or <strong>Reset</strong> to start a new game.</p>
      </section>

      <section className="rules-section">
        <h3 className="rules-subheading">Captures and observation</h3>
        <p>To capture, a piece must actually be on the square it is moving from. When the capturing piece is in superposition, an <strong>observation</strong> is performed: the game randomly determines whether the piece is in that square, weighted by its probability there.</p>
        <p>If the observation is <strong>positive</strong> (the piece is there), the capture proceeds. The capturing piece collapses to 100% on the target square — all its other copies are removed. The captured piece's copy on the target square is removed, but any other copies it has elsewhere on the board remain (their probabilities may now sum to less than 100%, which means it is uncertain whether the piece still exists at all).</p>
        <p>If the observation is <strong>negative</strong> (the piece is not there), the move fails and the turn passes to the opponent. The copy on the starting square is removed, and the probabilities of the piece's remaining copies are re-adjusted to sum correctly.</p>
        <p><strong>Pawn captures are special</strong>: because a pawn's diagonal move is only legal when actually capturing, both the pawn and the target piece are observed. The capture only proceeds if both observations are positive. If either observation is negative, the move fails — but only the piece whose observation was negative collapses. If the pawn's observation was negative, the target is untouched. If the pawn's was positive but the target's was negative, the pawn stays in place but the target collapses to its other copies. The same double-observation rule applies to en passant.</p>
      </section>

      <section className="rules-section">
        <h3 className="rules-subheading">Entanglement</h3>
        <p>When a piece moves along a path through a square occupied by another piece in superposition, it can only complete the move if that piece is <em>not</em> actually there. The moving piece therefore splits: one copy moves through (with probability equal to the chance the path was clear), the other stays behind (with the remaining probability). The two resulting pieces are now <strong>entangled</strong> with the blocking piece: if the blocking piece is later observed, whichever observation outcome occurs will also determine which copy of the moving piece survives.</p>
        <p>When a path crosses multiple pieces in superposition, the probabilities multiply. For example, moving through a 50% piece and then a 50% piece gives the moving copy a 25% chance (50% × 50%). Each blocking piece independently entangles with the moving piece.</p>
        <p>Pieces can be entangled with many other pieces at once. A single observation can therefore trigger a cascade of collapses across the board. This can cause seemingly possible moves to be illegal — for instance, if both copies of a split pawn are somewhere along a rook's path, no observation could ever clear the way, so the rook simply cannot move through.</p>
        <p>Entanglements are preserved through merging. When two copies of a piece merge (either via a merge move or a regular move onto a copy's square), the resulting piece carries forward all entanglements of both copies independently.</p>
      </section>

      <section className="rules-section">
        <h3 className="rules-subheading">Win condition and draws</h3>
        <p>There is no check or checkmate. The game ends when one side has no king copies left on the board — meaning the total probability of that player's king across all squares has reached 0%. Kings do not have to move out of attacked squares.</p>
        <p>If both kings are eliminated simultaneously (by a single move that collapses both to zero), the game is a draw.</p>
        <p>Other draw conditions from classical chess also apply: <strong>stalemate</strong> (a player has no legal moves on their turn), the <strong>50-move rule</strong> (50 consecutive moves by both sides with no pawn move and no capture), and <strong>threefold repetition</strong> (the same board state occurs three times). Because superposition greatly expands possible board states, draws by repetition are very rare — but stalemate and the 50-move rule apply exactly as in classical chess.</p>
      </section>

      <section className="rules-section">
        <h3 className="rules-subheading">Castling</h3>
        <p>Castling is allowed for both sides under the same conditions as classical chess — neither the king nor the relevant rook may have moved previously. Because there is no check concept, a king under attack may still castle. Castling can also be one leg of a split move, as long as the two resulting positions do not conflict (e.g. the king cannot split into two squares that would require the same rook to be in two places).</p>
      </section>

      <section className="rules-section">
        <h3 className="rules-subheading">Promotion</h3>
        <p>Pawns promote automatically to queens on the back rank. A promoted queen keeps all entanglements the pawn had — if a piece the pawn was entangled with is later observed, the queen can still be removed as a consequence. However, the queen cannot merge with pawn-copies of the same original piece that have not yet promoted: once a pawn promotes it is a queen, not a pawn sibling. If both copies of a split pawn promote, those two queens can merge with each other, as they are still copies of the same original piece.</p>
        <p>Split moves to the promotion rank are not allowed.</p>
      </section>
    </div>
  );
}
