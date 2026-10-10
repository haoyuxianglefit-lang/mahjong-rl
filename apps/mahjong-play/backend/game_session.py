"""对局会话：riichienv（天凤规则）驱动牌局，Mortal mjai.Bot 驱动 AI 座位。

核心循环（桥接协议）：
    env.reset() / env.step(actions) -> dict[座位, Observation]
    Observation.new_events()      -> 该座位新增的 mjai 事件 JSON 列表
    bot.react(event_json)         -> AI 的 mjai 动作 JSON 或 None
    obs.select_action_from_mjai() -> 转回 riichienv Action
人类座位不挂 bot：轮到人类时把 legal_actions 暴露给前端，等待提交。

线程安全：所有公共方法都在 self.lock 内执行（模型推理在 GIL 下天然串行，
这里的锁主要保护对局状态机不被并发请求打乱）。
"""
import json
import threading
import time
import uuid

from riichienv import RiichiEnv, GameRule, Action, ActionType

from mortal_bridge import make_bot, ProbeEngine

# riichienv ActionType 整数值 <-> 名字（与 _riichienv.pyi 一致）
ACTION_NAMES = {
    0: "discard",
    1: "chi",
    2: "pon",
    3: "daiminkan",
    4: "ron",
    5: "riichi",
    6: "tsumo",
    7: "pass",
    8: "ankan",
    9: "kakan",
    10: "kyushu_kyuhai",
    11: "kita",
}

# 天凤/mjai 牌面编码：tile_id // 4 -> 0-8=1m~9m, 9-17=1p~9p, 18-26=1s~9s,
# 27-33=东南西北白发中；赤五为特殊 id：16=0m(赤5m), 52=0p, 88=0s。
RED_FIVES = {16: "5mr", 52: "5pr", 88: "5sr"}

# Mortal 动作空间索引含义（libriichi consts.rs: ACTION_SPACE=46）。
# 注意 mask 用的是带赤五的原始索引：34/35/36 = 赤5m/赤5p/赤5s（仍属于"切牌"）。
TILE_NAMES = [f"{n}{s}" for s in "mps" for n in range(1, 10)] + ["东", "南", "西", "北", "白", "发", "中"]
AKA_TILES = {34: ("赤5m", 16), 35: ("赤5p", 52), 36: ("赤5s", 88)}  # 索引 -> (名称, 展示 tile id)

# 动作空间 34 及以上索引的含义（libriichi consts.rs: ACTION_SPACE=46）
META_ACTIONS = {
    37: ("立直", "riichi", None),
    38: ("吃(下)", "chi", None),
    39: ("吃(中)", "chi", None),
    40: ("吃上", "chi", None),
    41: ("碰", "pon", None),
    42: ("杠", "kan", None),
    43: ("和了", "agari", None),
    44: ("九种九牌", "ryukyoku", None),
    45: ("过", "pass", None),
}

# riichienv MeldType 整数值：0=chi 1=pon 2=daiminkan 3=ankan 4=kakan
MELD_NAMES = {0: "chi", 1: "pon", 2: "daiminkan", 3: "ankan", 4: "kakan"}

# 流局原因 -> 中文名（riichienv 的 reason 字段）
RYUKYOKU_NAMES = {
    "exhaustive_draw": "荒牌流局",
    "kyushu_kyuhai": "九种九牌",
    "suufon_renda": "四风连打",
    "sancha_ron": "三家和了",
    "suukaikan": "四杠散了",
    "suucha_riichi": "四家立直",
    "nagashi_mangan": "流局满贯",
}


def tile_from_mjai(s: str) -> int:
    """mjai 字符串 -> 展示用 tile id（同种牌取固定副本即可，渲染相同）。"""
    if s in ("5mr", "5pr", "5sr"):
        return {"5mr": 16, "5pr": 52, "5sr": 88}[s]
    honors = {"E": 27, "S": 28, "W": 29, "N": 30, "P": 31, "F": 32, "C": 33}
    if s in honors:
        return honors[s] * 4
    n, suit = int(s[0]), s[1]
    kind = "mps".index(suit) * 9 + (n - 1)
    # 普通五避开赤五 id（16/52/88），取副本 1
    return kind * 4 + (1 if n == 5 else 0)


