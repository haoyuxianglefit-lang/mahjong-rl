"""压力测试 _kyoku_result：整场对局，每次状态都调用，确保不崩且数据合理。"""
import json
import sys

sys.path.insert(0, r"D:\Mahjong AI\apps\mahjong-play\backend")

from game_session import GameSession, ACTION_NAMES, tile_to_mjai  # noqa: E402
from mortal_bridge import load_engine, make_bot  # noqa: E402

engine = load_engine()
n_hora = n_ryu = 0
for seed in (5, 11, 42, 77):
    g = GameSession(engine, human_seat=0, seed=seed)
    human_bot = make_bot(engine, 0)
    g.start()
    steps = 0
    last_result_id = -1
    while not g.env.done() and steps < 1500:
        st = g.state()  # 每次都会算 kyoku_result，崩了会抛异常
        kr = st["kyoku_result"]
        if kr and kr["id"] != last_result_id:
            last_result_id = kr["id"]
            if kr["type"] == "hora":
                n_hora += 1
                for w in kr["wins"]:
                    total = len(w["hand"]) + 3 * len(w["melds"])
                    assert total in (13, 14), f"手牌数异常: hand={len(w['hand'])} melds={len(w['melds'])}"
                    desc = [tile_to_mjai(t) for t in w["hand"]]
                    print(f"seed={seed} {kr['round_wind']}{kr['kyoku_idx']} hora: P{w['actor']} "
                          f"{'tsumo' if w['is_tsumo'] else 'ron'} yaku={[y['name'] for y in w['yaku']]} "
                          f"han={w['han']} fu={w['fu']} pts={w['points']} deltas={kr['deltas']}")
            else:
                n_ryu += 1
                print(f"seed={seed} {kr['round_wind']}{kr['kyoku_idx']} ryukyoku: {kr['ryukyoku_name']} deltas={kr['deltas']}")
        legal = st["legal_actions"]
        if not legal:
            break
        o = g.human_obs
        act = None
        for ev in o.new_events():
            r = human_bot.react(ev)
            if r is None:
                continue
            a = o.select_action_from_mjai(json.loads(r))
            if a is not None:
                act = a.to_dict()
                break
        if act is None:
            names = [l["type_name"] for l in legal]
            act = [l for l in legal if l["type_name"] == "discard"][0] if "discard" in names else legal[0]
        g.submit_action(ACTION_NAMES[act["type"]], act.get("tile"), act.get("consume_tiles"))
        steps += 1
print(f"OK: {n_hora} hora, {n_ryu} ryukyoku across 4 games")
