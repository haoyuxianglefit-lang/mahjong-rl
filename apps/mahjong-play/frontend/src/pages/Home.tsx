import { useEffect, useMemo, useRef, useState } from "react"
import {
  kyokuLabel, listCheckpoints, newGame, playSound,
  sendAction, sortTiles, WIND_LABELS,
} from "@/lib/mahjong"
import type { GameState, LegalAction, SoundName } from "@/lib/mahjong"
import { Tile } from "@/components/mahjong/Tile"
import { ActionBar } from "@/components/mahjong/ActionBar"
import { KyokuResultModal } from "@/components/mahjong/KyokuResult"
import { SuggestionPanel } from "@/components/mahjong/SuggestionPanel"

const EVENT_LABEL: Record<string, string> = {
  start_game: "开始对局", start_kyoku: "开局", tsumo: "摸牌", dahai: "舍牌",
  reach: "立直宣言", reach_accepted: "立直成立", chi: "吃", pon: "碰",
  daiminkan: "大明杠", ankan: "暗杠", kakan: "加杠", hora: "和牌",
  ryukyoku: "流局", dora_marker: "宝牌指示牌", end_game: "终局",
}

function eventText(ev: Record<string, any>): string {
  const t = String(ev.type ?? "")
  let s = EVENT_LABEL[t] ?? t
  if (ev.actor !== undefined) s += ` P${ev.actor}`
  if (ev.pai) s += ` ${ev.pai}`
  if (t === "hora" && ev.deltas) s += ` [${ev.deltas.join(", ")}]`
  return s
}

function DiscardField({ tiles, tsumogiri, riichiIdx, size = 30 }: { tiles: number[]; tsumogiri?: boolean[]; riichiIdx?: number; size?: number }) {
  return (
    <div className={`grid grid-cols-6 gap-[2px] p-1 rounded w-fit min-w-[120px] min-h-[40px] ${tiles.length ? "bg-black/20" : ""}`}>
      {tiles.map((t, i) => (
        <Tile key={i} id={t} w={size} rotated={i === riichiIdx} dimmed={false} tedashi={tsumogiri ? !tsumogiri[i] : false} />
      ))}
    </div>
  )
}

function MeldRow({ melds, size = 34 }: { melds: GameState["melds"][number]; size?: number }) {
  return (
    <div className="flex gap-3">
      {melds.map((m, i) => (
        <div key={i} className="flex gap-[1px]">
          {m.tiles.map((t, j) => (
            <Tile
              key={j}
              id={t}
              w={size}
              faceDown={m.type_name === "ankan" && (j === 0 || j === m.tiles.length - 1)}
            />
          ))}
        </div>
      ))}
    </div>
  )
}

// checkpoint 文件名 -> 友好显示名（未知文件回退显示原名）
const CHECKPOINT_LABELS: Record<string, string> = {
  "mortal.pth": "Mortal 官方模型（默认·最强）",
  "best.pth": "自训 best（你的模型）",
  "baseline.pth": "baseline（基线）",
  "grp.pth": "GRP 对手池模型",
  "mortal_298k.pth": "Mortal 298k 半成品",
}
// 默认主推模型
const DEFAULT_CHECKPOINT = "mortal.pth"

function checkpointLabel(c: string): string {
  return CHECKPOINT_LABELS[c] ?? c
}

