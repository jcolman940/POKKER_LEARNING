export interface ChartData {
  name: string
  source: string
  game_format: string
  players: number
  position: string
  vs_position: string | null
  stack_bb: number
  situation: string
  open_size_bb: number | null
  rake: string | null
  ante_bb: number
  note: string
  actions: Record<string, number[]>
}

export interface Chart extends ChartData {
  id: number
  created_at: string
  updated_at: string
}
