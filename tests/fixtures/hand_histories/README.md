# Hand history fixtures

Real sample hand histories provided by the user, one folder per room
(`ggpoker/`, `pokerstars/`), covering both cash and tournaments.

- `ggpoker/mtt-*.txt`: two GGPoker MTT exports (2026-10-10), unchanged. GG already
  anonymizes them: the user is `Hero` and opponents are hex ids.
- `ggpoker/summary-*.txt`: the PokerCraft tournament summaries of those two MTTs.

Formats must **not** be written from memory: parsers are closed only against
real samples placed here (phase 4).
