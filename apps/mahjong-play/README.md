# 日麻对弈程序（人类 vs 本地 Mortal 模型）

一个本地运行的日麻（立直麻将）对弈程序：**天凤规则、四人半庄**，你通过网页点击打牌，
另外三家由本地训练的 Mortal 模型驱动。

- 后端：`backend/`（Python + FastAPI + riichienv + libriichi/PyTorch）
- 前端：`frontend/`（React + TypeScript + Vite + Tailwind）
- 牌面图片：运行时从 CDN 获取（FluffyStuff/riichi-mahjong-tiles，见下文）

---

## 一、快速开始

需要两个进程（先后端，再前端）：

```powershell
# 1. 后端（使用 Mortal 的 venv，内含 torch / libriichi / riichienv / fastapi）
cd D:\Mahjong AI\apps\mahjong-play\backend
D:\Mahjong AI\third_party\Mortal\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8765

# 2. 前端（另开一个终端）
cd D:\Mahjong AI\apps\mahjong-play\frontend
npm run dev    # http://localhost:7100
```

也可以直接双击根目录的 `启动对弈.bat`（同时拉起两个进程）。

打开 http://localhost:7100/ → 选 checkpoint 和座位 → 开始对局。
首次加载模型约 5~10 秒（CPU 推理，不占用训练用 GPU）。

---

## 二、架构

```
浏览器 (React, :7100)
    │  REST /api/*（vite dev proxy 转发到 8765）
    ▼
FastAPI 后端 (:8765)
    ├── GameSession            对局状态机（每个对局一个实例，内存保存）
    │     ├── riichienv.RiichiEnv   天凤规则引擎：发牌/鸣牌判定/和牌计分/流局/罚符
    │     ├── 3 × libriichi.mjai.Bot AI 座位（Mortal 模型）
    │     └── 人类座位             不挂 bot，legal_actions 暴露给前端
    └── mortal_bridge          加载 Mortal checkpoint -> MortalEngine -> mjai.Bot
```

**模型桥接协议（关键设计）**：riichienv 与 Mortal 之间用 **mjai 事件 JSON** 通信：

```
env.reset() / env.step(actions) -> dict[座位, Observation]
Observation.new_events()        -> 该座位新增的 mjai 事件（JSON 字符串列表）
bot.react(event_json)           -> AI 的 mjai 动作 JSON（或 None）
obs.select_action_from_mjai()   -> 转回 riichienv Action 交给 env.step()
```

人类思考期间，AI 已经决定的争碰/争和动作会暂存（`held_actions`），
等人类提交后合并进同一次 `env.step()`，由规则引擎裁定优先级（和 > 碰/杠 > 吃）。

---

## 三、REST API 明细

Base URL：`http://127.0.0.1:8765`

### `GET /api/health`

健康检查。返回 `{"ok": true}`。

### `GET /api/checkpoints`

列出可用模型权重（`Mortal/mortal/checkpoints/*.pth`）。

```json
{"checkpoints": ["baseline.pth", "best.pth", "mortal.pth", "mortal_298k.pth"]}
```

### `POST /api/games`

创建对局。AI 会立即行动，直到轮到人类或终局。

请求体：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `checkpoint` | string | `"mortal.pth"` | checkpoints 目录下的权重文件名 |
| `human_seat` | int | `0` | 人类座位 0-3（0=东起） |
| `seed` | int\|null | `null` | 牌山种子，留空随机；固定种子可复现同一局 |

返回：`GameState`（见下）。错误：404=权重不存在，500=模型加载/对局启动失败。

### `GET /api/games/{game_id}`

查询当前局面状态（`GameState`）。

### `POST /api/games/{game_id}/action`

提交人类动作。**只能在 `awaiting_human=true` 时调用**。后端校验动作必须在
`legal_actions` 内，随后自动推进所有 AI 回合，直到再次轮到人类或终局，返回新的 `GameState`。

请求体：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `type` | string | 动作类型，见下表 |
| `tile` | int\|null | 动作涉及的牌 id（见"牌 id 编码"） |
| `consume_tiles` | int[]\|null | 吃/碰/杠时手中消耗的牌 |

动作类型（`type` 取值与 `legal_actions[].type_name` 一一对应）：

| type | 含义 | 需要 tile | 需要 consume_tiles |
| --- | --- | --- | --- |
| `discard` | 舍牌 | ✅ | |
| `riichi` | 立直**宣言**（tile 必须为 null，见下方说明） | | |
| `chi` | 吃 | ✅ | ✅（手中 2 张） |
| `pon` | 碰 | ✅ | ✅（手中 2 张） |
| `daiminkan` | 大明杠 | ✅ | ✅（手中 3 张） |
| `ankan` | 暗杠 | ✅ | |
| `kakan` | 加杠 | ✅ | |
| `tsumo` | 自摸和 | | |
| `ron` | 荣和 | | |
| `pass` | 过（放弃鸣牌/和牌） | | |
| `kyushu_kyuhai` | 九种九牌流局 | | |

