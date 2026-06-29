from fastapi import FastAPI
from fastapi.responses import MsgspecJSONResponse

import msgspec


class Item(msgspec.Struct):
    name: str
    price: float
    description: str | None = None


app = FastAPI()


@app.get("/items/")
async def read_items():
    return MsgspecJSONResponse(
        [Item(name="Foo", price=3.0), Item(name="Bar", price=4.0)]
    )
