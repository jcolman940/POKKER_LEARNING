import pokercore
from fastapi import APIRouter
from pydantic import BaseModel

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
    try:
        combos = pokercore.range_combos(body.text)
    except ValueError as e:
        return RangeParseOut(valid=False, error=f"Rango inválido: {e}")
    return RangeParseOut(
        valid=True,
        combos=sum(w for _, w in combos),
        grid=pokercore.range_grid(body.text),
    )
