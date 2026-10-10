export type SectionId = 'ranges' | 'simulator' | 'pushfold' | 'trainer' | 'history' | 'replayer' | 'stats' | 'solver'

export interface SectionDef {
  id: SectionId
  label: string
  icon: string
}

export const NAV_GROUPS: readonly { title: string; items: readonly SectionDef[] }[] = [
  {
    title: 'Estudiar',
    items: [
      { id: 'ranges', label: 'Preflop', icon: '♦' },
      { id: 'simulator', label: 'Simulador', icon: '⬭' },
      { id: 'pushfold', label: 'Push/Fold', icon: '⇪' },
      { id: 'trainer', label: 'Entrenador', icon: '✎' },
    ],
  },
  {
    title: 'Analizar',
    items: [
      { id: 'history', label: 'Manos', icon: '☰' },
      { id: 'replayer', label: 'Replayer', icon: '▶' },
      { id: 'stats', label: 'Estadísticas', icon: '▤' },
      { id: 'solver', label: 'Solver', icon: '⚙' },
    ],
  },
]

export const SIDEBAR_KEY = 'pokker.sidebar.collapsed'
