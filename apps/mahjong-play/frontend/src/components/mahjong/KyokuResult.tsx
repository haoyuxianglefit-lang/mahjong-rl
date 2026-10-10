import type { KyokuResult, KyokuWin } from "@/lib/mahjong"
import { kyokuLabel } from "@/lib/mahjong"
import { Tile } from "./Tile"

interface Props {
  result: KyokuResult
  humanSeat: number
  onClose: () => void
}

function pointsText(w: KyokuWin): string {
  if (w.yakuman) return "役满"
  if (w.points == null) return ""
  if (typeof w.points === "number") return `${w.points} 点`
  // 自摸：oya=0 表示赢家是庄家（每家付 ko_each）
  if (w.points.oya === 0) return `${w.points.ko_each} 点 all`
  return `${w.points.ko_each}/${w.points.oya} 点`
}

function WinBlock({ win, humanSeat }: { win: KyokuWin; humanSeat: number }) {
  const who = win.actor === humanSeat ? "你" : `P${win.actor}`
  const target = win.target === null ? null : win.target === humanSeat ? "你" : `P${win.target}`
  return (
    <div className="bg-zinc-800/80 rounded-xl p-4 mb-3">
      <div className="flex items-baseline justify-between mb-2">
        <span className="font-bold text-lg">
          {who} {win.is_tsumo ? "自摸" : "荣和"}
          {target && <span className="text-zinc-400 text-sm font-normal">（{target} 放铳）</span>}
        </span>
        <span className="text-yellow-300 font-bold text-lg">
          {pointsText(win)}
          {!win.yakuman && win.han !== null && (
            <span className="text-zinc-300 text-sm font-normal ml-2">
              {win.han} 翻 {win.fu} 符
            </span>
          )}
        </span>
      </div>

      {/* 手牌 + 和牌 + 副露 */}
      <div className="flex items-end gap-3 flex-wrap mb-2">
        <div className="flex gap-[1px]">
          {win.hand.map((t, i) => (
            <Tile key={i} id={t} w={26} />
          ))}
          {win.win_tile !== null && (
            <div className="ml-1 relative">
              <Tile id={win.win_tile} w={26} />
              <div className="absolute inset-0 rounded-[3px] ring-2 ring-yellow-300" />
            </div>
          )}
        </div>
        {win.melds.map((m, i) => (
          <div key={i} className="flex gap-[1px]">
            {m.tiles.map((t, j) => (
              <Tile
                key={j}
                id={t}
                w={26}
                faceDown={m.type_name === "ankan" && (j === 0 || j === m.tiles.length - 1)}
              />
            ))}
          </div>
        ))}
      </div>

      {/* 役种 */}
      <div className="flex gap-1 flex-wrap">
        {win.yaku.map((y, i) => (
          <span key={i} className="bg-emerald-800/70 text-emerald-100 text-xs rounded px-2 py-0.5">
            {y.name}
          </span>
        ))}
      </div>
    </div>
  )
}

export function KyokuResultModal({ result, humanSeat, onClose }: Props) {
  const title = `${kyokuLabel(result.round_wind, result.kyoku_idx)} ${result.honba} 本场`
  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-40">
      <div className="bg-zinc-900 border border-zinc-600 rounded-2xl p-6 w-[560px] max-h-[85vh] overflow-y-auto shadow-2xl">
        <h2 className="text-xl font-bold mb-1 text-center">
          {title} · {result.type === "hora" ? "和牌结算" : (result.ryukyoku_name ?? "流局")}
        </h2>
        <div className="h-px bg-zinc-700 my-3" />

        {result.wins.map((w, i) => (
          <WinBlock key={i} win={w} humanSeat={humanSeat} />
        ))}

        {/* 收支一览 */}
        <div className="bg-black/30 rounded-xl px-4 py-2 mb-4">
          {[0, 1, 2, 3].map((p) => (
            <div key={p} className="flex justify-between py-1 text-sm">
              <span className={p === humanSeat ? "text-emerald-300 font-bold" : "text-zinc-300"}>
                {p === humanSeat ? "你" : `P${p}`}
              </span>
              <span className="font-mono">
                <span className={result.deltas[p] > 0 ? "text-emerald-400" : result.deltas[p] < 0 ? "text-red-400" : "text-zinc-500"}>
                  {result.deltas[p] > 0 ? `+${result.deltas[p]}` : result.deltas[p]}
                </span>
                {result.scores_after && (
                  <span className="text-zinc-400 ml-3">→ {result.scores_after[p]}</span>
                )}
              </span>
            </div>
          ))}
        </div>

        <button
          className="w-full py-3 rounded-xl bg-emerald-600 hover:bg-emerald-500 font-bold"
          onClick={onClose}
        >
          继续
        </button>
      </div>
    </div>
  )
}
