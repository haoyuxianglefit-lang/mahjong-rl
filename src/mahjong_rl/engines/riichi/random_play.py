#!/usr/bin/env python3
"""Play full games on ``riichienv.RiichiEnv`` with a simple policy and dump MJAI JSONL logs.

Two built-in policies (``--policy``):

- ``random`` (default): uniformly random legal action.  Note that with uniform
  random play (including random chi/pon) players essentially never reach
  tenpai, so games typically end in exhaustive draws — that is expected.
- ``greedy``: shanten-greedy discards, always takes a win, passes calls.
  Produces games with wins / riichi / score movements — much better for
  eyeballing rules in the replay viewer.

Confirmed ``riichienv`` semantics (see README / reports for details):

- ``RiichiEnv(game_mode=GameType.YON_HANCHAN, seed=...)`` plays a full
  hanchan; round transitions and the final ``end_game`` event are produced
  automatically by ``env.step`` — no manual round bookkeeping needed.
- ``env.reset()`` returns ``dict[int, Observation]`` (only players that
  need to act have non-empty ``legal_actions()``).
- ``env.step(actions)`` takes a ``dict[int, Action]`` mapping every player
  who must act to their chosen ``Action``.  It returns the new
  ``dict[int, Observation]``.
- ``env.mjai_log`` is the full omniscient event stream of the current
  game: ``start_game``, one ``start_kyoku`` per round, ``tsumo``/``dahai``/
  ``chi``/``pon``/``daiminkan``/``ankan``/``kakan``/``dora``/``reach``/
  ``reach_accepted``/``hora``/``ryukyoku``/``end_kyoku``, ``end_game``.
- ``hora`` events in ``mjai_log`` do NOT carry yaku / han / fu details;
  this script re-parses the finished log with ``MjaiReplay`` and enriches
  each ``hora`` with ``yaku`` (list of English yaku names), ``han`` and
  ``fu`` (see ``enrich_hora_events``).
- Red fives are rendered in this engine's mjai dialect as ``5mr``/``5pr``/
  ``5sr`` (``0m``-style also appears in mjsoul events).
- Note: with *uniformly* random play (including random chi/pon) players
  essentially never reach tenpai, so games typically end in exhaustive
  draws — that is expected, not a bug.  Use ``--policy greedy`` for games
  with wins.

Usage::

    python src/mahjong_rl/engines/riichi/random_play.py --seed 42 --output data/sample_random.mjai.jsonl
    python src/mahjong_rl/engines/riichi/random_play.py --self-test 20
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
from pathlib import Path
from typing import Any

import riichienv
from riichienv import ActionType, GameType, RiichiEnv, calculate_shanten

# A hanchan is ~1000 decision steps; this is only a runaway guard.
MAX_STEPS = 100_000

GAME_MODES: dict[str, GameType] = {
    "hanchan": GameType.YON_HANCHAN,
    "tonpu": GameType.YON_TONPUSEN,
    "ikkyoku": GameType.YON_IKKYOKU,
}

STARTING_SCORES = [25000, 25000, 25000, 25000]


def enrich_hora_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich ``hora`` events with yaku / han / fu details.

    ``mjai_log`` ``hora`` events only carry score deltas — no yaku names,
    han or fu.  Re-parsing the finished log with ``MjaiReplay`` gives
    ``WinResultContext`` objects (via ``take_win_result_contexts``) with the
    full scoring breakdown.  Within one kyoku a (seat, tsumo) pair identifies
    at most one win, so we can match contexts to hora events reliably.

    Mutates and returns ``events``.  If replay re-parsing fails, the events
    are returned unenriched (deltas remain valid).
    """
    try:
        import tempfile

        from riichienv import MjaiReplay

        with tempfile.NamedTemporaryFile(
            "w", suffix=".mjai.jsonl", delete=False, encoding="utf-8"
        ) as f:
            for ev in events:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
            tmp_path = f.name
        try:
            contexts: dict[tuple[int, bool], Any] = {}
            for kyoku in MjaiReplay.from_jsonl(tmp_path).take_kyokus():
                for ctx in kyoku.take_win_result_contexts():
                    contexts[(ctx.seat, bool(ctx.conditions.tsumo))] = ctx.actual
            for ev in events:
                if ev.get("type") != "hora":
                    continue
                result = contexts.get((ev.get("actor"), bool(ev.get("tsumo"))))
                if result is None or not result.is_win:
                    continue
                ev["yaku"] = [y.name_en for y in result.yaku_list()]
                ev["han"] = result.han
                ev["fu"] = result.fu
        finally:
            os.unlink(tmp_path)
    except Exception as exc:  # pragma: no cover - defensive: deltas stay valid
        print(f"warning: could not enrich hora events: {exc!r}", file=sys.stderr)
    return events


