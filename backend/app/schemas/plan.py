from pydantic import BaseModel


class PlanResponse(BaseModel):
    id: str
    name: str
    label: str
    duration_days: int
    price_rub: int
    new_user_price_rub: int | None
    sort_order: int

    model_config = {"from_attributes": True}
