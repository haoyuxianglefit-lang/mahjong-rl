"""端到端验证人类立直链路：
用 Mortal bot 驾驶人类座位，直到 bot 想立直；
通过 GameSession.submit_action('riichi', None) 宣言（模拟前端修后的行为），
再提交宣言牌舍牌，验证 reach_accepted、1000 点扣除、riichi_declared。
"""
import json
import sys

sys.path.insert(0, r"D:\Mahjong AI\apps\mahjong-play\backend")

from game_session import GameSession, ACTION_NAMES  # noqa: E402
from mortal_bridge import load_engine, make_bot  # noqa: E402

engine = load_engine()

for seed in range(20):
    g = GameSession(engine, human_seat=0, seed=seed)
    human_bot = make_bot(engine, 0)
    g.start()
    steps = 0
    riichi_tested = False
    while not g.env.done() and steps < 1000:
        st = g.state()
        legal = st["legal_actions"]
        if not legal:
            break
        names = [l["type_name"] for l in legal]
        if "riichi" in names:
            # 宣言立直：tile 必须为 None
            scores_before = list(st["scores"])
            g.submit_action("riichi", None, [])
            st2 = g.state()
            legal2 = st2["legal_actions"]
            disc = [l for l in legal2 if l["type_name"] == "discard"]
            print(f"seed={seed}: riichi declared. next legal = {sorted(set(l['type_name'] for l in legal2))}, "
                  f"discard choices = {len(disc)}")
            assert disc, "riichi 宣言后应轮到人类舍牌"
            # 打出第一张宣言牌
            g.submit_action("discard", disc[0]["tile"], disc[0].get("consume_tiles"))
            st3 = g.state()
            log = g.env.mjai_log
            n_acc = sum(1 for ev in log if ev.get("type") == "reach_accepted" and ev.get("actor") == 0)
            print(f"  after dahai: reach_accepted={n_acc}, riichi_declared={st3['riichi_declared']}, "
                  f"scores {scores_before} -> {st3['scores']}")
            assert st3["riichi_declared"][0], "立直应成立"
            assert scores_before[0] - st3["scores"][0] == 1000, "应扣 1000 点棒"
            riichi_tested = True
            break
        # 用 Mortal bot 的决策推进（通过 obs 事件流）
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
            act = [l for l in legal if l["type_name"] == "discard"][0] if "discard" in names else legal[0]
        g.submit_action(ACTION_NAMES[act["type"]], act.get("tile"), act.get("consume_tiles"))
        steps += 1
    if riichi_tested:
        print("RIICHI E2E OK")
        break
else:
    print("20 个种子里 Mortal 没有想立直的时机（不太可能）")
