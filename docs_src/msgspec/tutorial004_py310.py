from fastapi import FastAPI

import msgspec


class Author(msgspec.Struct):
    name: str


class Book(msgspec.Struct):
    title: str
    author: Author


class Library(msgspec.Struct):
    name: str
    books: list[Book]
    address: str | None = None


app = FastAPI()


@app.get("/libraries/")
async def read_library():
    return Library(
        name="Central Library",
        books=[
            Book(title="1984", author=Author(name="George Orwell")),
            Book(title="Brave New World", author=Author(name="Aldous Huxley")),
        ],
        address="Main Street",
    )