export default function Home() {
  const [checkpoints, setCheckpoints] = useState<string[]>([])
  const [checkpoint, setCheckpoint] = useState(DEFAULT_CHECKPOINT)
  const [seat, setSeat] = useState(0)
  const [seed, setSeed] = useState("")
  const [st, setSt] = useState<GameState | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState("")
  const [chiChoice, setChiChoice] = useState<LegalAction[] | null>(null)
  const [dismissedKyoku, setDismissedKyoku] = useState(-1) // 已关闭的结算页 id

  useEffect(() => {
    listCheckpoints().then(setCheckpoints).catch((e) => setErr(String(e)))
  }, [])

  // ---------- 音效：按 event_count 增量检测新事件 ----------
  // 一次状态刷新可能包含多步 AI 动作，为避免连放造成嘈杂，
  // 每批新事件只播一个音，优先级：和牌 > 立直 > 鸣牌 > 舍牌。
  const lastEventCount = useRef(0)
  useEffect(() => {
    if (!st) {
      lastEventCount.current = 0
      return
    }
    const prev = lastEventCount.current
    lastEventCount.current = st.event_count
    if (prev === 0 || st.event_count <= prev) return // 新开局或无新事件
    const fresh = st.recent_events.slice(-(st.event_count - prev))
    const types = new Set(fresh.map((e) => String(e.type ?? "")))
    let sound: SoundName | null = null
    if (types.has("hora")) sound = "hora"
    else if (types.has("reach") || types.has("reach_accepted")) sound = "riichi"
    else if (["chi", "pon", "daiminkan", "ankan", "kakan"].some((t) => types.has(t))) sound = "call"
    else if (types.has("dahai")) sound = "discard"
    if (sound) playSound(sound)
  }, [st])

  const start = async () => {
    setBusy(true); setErr("")
    try {
      const s = await newGame({
        checkpoint,
        human_seat: seat,
        seed: seed.trim() === "" ? null : Number(seed),
      })
      setSt(s); setChiChoice(null); setDismissedKyoku(-1)
    } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }

  const act = async (a: { type: string; tile?: number | null; consume_tiles?: number[] }) => {
    if (!st || busy) return
    setBusy(true); setErr("")
    try {
      const s = await sendAction(st.game_id, a)
      setSt(s); setChiChoice(null)
    } catch (e) { setErr(String(e)) } finally { setBusy(false) }
  }

  // ---------- 派生状态 ----------
  const legal = st?.legal_actions ?? []
  const discardTiles = useMemo(
    () => new Set(legal.filter((a) => a.type_name === "discard").map((a) => a.tile)),
    [legal],
  )

  const onTileClick = (tileId: number) => {
    if (!st?.awaiting_human || busy) return
    if (discardTiles.has(tileId)) act({ type: "discard", tile: tileId })
  }

  // ---------- 开局面板 ----------
  if (!st) {
    return (
      <div className="min-h-screen bg-emerald-950 text-zinc-100 flex items-center justify-center p-6">
        <div className="bg-zinc-900/80 border border-zinc-700 rounded-2xl p-8 w-[420px] shadow-2xl">
          <h1 className="text-2xl font-bold mb-1">日麻对弈 · Mortal</h1>
          <p className="text-zinc-400 text-sm mb-6">天凤规则 · 四人半庄 · 你 vs 3 个 demo</p>

          <label className="block text-sm text-zinc-300 mb-1">AI 模型</label>
          <select
            className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 mb-4"
            value={checkpoint}
            onChange={(e) => setCheckpoint(e.target.value)}
          >
            {checkpoints.map((c) => <option key={c} value={c}>{checkpointLabel(c)}</option>)}
          </select>

          <label className="block text-sm text-zinc-300 mb-1">你的座位（0=东起，推荐）</label>
          <div className="flex gap-2 mb-4">
            {[0, 1, 2, 3].map((s) => (
              <button
                key={s}
                onClick={() => setSeat(s)}
                className={`flex-1 py-2 rounded-lg border ${seat === s ? "bg-emerald-600 border-emerald-400" : "bg-zinc-800 border-zinc-600"}`}
              >
                {WIND_LABELS[s]}起
              </button>
            ))}
          </div>

          <label className="block text-sm text-zinc-300 mb-1">种子（可选，留空随机）</label>
          <input
            className="w-full bg-zinc-800 border border-zinc-600 rounded-lg px-3 py-2 mb-6"
            value={seed}
            onChange={(e) => setSeed(e.target.value)}
            placeholder="例如 42"
          />

          {err && <div className="text-red-400 text-sm mb-3 break-all">{err}</div>}
          <button
            onClick={start}
            disabled={busy || checkpoints.length === 0}
            className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-bold text-lg disabled:opacity-40"
          >
            {busy ? "模型加载中…" : "开始对局"}
          </button>
          <p className="text-zinc-500 text-xs mt-3">首次加载模型约需 5~10 秒</p>
        </div>
      </div>
    )
  }

  // ---------- 牌桌 ----------
  const human = st.human_seat
  const playerAt = (pos: number) => (human + pos) % 4

  const drawn = st.drawn_tile
  const handBody = sortTiles(
    drawn !== null ? st.hand.filter((_, i) => i !== st.hand.indexOf(drawn)) : st.hand,
  )

  const renderOther = (pos: number) => {
    const p = playerAt(pos)
    const rot = pos === 1 ? "rotate(-90deg)" : pos === 2 ? "rotate(180deg)" : "rotate(90deg)"
    return (
      <div className="flex flex-col items-center gap-1" style={{ transform: rot }}>
        <div className="flex items-center gap-2 text-xs text-zinc-300">
          <span className={st.current_player === p ? "text-yellow-300 font-bold" : ""}>
            {WIND_LABELS[(p - st.oya + 4) % 4]}家 P{p}
            {st.riichi_declared[p] && <span className="ml-1 text-red-400">立直</span>}
          </span>
          <span>{st.scores[p]}</span>
        </div>
        <div className="flex gap-[1px]">
          {Array.from({ length: st.hand_counts[p] }).map((_, i) => (
            <Tile key={i} id={null} w={22} />
          ))}
        </div>
        <MeldRow melds={st.melds[p]} size={26} />
      </div>
    )
  }

  const renderDiscards = (pos: number) => {
    const p = playerAt(pos)
    const field = (
      <DiscardField tiles={st.discards[p]} tsumogiri={st.discard_tsumogiri?.[p]} riichiIdx={st.riichi_discard_index?.[String(p)] ?? st.riichi_discard_index?.[p]} size={pos === 0 ? 34 : 26} />
    )
    if (pos === 2) return <div style={{ transform: "rotate(180deg)" }}>{field}</div>
    if (pos === 1 || pos === 3) {
      // 侧家：固定尺寸方框内旋转，避免旋转后布局错位
      return (
        <div className="flex items-center justify-center" style={{ width: 190, height: 190 }}>
          <div style={{ transform: pos === 1 ? "rotate(-90deg)" : "rotate(90deg)" }}>{field}</div>
        </div>
      )
    }
    return field
  }

  return (
    <div className="min-h-screen bg-emerald-950 text-zinc-100 flex flex-col items-center py-4 gap-2 select-none">
      {/* 顶部信息栏 */}
      <div className="flex items-center gap-4 text-sm bg-black/30 rounded-xl px-4 py-2">
        <span className="font-bold text-lg">{kyokuLabel(st.round_wind, st.kyoku_idx)}</span>
        <span>本场 {st.honba}</span>
        <span>供托 {st.riichi_sticks}</span>
        <span className="flex items-center gap-1">
          宝牌指示牌 {st.dora_indicators.map((d, i) => <Tile key={i} id={d} w={24} />)}
        </span>
        <button
          className="ml-4 px-3 py-1 rounded bg-zinc-700 hover:bg-zinc-600 text-xs"
          onClick={() => setSt(null)}
        >
          新对局
        </button>
      </div>

      {/* 牌桌 */}
      <div className="grid grid-cols-[auto_minmax(380px,520px)_auto] grid-rows-[auto_1fr_auto] gap-2 items-center">
        <div className="col-start-2 row-start-1 flex justify-center">{renderOther(2)}</div>
        <div className="col-start-1 row-start-2 flex justify-center">{renderOther(3)}</div>
        <div className="col-start-3 row-start-2 flex justify-center">{renderOther(1)}</div>

        {/* 中央：四家舍牌 + 信息 */}
        <div className="col-start-2 row-start-2 relative bg-emerald-900/60 rounded-2xl border-4 border-emerald-800 aspect-square p-2">
          <div className="absolute left-1/2 top-2 -translate-x-1/2">{renderDiscards(2)}</div>
          <div className="absolute left-1/2 bottom-2 -translate-x-1/2">{renderDiscards(0)}</div>
          <div className="absolute left-2 top-1/2 -translate-y-1/2">{renderDiscards(3)}</div>
          <div className="absolute right-2 top-1/2 -translate-y-1/2">{renderDiscards(1)}</div>
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="bg-black/40 rounded-lg px-3 py-2 text-center text-xs leading-5">
              {[0, 1, 2, 3].map((p) => (
                <div key={p} className={p === human ? "text-emerald-300 font-bold" : "text-zinc-300"}>
                  {WIND_LABELS[(p - st.oya + 4) % 4]} {p === human ? "你" : `P${p}`}
                  {st.oya === p ? "（庄）" : ""}：{st.scores[p]}
                  {st.riichi_declared[p] ? " 🀄" : ""}
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* 人类区域 */}
        <div className="col-span-3 row-start-3 flex flex-col items-center gap-2 mt-1 bg-black/25 rounded-2xl px-6 py-3 border border-emerald-800/60">
          <div className="flex items-end gap-4">
            <MeldRow melds={st.melds[human]} size={40} />
            <div className="flex items-end gap-[2px]">
              {handBody.map((t, i) => (
                <Tile
                  key={`${t}-${i}`}
                  id={t}
                  w={52}
                  clickable={st.awaiting_human && discardTiles.has(t)}
                  onClick={() => onTileClick(t)}
                />
              ))}
              {drawn !== null && (
                <div className="ml-3">
                  <Tile
                    id={drawn}
                    w={52}
                    clickable={st.awaiting_human && discardTiles.has(drawn)}
                    onClick={() => onTileClick(drawn)}
                  />
                </div>
              )}
            </div>
          </div>
          <div className="min-h-[44px] flex items-center">
            {st.done ? null : st.awaiting_human ? (
              <ActionBar
                legal={legal}
                awaiting={st.awaiting_human && !busy}
                onAction={act}
                chiChoice={chiChoice}
                onChiChoice={setChiChoice}
              />
            ) : (
              <div className="text-zinc-400 text-sm">{busy ? "AI 思考中…" : "等待其他玩家…"}</div>
            )}
          </div>
        </div>
      </div>

      {/* 事件流 */}
      <div className="flex gap-3 text-xs text-zinc-400 max-w-3xl flex-wrap justify-center">
        {st.recent_events.slice(-6).map((e, i) => (
          <span key={i} className="bg-black/20 rounded px-2 py-0.5">{eventText(e)}</span>
        ))}
      </div>

      {err && <div className="text-red-400 text-sm">{err}</div>}

      {/* 小局结算页（优先于终局面板显示） */}
      {st.kyoku_result && st.kyoku_result.id !== dismissedKyoku && (
        <KyokuResultModal
          result={st.kyoku_result}
          humanSeat={human}
          onClose={() => setDismissedKyoku(st.kyoku_result!.id)}
        />
      )}

      {/* 终局面板（结算页关闭后再显示） */}
      {st.done && st.final && (!st.kyoku_result || st.kyoku_result.id === dismissedKyoku) && (
        <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-30">
          <div className="bg-zinc-900 border border-zinc-600 rounded-2xl p-8 w-[380px] text-center shadow-2xl">
            <h2 className="text-xl font-bold mb-4">对局结束</h2>
            {[0, 1, 2, 3]
              .map((p) => ({ p, score: st.final!.scores[p], rank: st.final!.ranks[p] }))
              .sort((a, b) => a.rank - b.rank)
              .map(({ p, score, rank }) => (
                <div
                  key={p}
                  className={`flex justify-between px-4 py-2 rounded-lg mb-1 ${p === human ? "bg-emerald-800/60" : "bg-zinc-800"}`}
                >
                  <span>{rank}位 — {p === human ? "你" : `P${p}`}</span>
                  <span className="font-mono">{score}</span>
                </div>
              ))}
            <button
              className="mt-5 w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-bold"
              onClick={() => setSt(null)}
            >
              再来一局
            </button>
          </div>
        </div>
      )}

      {/* AI 建议面板（右侧栏，可最小化） */}
      <SuggestionPanel suggestion={st.suggestions} />
    </div>
  )
}