def meld_to_dict(m) -> dict:
    return {
        "type": int(m.meld_type),
        "type_name": MELD_NAMES.get(int(m.meld_type), "unknown"),
        "tiles": list(m.tiles),
        "opened": bool(m.opened),
        "from_who": m.from_who,
    }


def tile_to_mjai(tile_id: int) -> str:
    """把 riichienv 的 tile int 转成 mjai 字符串，如 16->'5mr', 0->'1m'。"""
    if tile_id in RED_FIVES:
        return RED_FIVES[tile_id]
    kind = tile_id // 4
    if kind < 27:
        suit = "mps"[kind // 9]
        return f"{kind % 9 + 1}{suit}"
    return ["E", "S", "W", "N", "P", "F", "C"][kind - 27]


class GameSession:
    def __init__(self, engine, human_seat: int = 0, seed: int | None = None):
        assert 0 <= human_seat <= 3
        self.gid = uuid.uuid4().hex[:12]
        self.env = RiichiEnv(game_mode=2, rule=GameRule.default_tenhou(), seed=seed)
        self.human_seat = human_seat
        self.bots = {s: make_bot(engine, s) for s in range(4) if s != human_seat}
        # 影子 bot：与人类座位同步喂事件，只用于提取模型 Q 值做建议，不驱动对局
        self.probe_engine = ProbeEngine(engine)
        self.probe_bot = make_bot(self.probe_engine, human_seat)
        self.human_obs = None
        self.held_actions = {}  # 人类思考期间 AI 已决定的争碰/和牌动作
        self.created_at = time.time()
        self.lock = threading.Lock()
        self.error = None

    # ---------------- 内部驱动 ----------------

    def _ai_react(self, seat: int, obs):
        bot = self.bots[seat]
        for ev in obs.new_events():
            act_json = bot.react(ev)
            if act_json is None:
                continue
            try:
                act = obs.select_action_from_mjai(json.loads(act_json))
            except Exception:
                act = None
            if act is not None:
                return act
        return None

    def _run(self, obs):
        """推进对局，直到轮到人类或终局。AI 在人类思考期间的暂缓动作存入 held_actions。"""
        guard = 0
        while not self.env.done():
            guard += 1
            if guard > 20000:
                raise RuntimeError("game loop guard tripped")
            pending = {}
            human_needs = False
            human_seen = False
            for pid, o in obs.items():
                if pid == self.human_seat:
                    human_seen = True
                    if o is None:
                        continue
                    for ev in o.new_events():
                        self.probe_bot.react(ev)
                    self.human_obs = o
                    if o.legal_actions():
                        human_needs = True
                    continue
                if o is None:
                    continue
                act = self._ai_react(pid, o)
                if act is not None:
                    pending[pid] = act
            if not human_seen:
                # 人类座位在本轮没有任何新事件 => 之前的决策点必然已失效。
                # 必须清掉，否则前端会拿到过期的 legal_actions（比如上一局结束前的
                # 碰/过按钮），提交后会在错误阶段被判犯规（chombo）直接结束本局。
                self.human_obs = None
            elif self.human_obs is not None and not self.human_obs.legal_actions():
                self.human_obs = None
            if human_needs:
                self.held_actions = pending
                return
            if not pending:
                # 无人可行动，理论不应发生；防止死循环
                return
            obs = self.env.step(pending)
        self.human_obs = None
        self.held_actions = {}

    # ---------------- 公共接口 ----------------

    def start(self):
        with self.lock:
            self._run(self.env.reset())

    def submit_action(self, type_name: str, tile: int | None = None, consume_tiles=None):
        with self.lock:
            if self.env.done():
                raise RuntimeError("game is already finished")
            if self.human_obs is None or not self.human_obs.legal_actions():
                raise RuntimeError("not waiting for human action")

            at = getattr(ActionType, type_name.upper(), None)
            if at is None:
                raise ValueError(f"unknown action type: {type_name}")
            # 注意：tile 必须原样传 None。传 0 会让 PASS/RON 等无牌动作携带
            # tile=0（即 1m），riichienv 会判为 Illegal Action（chombo）。
            act = Action(at, tile, consume_tiles or [])

            mine = act.to_dict()
            norm = lambda d: (d["type"], d.get("tile") or 0, tuple(sorted(d.get("consume_tiles") or [])))
            legal = {norm(l.to_dict()) for l in self.human_obs.legal_actions()}
            if norm(mine) not in legal:
                raise ValueError(f"illegal action: {mine}")

            actions = {**self.held_actions, self.human_seat: act}
            self.held_actions = {}
            self._run(self.env.step(actions))

    # ---------------- AI 建议（影子 bot 的 Q 值） ----------------

    def _suggestions(self):
        """当前决策点 Mortal 的 top-5 建议（按 Q 值降序）。

        返回 None 表示无可用建议；否则返回 {
            "kan_select": bool,     # 是否为杠牌选择窗口
            "candidates": [{action_index, label, tile, kind, q, pi, gap}]
        }。pi 为仅在合法动作上做 softmax(Q/T=1) 得到的"策略概率"。
        """
        if self.human_obs is None or not self.human_obs.legal_actions():
            return None
        q, mask = self.probe_engine.last_q, self.probe_engine.last_mask
        if not q or not mask:
            return None

        legal_types = {ACTION_NAMES.get(int(l.to_dict()["type"]), "unknown")
                       for l in self.human_obs.legal_actions()}
        # 杠牌选择窗口：引擎把 0-33 索引复用为"杠哪张牌"
        kan_select = bool("discard" not in legal_types
                          and legal_types & {"ankan", "kakan", "daiminkan"})

        cands = [(i, qv) for i, (qv, m) in enumerate(zip(q, mask)) if m]
        if not cands:
            return None
        q_max = max(qv for _, qv in cands)
        exps = [(i, qv, pow(2.718281828, qv - q_max)) for i, qv in cands]  # 数值稳定的 softmax
        z = sum(e for _, _, e in exps) or 1.0
        exps.sort(key=lambda t: t[1], reverse=True)

        items = []
        for rank, (idx, qv, e) in enumerate(exps[:5]):
            if idx in AKA_TILES:
                name, tile = AKA_TILES[idx]
                label = f"杠 {name}" if kan_select else f"切 {name}"
                kind = "kan_select" if kan_select else "discard"
            elif idx < 34:
                label = f"杠 {TILE_NAMES[idx]}" if kan_select else f"切 {TILE_NAMES[idx]}"
                kind = "kan_select" if kan_select else "discard"
                tile = idx * 4
            else:
                label, kind, tile = META_ACTIONS.get(idx, (f"动作{idx}", "other", None))
            items.append({
                "rank": rank + 1,
                "action_index": idx,
                "label": label,
                "tile": tile,
                "kind": kind,
                "q": round(qv, 3),
                "pi": round(e / z, 4),
                "gap": round(q_max - qv, 3),
                "best": rank == 0,
            })
        return {"kan_select": kan_select, "candidates": items}

    # ---------------- 状态序列化 ----------------

    def _riichi_discard_index(self):
        """每位玩家的立直宣言牌在自家舍牌列表中的下标（用于前端横放）。"""
        result = {}
        dahai_count = {p: -1 for p in range(4)}
        riichi_pending = {}
        # 只扫描当前这一局（从最近的 start_kyoku 起）
        log = self.env.mjai_log
        start = 0
        for i, ev in enumerate(log):
            if ev.get("type") == "start_kyoku":
                start = i
        for ev in log[start:]:
            t = ev.get("type")
            actor = ev.get("actor")
            if t == "reach":
                riichi_pending[actor] = True
            elif t == "dahai":
                dahai_count[actor] += 1
                if riichi_pending.pop(actor, False):
                    result[actor] = dahai_count[actor]
        return result

    def _discard_tsumogiri(self):
        """每位玩家当前这一局每张舍牌是否为摸切（True=摸切, False=手切）。"""
        result = {p: [] for p in range(4)}
        log = self.env.mjai_log
        start = 0
        for i, ev in enumerate(log):
            if ev.get("type") == "start_kyoku":
                start = i
        for ev in log[start:]:
            if ev.get("type") == "dahai":
                result[ev["actor"]].append(bool(ev.get("tsumogiri")))
        return result

    # ---------------- 小局结算 ----------------

    def _replay_kyoku_hand(self, start_idx: int, end_idx: int, actor: int):
        """从 mjai 事件回放某个已结束小局中 actor 的最终手牌与副露。
        返回 (手牌 id 列表, 副露列表[{type_name, tiles:id列表, from_who}])。"""
        log = self.env.mjai_log
        sk = log[start_idx]
        hand = list(sk["tehais"][actor])  # mjai 字符串
        melds = []
        for ev in log[start_idx + 1 : end_idx]:
            t = ev.get("type")
            if ev.get("actor") != actor:
                continue
            if t == "tsumo":
                hand.append(ev["pai"])
            elif t == "dahai":
                if ev["pai"] in hand:
                    hand.remove(ev["pai"])
            elif t in ("chi", "pon", "daiminkan"):
                for c in ev["consumed"]:
                    hand.remove(c)
                melds.append({
                    "type_name": t,
                    "tiles": sorted(tile_from_mjai(x) for x in [*ev["consumed"], ev["pai"]]),
                    "from_who": ev["target"],
                })
            elif t == "ankan":
                for c in ev["consumed"]:
                    hand.remove(c)
                melds.append({
                    "type_name": "ankan",
                    "tiles": sorted(tile_from_mjai(x) for x in ev["consumed"]),
                    "from_who": None,
                })
            elif t == "kakan":
                added = (ev.get("consumed") or [ev["pai"]])[0]
                if added in hand:
                    hand.remove(added)
                kind_added = tile_from_mjai(added) // 4
                for m in melds:
                    if m["type_name"] == "pon" and any(tt // 4 == kind_added for tt in m["tiles"]):
                        m["type_name"] = "kakan"
                        m["tiles"] = sorted(m["tiles"] + [tile_from_mjai(added)])
                        break
            elif t == "kita" and ev.get("pai") in hand:
                hand.remove(ev["pai"])
        return sorted(tile_from_mjai(x) for x in hand), melds

    def _kyoku_result(self):
        """最近一个已结束小局的结算数据；未结束过任何小局时返回 None。
        id 取 end_kyoku 在 mjai_log 中的下标（单调唯一，供前端判重/关闭）。"""
        log = self.env.mjai_log
        end_idx = None
        for i in range(len(log) - 1, -1, -1):
            if log[i].get("type") == "end_kyoku":
                end_idx = i
                break
        if end_idx is None:
            return None
        start_idx = max(i for i in range(end_idx) if log[i].get("type") == "start_kyoku")
        sk = log[start_idx]
        seg = log[start_idx + 1 : end_idx]
        horas = [(start_idx + 1 + j, e) for j, e in enumerate(seg) if e.get("type") == "hora"]
        ryu = next((e for e in seg if e.get("type") == "ryukyoku"), None)
        if not horas and ryu is None:
            return None

        # WinResult（役/翻/符）按 hora 顺序对应
        round_idx = sum(1 for e in log[:start_idx] if e.get("type") == "start_kyoku")
        results = []
        if horas:
            try:
                from riichienv import get_yaku_by_id
                results = self.env.get_viewer().get_results(round_idx) or []
            except Exception:
                results = []

        wins = []
        for j, (hidx, h) in enumerate(horas):
            actor = h["actor"]
            target = h.get("target")
            is_tsumo = target is None or target == actor
            # 和牌：自摸=该玩家最后一次摸牌，荣和=放铳者最后一张舍牌
            win_tile = None
            for ev in reversed(log[start_idx + 1 : hidx]):
                if is_tsumo and ev.get("type") == "tsumo" and ev.get("actor") == actor:
                    win_tile = tile_from_mjai(ev["pai"])
                    break
                if not is_tsumo and ev.get("type") == "dahai" and ev.get("actor") == target:
                    win_tile = tile_from_mjai(ev["pai"])
                    break
            hand, melds = self._replay_kyoku_hand(start_idx, end_idx, actor)
            wr = results[j] if j < len(results) else None
            yaku = []
            han = fu = points = None
            yakuman = False
            if wr is not None:
                han, fu, yakuman = wr.han, wr.fu, bool(wr.yakuman)
                points = wr.ron_agari if not is_tsumo else (
                    {"ko_each": wr.tsumo_agari_ko, "oya": wr.tsumo_agari_oya}
                )
                try:
                    yaku = [{"name": get_yaku_by_id(y).name, "name_en": get_yaku_by_id(y).name_en}
                            for y in wr.yaku]
                except Exception:
                    yaku = [{"name": str(y), "name_en": ""} for y in wr.yaku]
            wins.append({
                "actor": actor,
                "target": None if is_tsumo else target,
                "is_tsumo": is_tsumo,
                "win_tile": win_tile,
                "hand": hand,
                "melds": melds,
                "yaku": yaku,
                "han": han,
                "fu": fu,
                "yakuman": yakuman,
                "points": points,
            })

        deltas = [0, 0, 0, 0]
        for _, h in horas:
            for p in range(4):
                deltas[p] += h.get("deltas", [0] * 4)[p]
        if ryu is not None:
            for p in range(4):
                deltas[p] += ryu.get("deltas", [0] * 4)[p]

        # 结算后分数：优先取下一局的 start_kyoku 快照，终局则取 env 当前分数
        scores_after = None
        for e in log[end_idx + 1 :]:
            if e.get("type") == "start_kyoku":
                scores_after = e.get("scores")
                break
        if scores_after is None and self.env.done():
            scores_after = self.env.scores()

        reason = ryu.get("reason", "") if ryu else None
        return {
            "id": end_idx,
            "round_wind": 0 if sk.get("bakaze") == "E" else 1,
            "kyoku_idx": (sk.get("kyoku") or 1) - 1,
            "honba": sk.get("honba", 0),
            "type": "hora" if horas else "ryukyoku",
            "wins": wins,
            "deltas": deltas,
            "scores_after": scores_after,
            "ryukyoku_reason": reason,
            "ryukyoku_name": (
                "犯规流局" if reason and reason.startswith("Error")
                else RYUKYOKU_NAMES.get(reason, reason)
            ) if reason else None,
        }

    def state(self):
        env = self.env
        tsumogiri_map = self._discard_tsumogiri()
        legal = []
        if self.human_obs is not None:
            for l in self.human_obs.legal_actions():
                ld = l.to_dict()
                ld["type_name"] = ACTION_NAMES.get(ld["type"], "unknown")
                ld["tile_str"] = tile_to_mjai(ld["tile"]) if ld.get("tile") is not None else None
                legal.append(ld)
        return {
            "game_id": self.gid,
            "done": env.done(),
            "awaiting_human": bool(legal),
            "human_seat": self.human_seat,
            "hand": sorted(env.hands[self.human_seat]),
            "drawn_tile": env.drawn_tile if env.current_player == self.human_seat else None,
            "hand_counts": [len(env.hands[p]) for p in range(4)],
            "discards": [list(env.discards[p]) for p in range(4)],
            "discard_tsumogiri": [tsumogiri_map[p] for p in range(4)],
            "event_count": len(env.mjai_log),
            "melds": [[meld_to_dict(m) for m in env.melds[p]] for p in range(4)],
            "dora_indicators": list(env.dora_indicators),
            "scores": env.scores(),
            "honba": env.honba,
            "riichi_sticks": env.riichi_sticks,
            "riichi_declared": list(env.riichi_declared),
            "riichi_discard_index": self._riichi_discard_index(),
            "round_wind": env.round_wind,  # 0=东 1=南
            "kyoku_idx": env.kyoku_idx,    # 0-3 = 1~4 局
            "oya": env.oya,
            "current_player": env.current_player,
            "legal_actions": legal,
            "suggestions": self._suggestions(),
            "recent_events": env.mjai_log[-12:],
            "kyoku_result": self._kyoku_result(),
            "final": {"scores": env.scores(), "ranks": env.ranks()} if env.done() else None,
        }