> 最稳妥的做法：从 `legal_actions` 里挑一个动作原样回传其
> `type_name` / `tile` / `consume_tiles`，不要自己构造。

**立直是两步流程**（与 mjai 协议一致）：`legal_actions` 里出现 `riichi` 时，
其 `tile` 恒为 `null`——它只是一条**宣言**。提交 `{"type":"riichi","tile":null}` 后，
局面会再次轮到人类，此时 `legal_actions` 里的 `discard` 只剩保持听牌的候选牌，
再从中选一张打出，立直即成立（宣言牌会被横放、扣除 1000 点棒）。
**不要**把舍牌塞进 riichi 动作里一起提交（会判非法动作）。

**无牌动作的 tile 必须传 `null` 或不传**（`pass` / `tsumo` / `ron` / `riichi` /
`kyushu_kyuhai`）。传 `0` 之类会被引擎理解为"携带一万"，直接判犯规（chombo：
罚 mangan 点、本局流局、进入下一本场）。

### `GET /api/games/{game_id}/mjai`

导出完整 mjai 牌谱（JSON 数组），兼容 mjai-reviewer 等复盘工具，
可用于后续训练或分析。

### `GameState` 字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `game_id` | string | 对局 ID |
| `done` | bool | 是否终局 |
| `awaiting_human` | bool | 是否在等人类行动（= `legal_actions` 非空） |
| `human_seat` | int | 人类座位 0-3 |
| `hand` | int[] | 人类手牌 id 列表（已排序，含摸到的那张） |
| `drawn_tile` | int\|null | 人类刚摸到的牌 id（仅轮到自己舍牌时非空） |
| `hand_counts` | int[4] | 各座位手牌数（别家手牌内容不下发） |
| `discards` | int[4][] | 各座位舍牌河（按打出顺序，含被鸣走的牌） |
| `discard_tsumogiri` | bool[4][] | 与 `discards` 一一对应：true=摸切，false=手切 |
| `event_count` | int | 整场 mjai 事件总数，单调递增（用于增量检测新事件，如播放音效） |
| `melds` | MeldInfo[4][] | 各座位副露；MeldInfo = `{type, type_name, tiles, opened, from_who}`，`type_name ∈ {chi,pon,daiminkan,ankan,kakan}` |
| `dora_indicators` | int[] | 宝牌指示牌（杠后会追加） |
| `scores` | int[4] | 当前分数 |
| `honba` | int | 本场数 |
| `riichi_sticks` | int | 供托立直棒数 |
| `riichi_declared` | bool[4] | 各座位是否已立直 |
| `riichi_discard_index` | map<int,int> | 各座位立直宣言牌在其舍牌河中的下标（用于横放） |
| `round_wind` | int | 场风：0=东 1=南 |
| `kyoku_idx` | int | 0-3 对应 1~4 局（如 round_wind=0, kyoku_idx=0 → 东1局） |
| `oya` | int | 庄家座位 |
| `current_player` | int | 当前行动座位 |
| `legal_actions` | LegalAction[] | 人类当前合法动作，元素 = `{type:int, type_name:str, tile:int\|null, consume_tiles:int[], tile_str:str\|null}` |
| `recent_events` | object[] | 最近 12 条 mjai 事件（用于前端事件流显示） |
| `kyoku_result` | object\|null | 最近一个已结束小局的结算（见下）；没有任何小局结束时为 null |
| `final` | object\|null | 终局时 `{scores: int[4], ranks: int[4]}`（ranks 1=一位） |

### `kyoku_result` 字段（小局结算）

每个小局结束（和牌/流局）后生成，`id` 单调唯一（= `end_kyoku` 在事件流中的下标），
前端用它判重：展示一次后记住 id，不再重复弹。

| 字段 | 说明 |
| --- | --- |
| `type` | `"hora"`（和牌）或 `"ryukyoku"`（流局） |
| `round_wind` / `kyoku_idx` / `honba` | 已结束小局的场风/局数/本场 |
| `wins` | 和牌列表（可能多家和）；元素 = `{actor, target(null=自摸), is_tsumo, win_tile, hand, melds, yaku:[{name,name_en}], han, fu, yakuman, points}` |
| `wins[].points` | 荣和为总点数 int；自摸为 `{ko_each, oya}`（`oya=0` 表示庄家自摸，每家付 `ko_each`） |
| `wins[].hand` / `wins[].melds` | 和牌者的手牌与副露（从 mjai 事件回放重建，tile id 同"牌 id 编码"） |
| `deltas` | int[4]，四家收支（含本场棒/供托/罚符） |
| `scores_after` | int[4]\|null，结算后的分数 |
| `ryukyoku_name` | 流局原因中文名（荒牌流局/九种九牌/四风连打/三家和了/四杠散了/四家立直/流局满贯/犯规流局） |

