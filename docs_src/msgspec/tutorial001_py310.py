from fastapi import FastAPI

import msgspec


class Item(msgspec.Struct):
    name: str
    price: float
    description: str | None = None
    tax: float | None = None


app = FastAPI()


@app.get("/items/")
async def read_item():
    return Item(name="Foo", price=3.0)