def act_greedy(obs):
    """Shanten-greedy policy: always win; pass calls; discard that minimizes
    shanten of the remaining 13-tile hand.  Reaches tenpai quickly, so games
    contain wins / riichi / score moves — much better for eyeballing rules in
    the replay viewer than uniform random play (which almost always draws).
    """
    la = list(obs.legal_actions())
    for a in la:
        if a.action_type in (ActionType.Tsumo, ActionType.Ron):
            return a
    discards = [a for a in la if a.action_type == ActionType.Discard]
    if discards:
        hand = list(obs.hands[obs.player_id])
        best, best_s = None, 99
        for a in discards:
            removed = False
            rest = []
            for x in hand:
                if not removed and x == a.tile:
                    removed = True
                    continue
                rest.append(x)
            s = calculate_shanten(rest)
            if s < best_s:
                best_s, best = s, a
        return best
    for a in la:
        if a.action_type == ActionType.Pass:
            return a
    return la[0]


def play_game(
    seed: int, game_mode: GameType = GameType.YON_HANCHAN, policy: str = "random"
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Play one full game with uniformly random actions.

    Returns ``(mjai_events, stats)`` where ``mjai_events`` is the full mjai
    event stream and ``stats`` holds basic game statistics.
    """
    env = RiichiEnv(game_mode=game_mode, seed=seed)
    obs = env.reset()
    # Per-player RNG streams: the dict returned by env.step has no stable
    # iteration order, so a single shared RNG would assign choices to
    # players nondeterministically.  Per-player streams make the whole
    # game reproducible from `seed` alone.
    rngs = {p: random.Random(f"{seed}:{p}") for p in range(4)}
    steps = 0

    def choose(obs):
        if policy == "greedy":
            return act_greedy(obs)
        return rngs[obs.player_id].choice(obs.legal_actions())

    while not env.is_done:
        actions: dict[int, Any] = {}
        for player_id, observation in obs.items():
            legal = observation.legal_actions()
            if legal:
                actions[player_id] = choose(observation)
        if not actions:
            raise RuntimeError(
                f"seed={seed}: no player has legal actions but env is not done "
                f"(phase={env.phase}, kyoku={env.kyoku_idx})"
            )
        obs = env.step(actions)
        steps += 1
        if steps > MAX_STEPS:
            raise RuntimeError(f"seed={seed}: exceeded {MAX_STEPS} steps (runaway game)")

    events: list[dict[str, Any]] = enrich_hora_events(list(env.mjai_log))
    final_scores = env.scores()
    stats = collect_stats(events, final_scores)
    stats["steps"] = steps
    return events, stats


def collect_stats(
    events: list[dict[str, Any]], final_scores: list[int]
) -> dict[str, Any]:
    """Aggregate basic statistics from an mjai event stream."""
    num_kyoku = 0
    hora_tsumo = 0
    hora_ron = 0
    ryukyoku_reasons: dict[str, int] = {}
    num_calls = 0
    for ev in events:
        t = ev.get("type")
        if t == "start_kyoku":
            num_kyoku += 1
        elif t == "hora":
            if ev.get("tsumo"):
                hora_tsumo += 1
            else:
                hora_ron += 1
        elif t == "ryukyoku":
            reason = ev.get("reason", "unknown")
            ryukyoku_reasons[reason] = ryukyoku_reasons.get(reason, 0) + 1
        elif t in ("chi", "pon", "daiminkan", "ankan", "kakan"):
            num_calls += 1
    return {
        "num_kyoku": num_kyoku,
        "hora_tsumo": hora_tsumo,
        "hora_ron": hora_ron,
        "ryukyoku": ryukyoku_reasons,
        "num_calls": num_calls,
        "final_scores": list(final_scores),
        "score_deltas": [s - STARTING_SCORES[i] for i, s in enumerate(final_scores)],
    }


def print_stats(stats: dict[str, Any], seed: int) -> None:
    print(f"-- seed {seed} --")
    print(f"  kyoku (hands) played : {stats['num_kyoku']}")
    print(
        f"  wins: tsumo={stats['hora_tsumo']} ron={stats['hora_ron']}  "
        f"draws: {stats['ryukyoku']}  calls: {stats['num_calls']}"
    )
    print(f"  decision steps       : {stats['steps']}")
    print(f"  final scores         : {stats['final_scores']}")
    print(f"  score deltas         : {stats['score_deltas']}")


def write_jsonl(events: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for ev in events:
            f.write(json.dumps(ev, ensure_ascii=False) + "\n")


def self_test(num_seeds: int, game_mode: GameType, policy: str = "random") -> None:
    """Run ``num_seeds`` games and assert basic rule sanity.

    Checks, per seed: the game terminates with an ``end_game`` event, the
    four final scores sum to 100000 (all riichi sticks are returned at the
    end of the game), every event is a dict with a string ``type``, and the
    per-round structure (``start_kyoku`` ... ``end_kyoku``) is consistent.
    """
    for seed in range(num_seeds):
        events, stats = play_game(seed, game_mode, policy)
        types = [ev.get("type") for ev in events]
        assert all(isinstance(ev, dict) for ev in events), f"seed {seed}: non-dict event"
        assert all(isinstance(t, str) for t in types), f"seed {seed}: event without type"
        assert "start_game" in types, f"seed {seed}: missing start_game"
        assert "end_game" in types, f"seed {seed}: game did not finish"
        assert types.count("start_kyoku") == types.count("end_kyoku"), (
            f"seed {seed}: start_kyoku/end_kyoku mismatch"
        )
        total = sum(stats["final_scores"])
        assert total == 100000, f"seed {seed}: score sum {total} != 100000"
        assert stats["num_kyoku"] >= 1, f"seed {seed}: no kyoku played"
        print(f"  seed {seed}: OK "
              f"({stats['num_kyoku']} kyoku, wins={stats['hora_tsumo'] + stats['hora_ron']}, "
              f"draws={sum(stats['ryukyoku'].values())}, sum={total})")
    print(f"SELF-TEST PASSED: {num_seeds} games, all assertions held.")


def main() -> None:
    # Git Bash / Windows consoles: force UTF-8 so Chinese/Japanese text is safe.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(
        description="Play a full riichi mahjong game on RiichiEnv with random actions "
        "and dump the mjai event stream as JSONL.",
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed (default: 42)")
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for the mjai JSONL event stream.",
    )
    parser.add_argument(
        "--game-mode",
        choices=list(GAME_MODES),
        default="hanchan",
        help="Game length: hanchan (default), tonpu (east round only), ikkyoku (single hand).",
    )
    parser.add_argument(
        "--policy",
        choices=["random", "greedy"],
        default="random",
        help="Agent policy: random (default, uniformly random legal action) or "
        "greedy (shanten-greedy discards, always wins, passes calls — produces "
        "games with wins/riichi, better for rule inspection in the viewer).",
    )
    parser.add_argument(
        "--self-test",
        type=int,
        metavar="N",
        default=0,
        help="Run N seeded games with sanity assertions instead of a single game.",
    )
    args = parser.parse_args()
    game_mode = GAME_MODES[args.game_mode]

    if args.self_test > 0:
        print(f"Running self-test with {args.self_test} seeds "
              f"(game mode: {args.game_mode}, policy: {args.policy})...")
        self_test(args.self_test, game_mode, args.policy)
        return

    events, stats = play_game(args.seed, game_mode, args.policy)
    print_stats(stats, args.seed)
    if args.output is not None:
        write_jsonl(events, args.output)
        print(f"Wrote {len(events)} mjai events to {args.output}")


if __name__ == "__main__":
    main()