### 牌 id 编码（riichienv / mjai / 天凤一致）

```
id // 4 -> 0-8=1m~9m，9-17=1p~9p，18-26=1s~9s，27-33=东南西北白发中
id % 4  -> 同种牌的张数序号（0-3）
赤五为特殊 id：16=赤5m，52=赤5p，88=赤5s
```

前端展示时 id → 图片文件名的映射见 `frontend/src/lib/mahjong.ts` 的 `tileImage()`。

---

## 四、接入你自己的模型（重要）

程序把"模型"抽象为一个对象：**喂给它 mjai 事件 JSON，它返回 mjai 动作 JSON（或 None）**——
即 `libriichi.mjai.Bot` 的 `react(line: str, can_act=True) -> str | None` 接口。
有两种接入方式：

### 方式 A：进程内替换 AI（推荐，改动最小）

编辑 `backend/mortal_bridge.py` 的 `load_engine()`：返回任何实现了
`react_batch(obs, masks, invisible_obs)` 推理接口的对象，并用
`libriichi.mjai.Bot(engine, seat)` 包装即可（Bot 内部自带观测编码 PlayerState）。

如果你的模型**不是** Mortal 架构，更简单的是直接实现一个 duck-typed "Bot"类：

```python
class MyBot:
    def __init__(self, seat): ...
    def react(self, event_json: str, can_act: bool = True) -> str | None:
        """吃入一条 mjai 事件，需要行动时返回 mjai 动作 JSON，否则 None。
        例如弃牌: {"type":"dahai","actor":seat,"pai":"5m","tsumogiri":false}
        无动作:  {"type":"none"} 或直接返回 None。"""
```

然后在 `game_session.py` 的 `GameSession.__init__` 里把 `make_bot(engine, s)`
换成 `MyBot(s)`。mjai 事件协议参考 https://gimite.net/mjai-manual/ 。

### 方式 B：只复用规则引擎（不用 Mortal）

如果只想用"天凤规则 + REST API"这个壳，AI 座位甚至可以留空：
`GameSession` 里 AI 座位不挂 bot 时，可把人类座位扩展为多个或接入远端模型服务。
核心引擎调用只有 5 个：`RiichiEnv(game_mode=2, rule=GameRule.default_tenhou())`、
`reset()`、`step(actions)`、`Observation.new_events()`、`legal_actions()`。

### 模型权重要求（方式 A，Mortal 系）

checkpoint 需为 Mortal 训练格式：`torch.load` 后含
`mortal` / `current_dqn` / `config` 等 key，`config` 里带
`control.version`、`resnet.num_blocks`、`resnet.conv_channels`，程序会自动按配置组网。

---

## 五、牌面图片

运行时从 jsDelivr CDN 加载（开源项目 FluffyStuff/riichi-mahjong-tiles，SVG 矢量图）：

```
https://cdn.jsdelivr.net/gh/FluffyStuff/riichi-mahjong-tiles@master/Regular/{Name}.svg
```

- 数牌：`Man1..9` / `Pin1..9` / `Sou1..9`，赤五：`Man5-Dora` / `Pin5-Dora` / `Sou5-Dora`
- 字牌：`Ton Nan Shaa Pei Haku Hatsu Chun`（东南西北白发中）
- 特殊：`Front`（牌身，Face SVG 是透明底需叠在 Front 上）、`Back`（牌背）

**离线/加速**：把该仓库下载到本地，修改 `frontend/src/lib/mahjong.ts` 顶部的
`TILE_IMG_BASE` 指向本地路径或自建镜像即可。

---

## 六、依赖与环境

| 组件 | 环境 | 说明 |
| --- | --- | --- |
| 后端 | `D:\Mahjong AI\third_party\Mortal\.venv`（Python 3.10） | 已含 torch / libriichi；额外装了 `fastapi`、`uvicorn`、`riichienv` |
| 前端 | Node 20+ | `mahjong-play/frontend`，`npm install` 后 `npm run dev` |
| 规则 | riichienv `GameRule.default_tenhou()` + `game_mode=2`（四人半庄） | 飞人/西入/击飞结束等均按天凤 |

AI 推理默认在 **CPU**（MortalEngine `device='cpu'`），不会影响同时进行的 GPU 训练；
想加速可在 `mortal_bridge.load_engine(..., device="cuda:0")` 改上 GPU。

---

## 七、已知限制 / 路线图

- 会话保存在内存，后端重启即丢失（20 个会话上限，先进先出）。
- 暂不支持三人麻将（riichienv 支持，可自行扩展 `game_mode=5`）。
- 事件流只显示最近 12 条；完整牌谱走 `/api/games/{id}/mjai`。
- 前端为桌面优先设计，窄屏未做深度适配。
