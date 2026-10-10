// AI 建议面板：右侧栏展示 Mortal 对当前决策点的 top-5 候选动作
// （Q 值 / softmax 概率 / 与最优的差距），可最小化为侧边小标签。
import { useState } from "react"
import type { Suggestion } from "@/lib/mahjong"
import { Tile } from "@/components/mahjong/Tile"

export function SuggestionPanel({ suggestion }: { suggestion: Suggestion | null }) {
  const [collapsed, setCollapsed] = useState(false)

  if (collapsed) {
    return (
      <button
        onClick={() => setCollapsed(false)}
        className="fixed right-0 top-1/2 -translate-y-1/2 z-40 bg-zinc-900/95 border border-zinc-600 border-r-0 rounded-l-xl px-1.5 py-4 text-xs text-zinc-300 hover:bg-zinc-800 shadow-lg"
        title="展开 AI 建议"
      >
        <span className="block" style={{ writingMode: "vertical-rl" }}>
          AI 建议
        </span>
      </button>
    )
  }

  return (
    <div className="fixed right-3 top-24 z-40 w-64 bg-zinc-900/95 border border-zinc-600 rounded-2xl shadow-2xl">
      <div className="flex items-center justify-between px-3 py-2 border-b border-zinc-700">
        <span className="text-sm font-bold text-emerald-300">AI 建议 · Top 5</span>
        <button
          onClick={() => setCollapsed(true)}
          className="text-zinc-400 hover:text-zinc-200 text-xs px-1.5 py-0.5 rounded hover:bg-zinc-700"
          title="最小化"
        >
          最小化 —
        </button>
      </div>

      {!suggestion ? (
        <div className="px-3 py-4 text-xs text-zinc-500">等待你的决策点时显示模型建议…</div>
      ) : (
        <div className="p-2 flex flex-col gap-1.5">
          {suggestion.candidates.map((c) => {
            const piPct = c.pi * 100
            return (
              <div
                key={c.rank}
                className={`rounded-xl px-2.5 py-1.5 ${
                  c.best ? "bg-emerald-800/50 border border-emerald-500/60" : "bg-zinc-800/70"
                }`}
              >
                <div className="flex items-center gap-2">
                  <span
                    className={`text-xs font-mono w-4 ${c.best ? "text-emerald-300 font-bold" : "text-zinc-500"}`}
                  >
                    {c.rank}
                  </span>
                  {c.tile !== null && <Tile id={c.tile} w={26} />}
                  <span className={`text-sm flex-1 ${c.best ? "text-emerald-200 font-bold" : "text-zinc-200"}`}>
                    {c.label}
                  </span>
                  <span className="text-xs font-mono text-zinc-400">
                    π {piPct >= 99.95 ? "99.9+" : piPct.toFixed(1)}%
                  </span>
                </div>
                <div className="mt-1 h-1.5 rounded bg-black/40 overflow-hidden">
                  <div
                    className={`h-full rounded ${c.best ? "bg-emerald-400" : "bg-zinc-500"}`}
                    style={{ width: `${Math.max(piPct, 0.5)}%` }}
                  />
                </div>
                <div className="mt-0.5 flex justify-between text-[10px] font-mono text-zinc-500">
                  <span>Q {c.q.toFixed(2)}</span>
                  {c.gap > 0.001 && <span>Δ {c.gap.toFixed(2)}</span>}
                </div>
              </div>
            )
          })}
          <div className="text-[10px] text-zinc-600 px-1 pt-0.5">
            π 为合法动作上 softmax(Q) 的概率 · Q 为模型打分
          </div>
        </div>
      )}
    </div>
  )
}
