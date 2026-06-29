from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

import msgspec


class Item(msgspec.Struct):
    name: str
    price: float
    description: str | None = None
    tax: float | None = None


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item):
    return PlainTextResponse(f"We got {item!r}")
