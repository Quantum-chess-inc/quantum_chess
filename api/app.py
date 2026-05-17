from pathlib import Path
import sys
from typing import NoReturn

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
UI_DIST = ROOT / "ui" / "dist"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from api.schemas import (
    ClassicalMoveRequest,
    GameSnapshot,
    MergeMoveRequest,
    SplitMoveRequest,
)
from api.state_store import snapshot_game, store

app = FastAPI(title="Quantum Chess API")


def _handle_engine_error(exc: ValueError) -> NoReturn:
    raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/game", response_model=GameSnapshot)
def get_game() -> GameSnapshot:
    game, history = store.get_snapshot_data()
    return snapshot_game(game, history, legal_moves=store.get_legal_moves())


@app.post("/game/reset", response_model=GameSnapshot)
def reset_game() -> GameSnapshot:
    game = store.reset()
    return snapshot_game(game, [], legal_moves=store.get_legal_moves())


@app.post("/game/move/classical", response_model=GameSnapshot)
def apply_classical_move(payload: ClassicalMoveRequest) -> GameSnapshot:
    try:
        game = store.apply_classical_move(payload.src, payload.target)
        return snapshot_game(game, store.get_history(), legal_moves=store.get_legal_moves())
    except ValueError as exc:
        _handle_engine_error(exc)


@app.post("/game/move/split", response_model=GameSnapshot)
def apply_split_move(payload: SplitMoveRequest) -> GameSnapshot:
    try:
        game = store.apply_split_move(payload.src, payload.target_a, payload.target_b)
        return snapshot_game(game, store.get_history(), legal_moves=store.get_legal_moves())
    except ValueError as exc:
        _handle_engine_error(exc)


@app.post("/game/move/merge", response_model=GameSnapshot)
def apply_merge_move(payload: MergeMoveRequest) -> GameSnapshot:
    try:
        game = store.apply_merge_move(payload.src_a, payload.src_b, payload.target)
        return snapshot_game(game, store.get_history(), legal_moves=store.get_legal_moves())
    except ValueError as exc:
        _handle_engine_error(exc)


if UI_DIST.exists():
    assets_dir = UI_DIST / "assets"
    if assets_dir.exists():
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


@app.get("/")
def serve_index():
    if not UI_DIST.exists():
        raise HTTPException(status_code=404, detail="UI bundle not found")
    return FileResponse(UI_DIST / "index.html")


@app.post("/{path:path}")
def reject_unknown_post(path: str):
    raise HTTPException(status_code=404, detail="Not found")


@app.get("/{path:path}")
def serve_spa(path: str):
    if path.startswith("game"):
        raise HTTPException(status_code=404, detail="Not found")
    if not UI_DIST.exists():
        raise HTTPException(status_code=404, detail="UI bundle not found")

    target = (UI_DIST / path).resolve()
    if path and target.is_relative_to(UI_DIST.resolve()) and target.exists() and target.is_file():
        return FileResponse(target)

    return FileResponse(UI_DIST / "index.html")
