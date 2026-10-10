#!/usr/bin/env python3
"""Self-contained interactive mjai replay viewer.

Reads a mjai event JSONL file (as produced by ``src/mahjong_rl/engines/riichi/random_play.py``) and
writes a single self-contained HTML file: all events are embedded as JSON,
there are no external dependencies, and the file works when opened directly
in a browser (double-click).

Reconstructed per-event state (seat 0 / 自家 at the bottom):

- own hand shown fully; opponents show face-down backs with a tile count
  (the log is omniscient, but hidden information stays hidden by design)
- open melds (副露) per player, closed kans shown as four backs
- discard rivers (舍牌河) with riichi discards rotated sideways
- dora indicators, round wind / seat winds, scores, honba / riichi sticks
- current turn indicator; ``hora`` events show yaku / han / fu / deltas
  (yaku details are present when the log was produced by random_play.py,
  which enriches ``hora`` events via ``MjaiReplay``)
- ``chi``/``pon``/``daiminkan``/``kakan``/``ankan`` events highlight the
  newly formed meld

Controls: prev / next buttons, keyboard ← / →, an event-index slider and a
clickable event-list sidebar.

Usage::

    python tools/replay_viewer.py in.mjai.jsonl [--output view.html]

Notes on the mjai dialect emitted by ``riichienv`` (handled here):

- red fives are ``5mr`` / ``5pr`` / ``5sr`` (``0m`` style is also accepted)
- riichi is a 3-event sequence: ``reach`` -> ``dahai`` -> ``reach_accepted``
- ``hora`` events may lack ``yaku``/``han``/``fu`` if the log was not
  enriched; the viewer then falls back to showing score deltas only
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>mjai 回放查看器 - {title}</title>
<style>
  :root {{
    --felt: #0b6e4f; --felt-dark: #084d37; --panel: #123c2f; --panel2: #0d2f24;
    --accent: #ffd54a; --text: #e8f5ee; --dim: #9dbfb0; --red: #e5383b;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; background: var(--felt-dark); color: var(--text);
    font-family: "Microsoft YaHei", "PingFang SC", sans-serif; height: 100vh;
    display: flex; flex-direction: column; overflow: hidden;
  }}
  #topbar {{
    display: flex; align-items: center; gap: 18px; padding: 6px 14px;
    background: var(--panel2); border-bottom: 1px solid #1d5741; font-size: 14px;
    flex-wrap: wrap;
  }}
  #topbar .kyoku {{ font-size: 18px; font-weight: bold; color: var(--accent); }}
  #topbar .info span {{ margin-right: 10px; }}
  .dora-tiles, .hand, .melds {{ display: inline-flex; gap: 2px; flex-wrap: wrap; }}
  .tile {{
    display: inline-flex; align-items: center; justify-content: center;
    width: 26px; height: 34px; background: #f5f0e6; color: #1a1a1a;
    border-radius: 3px; font-size: 20px; line-height: 1; user-select: none;
    border: 1px solid #c9c2b2;
  }}
  .tile.red {{ color: var(--red); font-weight: bold; }}
  .tile.back {{ background: #2a5d8f; border-color: #1c4368; color: #7ea8cf; font-size: 14px; }}
  .tile.riichi-discard {{ transform: rotate(-90deg); margin: 0 4px; }}
  .tile.small {{ width: 20px; height: 27px; font-size: 15px; }}
  #main {{ display: flex; flex: 1; min-height: 0; }}
  #table {{
    flex: 1; display: grid; padding: 8px;
    grid-template-columns: 1fr minmax(340px, 1.2fr) 1fr;
    grid-template-rows: auto 1fr auto;
    grid-template-areas:
      ".    top    ."
      "left center right"
      ".    bottom .";
    gap: 6px; min-width: 0;
  }}
  .seat {{
    background: var(--panel); border: 2px solid transparent; border-radius: 8px;
    padding: 6px 8px; display: flex; flex-direction: column; gap: 4px; min-width: 0;
  }}
  .seat.active {{ border-color: var(--accent); box-shadow: 0 0 8px rgba(255,213,74,.4); }}
  .seat.flash {{ border-color: #ff8fa3; box-shadow: 0 0 10px rgba(255,143,163,.6); }}
  #seat-0 {{ grid-area: bottom; }} #seat-1 {{ grid-area: right; }}
  #seat-2 {{ grid-area: top; }}    #seat-3 {{ grid-area: left; }}
  .seat-head {{ display: flex; align-items: center; gap: 10px; font-size: 14px; }}
  .seat-wind {{
    writing-mode: vertical-rl; font-size: 16px; font-weight: bold;
    background: #1d5741; border-radius: 4px; padding: 4px 2px; letter-spacing: 2px;
  }}
  .seat.oya .seat-wind {{ background: #8d0801; }}
  .score {{ font-weight: bold; color: var(--accent); font-variant-numeric: tabular-nums; }}
  .riichi-badge {{ color: var(--red); font-weight: bold; font-size: 12px; display: none; }}
  .seat.riichi .riichi-badge {{ display: inline; }}
  .river {{ display: grid; grid-template-columns: repeat(6, 28px); gap: 3px; min-height: 40px; }}
  .river .tile {{ width: 26px; height: 34px; font-size: 18px; }}
  #center {{
    grid-area: center; display: flex; flex-direction: column; align-items: center;
    justify-content: center; gap: 10px; padding: 8px; min-width: 0;
  }}
  #msg {{
    background: var(--panel2); border-radius: 8px; padding: 10px 14px; max-width: 100%;
    font-size: 15px; text-align: center; min-height: 44px; word-break: break-all;
  }}
  #msg .yaku {{ color: var(--accent); }}
  #msg .delta {{ font-variant-numeric: tabular-nums; }}
  #event-json {{
    font-family: Consolas, monospace; font-size: 11px; color: var(--dim);
    max-width: 100%; overflow: auto; max-height: 90px; white-space: pre-wrap;
  }}
  #controls {{
    display: flex; align-items: center; gap: 10px; padding: 6px 14px;
    background: var(--panel2); border-top: 1px solid #1d5741;
  }}
  #controls button {{
    background: #1d5741; color: var(--text); border: 1px solid #2e7d5b;
    border-radius: 4px; padding: 5px 14px; font-size: 14px; cursor: pointer;
  }}
  #controls button:hover {{ background: #2e7d5b; }}
  #slider {{ flex: 1; }}
  #counter {{ font-variant-numeric: tabular-nums; min-width: 90px; text-align: center; }}
  #sidebar {{
    width: 300px; border-left: 1px solid #1d5741; background: var(--panel2);
    overflow-y: auto; font-size: 12px; flex-shrink: 0;
  }}
  #sidebar .ev {{
    padding: 3px 8px; cursor: pointer; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; color: var(--dim); border-bottom: 1px solid #123c2f;
  }}
  #sidebar .ev:hover {{ background: #1d5741; }}
  #sidebar .ev.cur {{ background: #2e7d5b; color: #fff; }}
  .hidden {{ display: none !important; }}
</style>
</head>
<body>
<div id="topbar">
  <span class="kyoku" id="kyoku-label">-</span>
  <span class="info">
    <span>本场 <b id="honba">0</b></span>
    <span>供托 <b id="kyotaku">0</b></span>
    <span>宝牌指示牌: <span class="dora-tiles" id="dora"></span></span>
  </span>
  <span style="flex:1"></span>
  <button id="toggle-sidebar" style="background:#1d5741;color:#e8f5ee;border:1px solid #2e7d5b;border-radius:4px;padding:3px 10px;cursor:pointer;">事件列表</button>
</div>
<div id="main">
  <div id="table">
    <div id="seat-2" class="seat"></div>
    <div id="seat-3" class="seat"></div>
    <div id="center">
      <div id="msg">载入中…</div>
      <div id="event-json"></div>
    </div>
    <div id="seat-1" class="seat"></div>
    <div id="seat-0" class="seat"></div>
  </div>
  <div id="sidebar"></div>
</div>
<div id="controls">
  <button id="prev">◀ 上一事件</button>
  <button id="next">下一事件 ▶</button>
  <input type="range" id="slider" min="0" max="0" value="0" step="1">
  <span id="counter">0 / 0</span>
  <span style="color:var(--dim);font-size:12px;">键盘 ← / → 也可翻页</span>
</div>
<script>
"use strict";
const EVENTS = {events_json};

const WIND_CHARS = ["东", "南", "西", "北"];
const TILE_BACK = String.fromCodePoint(0x1F02B); // 🀫

function tileGlyph(t) {{
  if (!t) return "?";
  const suit = t.slice(-1);
  let num = t.charAt(0);
  let code = null;
  if (suit === "m") code = 0x1F006 + parseInt(num);        // 🀇..🀏
  else if (suit === "p") code = 0x1F018 + parseInt(num);   // 🀙..🀡
  else if (suit === "s") code = 0x1F00F + parseInt(num);   // 🀐..🀘
  else {{
    const z = {{"E":0,"S":1,"W":2,"N":3,"P":4,"F":5,"C":6}}[t];
    if (z === undefined) return "?";
    code = 0x1F000 + z;                                     // 🀀..🀃🀄🀅🀆
  }}
  return String.fromCodePoint(code);
}}
function isRed(t) {{
  return t === "5mr" || t === "5pr" || t === "5sr" ||
         t === "0m" || t === "0p" || t === "0s";
}}
function tileSpan(t, cls) {{
  const s = document.createElement("span");
  s.className = "tile" + (isRed(t) ? " red " : " ") + (cls || "");
  s.textContent = tileGlyph(t);
  s.title = t;
  return s;
}}
function sortTiles(tiles) {{
  const order = t => {{
    if (t === "5mr") return 4.5;
    if (t === "5pr") return 13.5;
    if (t === "5sr") return 22.5;
    if (t === "0m") return 4.4;
    if (t === "0p") return 13.4;
    if (t === "0s") return 22.4;
    const suit = t.slice(-1);
    const base = {{m: 0, p: 9, s: 18}}[suit];
    if (base !== undefined) return base + (parseInt(t) - 1);
    return 27 + {{"E":0,"S":1,"W":2,"N":3,"P":4,"F":5,"C":6}}[t];
  }};
  return tiles.slice().sort((a, b) => order(a) - order(b));
}}

const RYU_REASONS = {{
  exhaustive_draw: "荒牌流局", four_winds: "四风连打", four_kans: "四杠散了",
  four_riichi: "四家立直", nine_terminals: "九种九牌", triple_ron: "三家和了",
}};
const CALL_NAMES = {{chi: "吃", pon: "碰", daiminkan: "大明杠", kakan: "加杠", ankan: "暗杠"}};

function freshState() {{
  return {{
    scores: [25000, 25000, 25000, 25000],
    bakaze: "E", kyoku: 0, honba: 0, kyotaku: 0, oya: 0,
    dora: [], tehais: null,
    hands: [[], [], [], []],        // seat 0 only: real tiles
    handCount: [13, 13, 13, 13],
    melds: [[], [], [], []],
    rivers: [[], [], [], []],       // {{tile, riichi, tsumogiri}}
    riichi: [false, false, false, false],
    pendingRiichi: -1,
    currentActor: -1,
    lastCall: null,                 // {{actor, type}}
    banner: null,                   // html string for center message
  }};
}}

function applyEvent(st, ev) {{
  st.lastCall = null;
  const t = ev.type, actor = ev.actor;
  const removeFromHand = (seat, tile) => {{
    const h = st.hands[seat];
    const i = h.indexOf(tile);
    if (i >= 0) h.splice(i, 1);
  }};
  switch (t) {{
    case "start_game":
      Object.assign(st, freshState());
      break;
    case "start_kyoku":
      st.bakaze = ev.bakaze; st.kyoku = ev.kyoku; st.honba = ev.honba;
      st.kyotaku = ev.kyotaku; st.oya = ev.oya;
      st.scores = ev.scores.slice();
      st.dora = ev.dora_marker ? [ev.dora_marker] : [];
      st.tehais = ev.tehais;
      st.hands = ev.tehais.map(h => sortTiles(h.slice()));
      st.handCount = [13, 13, 13, 13];
      st.melds = [[], [], [], []];
      st.rivers = [[], [], [], []];
      st.riichi = [false, false, false, false];
      st.pendingRiichi = -1; st.currentActor = -1; st.banner = null;
      break;
    case "tsumo":
      st.currentActor = actor;
      if (actor === 0) st.hands[0].push(ev.pai);
      st.handCount[actor] += 1;
      break;
    case "dahai": {{
      st.currentActor = actor;
      let riichi = !!ev.riichi;
      if (st.pendingRiichi === actor) {{ riichi = true; st.pendingRiichi = -1; }}
      if (actor === 0) removeFromHand(0, ev.pai);
      st.handCount[actor] -= 1;
      st.rivers[actor].push({{tile: ev.pai, riichi: riichi, tsumogiri: !!ev.tsumogiri}});
      break;
    }}
    case "reach":
      st.pendingRiichi = actor;
      st.riichi[actor] = true;
      break;
    case "reach_accepted":
      st.kyotaku = (st.kyotaku || 0) + 0; // kyotaku tracked from start_kyoku; score shift applied by engine
      break;
    case "chi": case "pon": case "daiminkan": case "kakan": case "ankan": {{
      const consumed = ev.consumed || [];
      const meldTiles = t === "ankan"
        ? (consumed.length ? consumed : [ev.pai, ev.pai, ev.pai, ev.pai])
        : (consumed.length ? consumed.slice() : [ev.pai, ev.pai, ev.pai]).concat(t === "chi" ? [ev.pai] : []);
      st.melds[actor].push({{type: t, tiles: sortTiles(meldTiles)}});
      if (actor === 0) {{
        const hand = st.hands[0];
        for (const c of consumed) {{
          const i = hand.indexOf(c);
          if (i >= 0) hand.splice(i, 1);
        }}
        if (t === "kakan") removeFromHand(0, ev.pai);
      }}
      st.handCount[actor] -= consumed.length + (t === "kakan" ? 1 : 0);
      // the called tile comes off the discarder's river
      const target = ev.target !== undefined ? ev.target : -1;
      if (t !== "ankan" && t !== "kakan" && target >= 0 && st.rivers[target].length)
        st.rivers[target].pop();
      st.currentActor = actor;
      st.lastCall = {{actor: actor, type: t}};
      break;
    }}
    case "dora":
      if (ev.dora_marker) st.dora.push(ev.dora_marker);
      break;
    case "hora": {{
      if (ev.deltas) st.scores = st.scores.map((s, i) => s + (ev.deltas[i] || 0));
      const who = seatName(st, actor);
      const how = ev.tsumo ? "自摸" : "荣和";
      const from = !ev.tsumo && ev.target !== undefined ? seatName(st, ev.target) : null;
      let html = `<b>${{who}} ${{how}}</b>` + (from ? `（自 ${{from}}）` : "") + "<br>";
      if (ev.yaku && ev.yaku.length)
        html += `<span class="yaku">${{ev.yaku.join("、")}}</span>` +
                (ev.han ? ` ${{ev.han}}番${{ev.fu ? " " + ev.fu + "符" : ""}}` : "") + "<br>";
      if (ev.deltas)
        html += `<span class="delta">收支: ${{ev.deltas.map(d => (d > 0 ? "+" : "") + d).join(" / ")}}</span>`;
      st.banner = html;
      break;
    }}
    case "ryukyoku": {{
      if (ev.deltas) st.scores = st.scores.map((s, i) => s + (ev.deltas[i] || 0));
      const reason = RYU_REASONS[ev.reason] || ev.reason || "流局";
      st.banner = `<b>流局</b> — ${{reason}}` +
        (ev.deltas ? `<br><span class="delta">收支: ${{ev.deltas.map(d => (d > 0 ? "+" : "") + d).join(" / ")}}</span>` : "");
      break;
    }}
    case "end_kyoku":
      st.banner = null;
      break;
    case "end_game": {{
      const ranks = st.scores.map((s, i) => [s, i]).sort((a, b) => b[0] - a[0]);
      st.banner = "<b>对局结束</b><br>" + ranks.map(([s, i], r) =>
        `${{r + 1}}位: ${{seatName(st, i)}} ${{s}}点`).join("　");
      break;
    }}
  }}
}}

function seatName(st, seat) {{
  const w = WIND_CHARS[("ESWN".indexOf(st.bakaze) + seat) % 4];
  return w + "家" + (seat === st.oya ? "(庄)" : "");
}}

function describeEvent(st, ev) {{
  const t = ev.type;
  switch (t) {{
    case "start_game": return "对局开始";
    case "start_kyoku":
      return `${{WIND_CHARS["ESWN".indexOf(ev.bakaze)]}}${{ev.kyoku}}局 开始` +
             (ev.honba ? `（${{ev.honba}} 本场）` : "");
    case "tsumo": return `${{seatName(st, ev.actor)}} 摸牌`;
    case "dahai": return `${{seatName(st, ev.actor)}} 打出 ${{ev.pai}}${{ev.tsumogiri ? "（摸切）" : ""}}`;
    case "reach": return `${{seatName(st, ev.actor)}} 宣告立直！`;
    case "reach_accepted": return `立直成立`;
    case "chi": case "pon": case "daiminkan": case "kakan": case "ankan":
      return `${{seatName(st, ev.actor)}} ${{CALL_NAMES[t]}}`;
    case "dora": return `新宝牌指示牌 ${{ev.dora_marker}}`;
    case "hora": case "ryukyoku": case "end_game": return "";
    case "end_kyoku": return "本局结束";
    default: return t;
  }}
}}

function renderSeat(st, seat) {{
  const el = document.getElementById("seat-" + seat);
  el.className = "seat" + (seat === st.oya ? " oya" : "") +
    (st.riichi[seat] ? " riichi" : "") +
    (seat === st.currentActor ? " active" : "") +
    (st.lastCall && st.lastCall.actor === seat ? " flash" : "");
  el.innerHTML = "";
  const head = document.createElement("div");
  head.className = "seat-head";
  const wind = document.createElement("span");
  wind.className = "seat-wind";
  wind.textContent = WIND_CHARS[("ESWN".indexOf(st.bakaze) + seat) % 4];
  head.appendChild(wind);
  const label = document.createElement("span");
  label.textContent = seat === 0 ? "自家" : `玩家 ${{seat}}`;
  head.appendChild(label);
  const score = document.createElement("span");
  score.className = "score";
  score.textContent = (st.scores[seat] || 0).toLocaleString();
  head.appendChild(score);
  const rb = document.createElement("span");
  rb.className = "riichi-badge";
  rb.textContent = "立直";
  head.appendChild(rb);
  el.appendChild(head);

  // melds
  if (st.melds[seat].length) {{
    const melds = document.createElement("div");
    melds.className = "melds";
    st.melds[seat].forEach((m, mi) => {{
      const box = document.createElement("span");
      box.style.display = "inline-flex"; box.style.gap = "1px";
      box.style.padding = "1px"; box.style.borderRadius = "3px";
      if (st.lastCall && st.lastCall.actor === seat && mi === st.melds[seat].length - 1)
        box.style.background = "rgba(255,143,163,.35)";
      if (m.type === "ankan") {{
        for (let k = 0; k < 4; k++) {{
          const b = document.createElement("span");
          b.className = "tile back"; b.textContent = TILE_BACK;
          box.appendChild(b);
        }}
      }} else {{
        for (const tile of m.tiles) box.appendChild(tileSpan(tile, "small"));
      }}
      melds.appendChild(box);
    }});
    el.appendChild(melds);
  }}

  // river
  const river = document.createElement("div");
  river.className = "river";
  for (const d of st.rivers[seat])
    river.appendChild(tileSpan(d.tile, d.riichi ? "riichi-discard" : ""));
  el.appendChild(river);

  // hand
  const hand = document.createElement("div");
  hand.className = "hand";
  if (seat === 0) {{
    for (const tile of sortTiles(st.hands[0])) hand.appendChild(tileSpan(tile));
  }} else {{
    const n = Math.max(0, st.handCount[seat]);
    const cap = 20;
    for (let k = 0; k < Math.min(n, cap); k++) {{
      const b = document.createElement("span");
      b.className = "tile back"; b.textContent = TILE_BACK;
      hand.appendChild(b);
    }}
    const cnt = document.createElement("span");
    cnt.style.cssText = "color:var(--dim);font-size:12px;align-self:center;margin-left:4px";
    cnt.textContent = "×" + n;
    hand.appendChild(cnt);
  }}
  el.appendChild(hand);
}}

function render(idx) {{
  const st = freshState();
  for (let i = 0; i <= idx && i < EVENTS.length; i++) applyEvent(st, EVENTS[i]);
  const ev = EVENTS[idx] || {{}};

  document.getElementById("kyoku-label").textContent =
    st.kyoku ? `${{WIND_CHARS["ESWN".indexOf(st.bakaze)]}}${{st.kyoku}}局` : "-";
  document.getElementById("honba").textContent = st.honba;
  document.getElementById("kyotaku").textContent = st.kyotaku;
  const dora = document.getElementById("dora");
  dora.innerHTML = "";
  for (const d of st.dora) dora.appendChild(tileSpan(d, "small"));

  for (let s = 0; s < 4; s++) renderSeat(st, s);

  const desc = describeEvent(st, ev) || (idx === EVENTS.length - 1 ? "" : ev.type);
  document.getElementById("msg").innerHTML = st.banner || desc || "…";
  document.getElementById("event-json").textContent = JSON.stringify(ev);

  document.getElementById("slider").value = idx;
  document.getElementById("counter").textContent = (idx + 1) + " / " + EVENTS.length;
  const items = document.querySelectorAll("#sidebar .ev");
  items.forEach((it, i) => it.classList.toggle("cur", i === idx));
  const cur = document.querySelector("#sidebar .ev.cur");
  if (cur) cur.scrollIntoView({{block: "nearest"}});
}}

// ---- controls ----
let idx = 0;
const slider = document.getElementById("slider");
slider.max = EVENTS.length - 1;
function setIdx(i) {{
  idx = Math.max(0, Math.min(EVENTS.length - 1, i));
  render(idx);
}}
document.getElementById("prev").onclick = () => setIdx(idx - 1);
document.getElementById("next").onclick = () => setIdx(idx + 1);
slider.oninput = () => setIdx(parseInt(slider.value));
document.addEventListener("keydown", e => {{
  if (e.key === "ArrowLeft") setIdx(idx - 1);
  else if (e.key === "ArrowRight") setIdx(idx + 1);
}});
document.getElementById("toggle-sidebar").onclick = () =>
  document.getElementById("sidebar").classList.toggle("hidden");

// sidebar list
const sidebar = document.getElementById("sidebar");
EVENTS.forEach((ev, i) => {{
  const div = document.createElement("div");
  div.className = "ev";
  const t = ev.type;
  const brief = (ev.pai ? " " + ev.pai : "") + (ev.dora_marker ? " " + ev.dora_marker : "");
  div.textContent = `${{i}}  ${{t}}${{brief}}`;
  div.onclick = () => setIdx(i);
  sidebar.appendChild(div);
}});

setIdx(0);
</script>
</body>
</html>
"""


def load_events(path: Path) -> list[dict[str, Any]]:
    """Read a mjai JSONL file into a list of event dicts."""
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    if not events:
        raise ValueError(f"{path}: no events found")
    return events


def generate_html(events: list[dict[str, Any]], title: str) -> str:
    """Render the viewer HTML with the events embedded as JSON."""
    events_json = json.dumps(events, ensure_ascii=False).replace("</", "<\\/")
    return HTML_TEMPLATE.format(events_json=events_json, title=title)


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    parser = argparse.ArgumentParser(
        description="Render a mjai JSONL replay as a self-contained interactive HTML file.",
    )
    parser.add_argument("input", type=Path, help="mjai event JSONL file")
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Output HTML path (default: <input> with .html suffix).",
    )
    args = parser.parse_args()

    events = load_events(args.input)
    output = args.output or args.input.with_suffix(".html")
    output.parent.mkdir(parents=True, exist_ok=True)
    html = generate_html(events, args.input.name)
    output.write_text(html, encoding="utf-8")
    print(f"Wrote {output} ({len(events)} events embedded, {len(html)} bytes)")


if __name__ == "__main__":
    main()
