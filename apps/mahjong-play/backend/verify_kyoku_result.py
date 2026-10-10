"""验证小局结算数据：打完第一小局后检查 kyoku_result 内容。"""
import json
import sys

sys.path.insert(0, r"D:\Mahjong AI\apps\mahjong-play\backend")

from game_session import GameSession, ACTION_NAMES, tile_to_mjai  # noqa: E402
from mortal_bridge import load_engine, make_bot  # noqa: E402

engine = load_engine()
g = GameSession(engine, human_seat=0, seed=5)
human_bot = make_bot(engine, 0)
g.start()

steps = 0
while not g.env.done() and steps < 1500:
    st = g.state()
    if st["kyoku_result"] is not None:
        print(json.dumps(st["kyoku_result"], ensure_ascii=False, indent=1, default=str))
        # 校验手牌渲染可读
        for w in st["kyoku_result"]["wins"]:
            print("winner hand:", [tile_to_mjai(t) for t in w["hand"]],
                  "| win_tile:", tile_to_mjai(w["win_tile"]) if w["win_tile"] is not None else None,
                  "| melds:", [[tile_to_mjai(t) for t in m["tiles"]] for m in w["melds"]])
        break
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
else:
    print("no kyoku result / done:", g.env.done(), "steps:", steps)
