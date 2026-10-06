# Preflop ranges

Ranges live in the app database and are edited from **Rangos preflop** in the UI
(13×13 matrix editor with mixed frequencies, range notation or PioViewer `.txt`).
Sets are exchanged as JSON files with this shape (`empty.json` is the empty template):

```json
{
  "format": "poker-study-ranges",
  "version": 1,
  "charts": [
    {
      "name": "BTN RFI 100bb",
      "source": "pokalab",              // pokalab | preflopranges | custom | computed
      "game_format": "cash",            // cash | mtt | sng | spin
      "players": 6,
      "position": "BTN",
      "vs_position": null,              // opener / raiser / shover, when the spot has one
      "stack_bb": 100,
      "situation": "rfi",               // rfi | vs_open | vs_3bet | vs_4bet | squeeze | bvb | vs_allin
      "open_size_bb": 2.5,
      "rake": "GG NL50",
      "ante_bb": 0,
      "note": "",
      "actions": { "raise": "22+,A2s+,K9s+,AJo:0.5" }   // fold = the rest of each hand
    }
  ]
}
```

Actions: `raise`, `limp`, `call`, `3bet`, `4bet`, `5bet`, `allin`. Weights use the
PioViewer / ProPokerTools notation (`AA:1.0,AKs:0.5`).

External ranges (Pokalab, preflopranges.app, purchased packs) are for **personal use**:
they are loaded by hand through the UI and are **not** shipped in packaged builds.
"Exportar propios y calculados" exports only `custom` and `computed` ranges.
