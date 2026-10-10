"""验证 stale human_obs 修复：模拟人类'能碰就碰/过'的打法，
修复前会在错误阶段提交过期 PASS 被判 chombo（罚符 + ryukyoku + 直接进入下一本场）。
修复后应能正常打完整场，无异常罚符。
"""
import sys

sys.path.insert(0, r"D:\Mahjong AI\apps\mahjong-play\backend")

from game_session import GameSession  # noqa: E402
from mortal_bridge import load_engine  # noqa: E402


def pick_action(legal, step):
    """人类策略：有 tsumo/ron/riichi 必选；能碰就碰；否则交替 pass/鸣牌；兜底舍牌。"""
    names = [l["type_name"] for l in legal]
    for pref in ("tsumo", "ron", "riichi"):
        if pref in names:
            return legal[names.index(pref)]
    if "pon" in names:
        return legal[names.index("pon")]
    if "pass" in names:
        return legal[names.index("pass")]
    if "discard" in names:
        return legal[names.index("discard")]
    return legal[0]


def play(seed):
    engine = load_engine()
    g = GameSession(engine, human_seat=0, seed=seed)
    g.start()
    steps = 0
    anomalies = []
    prev_scores = None
    while not g.env.done():
        st = g.state()
        if prev_scores is not None and st["scores"] != prev_scores:
            diff = [a - b for a, b in zip(st["scores"], prev_scores)]
            # 非庄 mangan 罚符 = [-12000, 4000, 4000, 4000] 的某种轮换
            if sorted(diff) == sorted([-12000, 4000, 4000, 4000]) or sorted(diff) == sorted([-8000, 2000, 2000, 4000]):
                anomalies.append((steps, diff, "chombo penalty pattern"))
        prev_scores = list(st["scores"])
        legal = st["legal_actions"]
        if not legal:
            break
        act = pick_action(legal, steps)
        g.submit_action(act["type_name"], act.get("tile"), act.get("consume_tiles"))
        steps += 1
        if steps > 3000:
            raise RuntimeError("too many steps")
    return steps, g.env.scores(), anomalies


for seed in (7, 123, 999):
    steps, scores, anomalies = play(seed)
    status = "ANOMALY" if anomalies else "OK"
    print(f"seed={seed}: steps={steps} final_scores={scores} anomalies={anomalies} -> {status}")
print("done")
