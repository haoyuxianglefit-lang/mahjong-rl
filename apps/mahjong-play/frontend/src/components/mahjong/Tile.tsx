import { TILE_IMG_BASE, TILE_BACK, tileImage, tileLabel } from "@/lib/mahjong"

const TILE_FRONT = TILE_IMG_BASE + "Front.svg" // 牌身（Face SVG 是透明背景，需叠在牌身上）

interface TileProps {
  id: number | null // null = 牌背
  w?: number // 宽度 px，高 = 4/3 w
  rotated?: boolean // 横放（立直宣言牌等）
  faceDown?: boolean
  clickable?: boolean
  selected?: boolean
  dimmed?: boolean
  tedashi?: boolean // 手切标记（红框）
  onClick?: () => void
}

export function Tile({
  id,
  w = 48,
  rotated = false,
  faceDown = false,
  clickable = false,
  selected = false,
  dimmed = false,
  tedashi = false,
  onClick,
}: TileProps) {
  const h = Math.round((w * 4) / 3)
  const body = (
    <div
      className={[
        "relative select-none transition-transform",
        clickable ? "cursor-pointer hover:-translate-y-2" : "",
        selected ? "-translate-y-2" : "",
        dimmed ? "opacity-50" : "",
      ].join(" ")}
      style={{ width: w, height: h }}
      onClick={clickable ? onClick : undefined}
    >
      <img
        src={faceDown || id === null ? TILE_BACK : TILE_FRONT}
        alt=""
        draggable={false}
        className="absolute inset-0 w-full h-full drop-shadow"
      />
      {!faceDown && id !== null && (
        <img
          src={tileImage(id)}
          alt={tileLabel(id)}
          draggable={false}
          className="absolute inset-0 w-full h-full"
        />
      )}
      {selected && (
        <div className="absolute inset-0 rounded-[4px] ring-2 ring-yellow-300" />
      )}
      {tedashi && (
        <div className="absolute inset-0 rounded-[4px] ring-2 ring-red-500" />
      )}
    </div>
  )
  if (rotated) {
    // 横放：外层占位仍为 w×h，内部旋转 90° 后视觉宽高互换
    return (
      <div
        className="flex items-center justify-center"
        style={{ width: h, height: w, margin: `${(w - h) / 2}px ${(h - w) / 2}px` }}
      >
        <div style={{ transform: "rotate(90deg)" }}>{body}</div>
      </div>
    )
  }
  return body
}
