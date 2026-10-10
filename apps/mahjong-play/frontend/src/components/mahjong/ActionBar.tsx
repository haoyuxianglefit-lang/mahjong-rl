import type { LegalAction } from "@/lib/mahjong"
import { Tile } from "./Tile"

interface ActionBarProps {
  legal: LegalAction[]
  awaiting: boolean
  onAction: (a: { type: string; tile?: number | null; consume_tiles?: number[] }) => void
  chiChoice: LegalAction[] | null
  onChiChoice: (a: LegalAction[] | null) => void
}

const BTN =
  "px-4 py-2 rounded-lg font-bold text-sm shadow transition-colors disabled:opacity-30 disabled:cursor-not-allowed"

export function ActionBar({
  legal,
  awaiting,
  onAction,
  chiChoice,
  onChiChoice,
}: ActionBarProps) {
  const has = (n: string) => legal.some((a) => a.type_name === n)
  const first = (n: string) => legal.find((a) => a.type_name === n)
  const chis = legal.filter((a) => a.type_name === "chi")

  const send = (n: string) => {
    const a = first(n)
    if (a) onAction({ type: n, tile: a.tile, consume_tiles: a.consume_tiles })
  }

  return (
    <div className="relative flex items-center gap-2 flex-wrap">
      {/* 吃的多种选择 */}
      {chiChoice && (
        <div className="absolute bottom-14 left-0 z-20 bg-zinc-800 border border-zinc-600 rounded-xl p-3 shadow-xl">
          <div className="text-xs text-zinc-400 mb-2">选择吃牌组合：</div>
          <div className="flex flex-col gap-2">
            {chiChoice.map((c, i) => (
              <button
                key={i}
                className="flex items-center gap-1 bg-zinc-700 hover:bg-zinc-600 rounded-lg px-2 py-1"
                onClick={() => {
                  onAction({ type: "chi", tile: c.tile, consume_tiles: c.consume_tiles })
                  onChiChoice(null)
                }}
              >
                {c.consume_tiles.map((t, j) => (
                  <Tile key={j} id={t} w={26} />
                ))}
                <span className="text-zinc-300 text-xs ml-1">+ 吃 {c.tile_str}</span>
              </button>
            ))}
            <button
              className="text-xs text-zinc-400 hover:text-white"
              onClick={() => onChiChoice(null)}
            >
              取消
            </button>
          </div>
        </div>
      )}

      {has("tsumo") && (
        <button disabled={!awaiting} className={`${BTN} bg-red-600 hover:bg-red-500 text-white`} onClick={() => send("tsumo")}>
          ツモ（自摸）
        </button>
      )}
      {has("ron") && (
        <button disabled={!awaiting} className={`${BTN} bg-red-600 hover:bg-red-500 text-white`} onClick={() => send("ron")}>
          ロン（荣和）
        </button>
      )}
      {has("riichi") && (
        <button
          disabled={!awaiting}
          className={`${BTN} bg-purple-600 hover:bg-purple-500 text-white`}
          onClick={() => send("riichi")}
        >
          リーチ
        </button>
      )}
      {has("chi") && (
        <button
          disabled={!awaiting}
          className={`${BTN} bg-sky-600 hover:bg-sky-500 text-white`}
          onClick={() => (chis.length > 1 ? onChiChoice(chis) : send("chi"))}
        >
          吃
        </button>
      )}
      {has("pon") && (
        <button disabled={!awaiting} className={`${BTN} bg-sky-600 hover:bg-sky-500 text-white`} onClick={() => send("pon")}>
          碰
        </button>
      )}
      {has("daiminkan") && (
        <button disabled={!awaiting} className={`${BTN} bg-sky-600 hover:bg-sky-500 text-white`} onClick={() => send("daiminkan")}>
          大明杠
        </button>
      )}
      {has("ankan") && (
        <button disabled={!awaiting} className={`${BTN} bg-sky-600 hover:bg-sky-500 text-white`} onClick={() => send("ankan")}>
          暗杠
        </button>
      )}
      {has("kakan") && (
        <button disabled={!awaiting} className={`${BTN} bg-sky-600 hover:bg-sky-500 text-white`} onClick={() => send("kakan")}>
          加杠
        </button>
      )}
      {has("kyushu_kyuhai") && (
        <button disabled={!awaiting} className={`${BTN} bg-amber-600 hover:bg-amber-500 text-white`} onClick={() => send("kyushu_kyuhai")}>
          九种九牌
        </button>
      )}
      {has("pass") && (
        <button disabled={!awaiting} className={`${BTN} bg-zinc-600 hover:bg-zinc-500 text-white`} onClick={() => send("pass")}>
          过
        </button>
      )}
    </div>
  )
}
