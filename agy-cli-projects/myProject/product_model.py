from pydantic import BaseModel
from typing import Optional, Any

class Product(BaseModel):
    product: str
    cost: float
    stock: Optional[Any] = None
