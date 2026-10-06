import pokercore
from fastapi import APIRouter
from pydantic import BaseModel

from app.recommend.charts import normalize_range_text

router = APIRouter(prefix="/ranges", tags=["ranges"])


class RangeParseIn(BaseModel):
    text: str


class RangeParseOut(BaseModel):
    valid: bool
    error: str | None = None
    combos: float = 0.0  # weighted combo count (out of 1326)
    grid: list[float] = []  # 169 class weights, 13x13 grid order (aces first)


@router.post("/parse", response_model=RangeParseOut)
def parse_range(body: RangeParseIn) -> RangeParseOut:
    text = normalize_range_text(body.text)
    try:
        combos = pokercore.range_combos(text)
    except ValueError as e:
        return RangeParseOut(valid=False, error=f"Rango inválido: {e}")
    return RangeParseOut(
        valid=True,
        combos=sum(w for _, w in combos),
        grid=pokercore.range_grid(text),
    )
