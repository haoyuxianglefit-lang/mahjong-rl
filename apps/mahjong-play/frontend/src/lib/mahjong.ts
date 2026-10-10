// 日麻对弈前端：类型、API 客户端、牌面工具
//
// 牌 ID 编码（与后端/天凤 mjai 一致）：
//   id // 4 -> 0-8=1m~9m, 9-17=1p~9p, 18-26=1s~9s, 27-33=东南西北白发中
//   id % 4  -> 同种牌的张数序号；赤五为特殊 id：16=赤5m, 52=赤5p, 88=赤5s

export const TILE_IMG_BASE =
  "https://cdn.jsdelivr.net/gh/FluffyStuff/riichi-mahjong-tiles@master/Regular/"

const HONORS = ["Ton", "Nan", "Shaa", "Pei", "Haku", "Hatsu", "Chun"] // 东南西北白发中
export const WIND_LABELS = ["东", "南", "西", "北"]

export function tileImage(id: number): string {
  if (id === 16) return TILE_IMG_BASE + "Man5-Dora.svg"
  if (id === 52) return TILE_IMG_BASE + "Pin5-Dora.svg"
  if (id === 88) return TILE_IMG_BASE + "Sou5-Dora.svg"
  const kind = Math.floor(id / 4)
  if (kind < 9) return `${TILE_IMG_BASE}Man${kind + 1}.svg`
  if (kind < 18) return `${TILE_IMG_BASE}Pin${kind - 8}.svg`
  if (kind < 27) return `${TILE_IMG_BASE}Sou${kind - 17}.svg`
  return `${TILE_IMG_BASE}${HONORS[kind - 27]}.svg`
}

export const TILE_BACK = TILE_IMG_BASE + "Back.svg"

export function tileLabel(id: number): string {
  if (id === 16) return "0m"
  if (id === 52) return "0p"
  if (id === 88) return "0s"
  const kind = Math.floor(id / 4)
  if (kind < 27) return `${(kind % 9) + 1}${"mps"[Math.floor(kind / 9)]}`
  return ["E", "S", "W", "N", "P", "F", "C"][kind - 27]
}

// 排序键：按种类，赤五排在普通五之前
export function tileSortKey(id: number): number {
  const kind = Math.floor(id / 4)
  const red = id === 16 || id === 52 || id === 88 ? -0.5 : 0
  return kind * 4 + (id % 4) + red
}

export function sortTiles(ids: number[]): number[] {
  return [...ids].sort((a, b) => tileSortKey(a) - tileSortKey(b))
}

// ---------- API 类型 ----------

export interface LegalAction {
  type: number
  type_name:
    | "discard" | "chi" | "pon" | "daiminkan" | "ron" | "riichi"
    | "tsumo" | "pass" | "ankan" | "kakan" | "kyushu_kyuhai" | "kita"
  tile: number | null
  consume_tiles: number[]
  tile_str: string | null
}

export interface MeldInfo {
  type: number
  type_name: "chi" | "pon" | "daiminkan" | "ankan" | "kakan"
  tiles: number[]
  opened: boolean
  from_who: number
}

export interface KyokuWin {
  actor: number
  target: number | null // 放铳者；自摸为 null
  is_tsumo: boolean
  win_tile: number | null
  hand: number[] // 和牌时手牌（不含和牌本身）
  melds: { type_name: string; tiles: number[]; from_who: number | null }[]
  yaku: { name: string; name_en: string }[]
  han: number | null
  fu: number | null
  yakuman: boolean
  /** 荣和=总点数；自摸={ko_each, oya} 各家支付 */
  points: number | { ko_each: number; oya: number } | null
}

export interface KyokuResult {
  id: number // end_kyoku 在事件流中的下标，单调唯一
  round_wind: number
  kyoku_idx: number
  honba: number
  type: "hora" | "ryukyoku"
  wins: KyokuWin[]
  deltas: number[] // 四家收支（含本场/供托/罚符）
  scores_after: number[] | null
  ryukyoku_reason: string | null
  ryukyoku_name: string | null
}

export interface SuggestionCandidate {
  rank: number
  action_index: number
  label: string       // 如 "切 5m" / "立直" / "碰"
  tile: number | null // 切牌建议对应的展示 tile id（非切牌为 null）
  kind: string
  q: number           // DQN 输出的 Q 值
  pi: number          // 合法动作上的 softmax(Q) 概率
  gap: number         // 与最优动作的 Q 差
  best: boolean
}

export interface Suggestion {
  kan_select: boolean
  candidates: SuggestionCandidate[]
}

export interface GameState {
  game_id: string
  done: boolean
  awaiting_human: boolean
  human_seat: number
  hand: number[]
  drawn_tile: number | null
  hand_counts: number[]
  discards: number[][]
  /** 与 discards 一一对应：true=摸切 false=手切 */
  discard_tsumogiri: boolean[][]
  /** 整场 mjai 事件总数（用于增量检测新事件以播放音效） */
  event_count: number
  melds: MeldInfo[][]
  dora_indicators: number[]
  scores: number[]
  honba: number
  riichi_sticks: number
  riichi_declared: boolean[]
  riichi_discard_index: Record<string, number>
  round_wind: number // 0=东 1=南
  kyoku_idx: number  // 0-3
  oya: number
  current_player: number
  legal_actions: LegalAction[]
  suggestions: Suggestion | null
  recent_events: Record<string, unknown>[]
  kyoku_result: KyokuResult | null
  final: { scores: number[]; ranks: number[] } | null
}

const API = "/api"

export async function listCheckpoints(): Promise<string[]> {
  const r = await fetch(`${API}/checkpoints`)
  if (!r.ok) throw new Error(`checkpoints: HTTP ${r.status}`)
  return (await r.json()).checkpoints
}

export async function newGame(req: {
  checkpoint: string
  human_seat: number
  seed?: number | null
}): Promise<GameState> {
  const r = await fetch(`${API}/games`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!r.ok) throw new Error(`new game: HTTP ${r.status} ${await r.text()}`)
  return r.json()
}

export async function sendAction(
  gid: string,
  a: { type: string; tile?: number | null; consume_tiles?: number[] },
): Promise<GameState> {
  const r = await fetch(`${API}/games/${gid}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(a),
  })
  if (!r.ok) throw new Error(`action: HTTP ${r.status} ${await r.text()}`)
  return r.json()
}

// ---------- 展示辅助 ----------

export function kyokuLabel(roundWind: number, kyokuIdx: number): string {
  return `${WIND_LABELS[roundWind] ?? "?"}${kyokuIdx + 1}局`
}

/** 座位 p 相对于人类的方位：0=下(自己) 1=右(下家) 2=对 3=左(上家) */
export function relativePos(p: number, humanSeat: number): number {
  return (p - humanSeat + 4) % 4
}

// ---------- 音效 ----------

export type SoundName = "discard" | "call" | "riichi" | "hora"

const audioCache: Partial<Record<SoundName, HTMLAudioElement>> = {}

const SOUND_VOLUME: Record<SoundName, number> = {
  discard: 1.0,
  call: 0.7,
  riichi: 0.3,
  hora: 0.8,
}

export function playSound(name: SoundName) {
  try {
    const a = (audioCache[name] ??= new Audio(`/sounds/${name}.mp3`))
    a.currentTime = 0
    a.volume = SOUND_VOLUME[name]
    void a.play().catch(() => {}) // 首次交互前浏览器会拒绝自动播放，静默忽略
  } catch {
    /* 无音频环境时忽略 */
  }
}
