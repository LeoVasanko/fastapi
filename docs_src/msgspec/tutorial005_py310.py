from fastapi import FastAPI

import msgspec


class Item(msgspec.Struct):
    item_name: str = msgspec.field(name="itemName")
    price: float


app = FastAPI()


@app.post("/items/")
async def create_item(item: Item):
    return item
