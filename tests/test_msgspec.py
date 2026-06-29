from typing import Any

import pytest
from dirty_equals import IsDict
from fastapi import FastAPI
from fastapi.responses import MsgspecJSONResponse
from fastapi.testclient import TestClient
from pydantic import BaseModel

try:
    import msgspec
except ImportError:  # pragma: nocover
    pytest.skip("msgspec not installed", allow_module_level=True)


class Address(msgspec.Struct):
    city: str


class Item(msgspec.Struct):
    name: str
    price: float = 0.0
    address: Address | None = None


class ItemOut(msgspec.Struct):
    name: str
    total: float


class ItemAlias(msgspec.Struct):
    item_name: str = msgspec.field(name="itemName")
    price: float


class PydanticItem(BaseModel):
    name: str
    price: float


def test_msgspec_request_and_response_model() -> None:
    app = FastAPI()

    @app.post("/items", response_model=ItemOut)
    def create_item(item: Item) -> ItemOut:
        return ItemOut(name=item.name, total=item.price * 2)

    client = TestClient(app)
    response = client.post("/items", json={"name": "widget", "price": 10.0})
    assert response.status_code == 200
    assert response.json() == {"name": "widget", "total": 20.0}


def test_msgspec_request_validation_error() -> None:
    app = FastAPI()

    @app.post("/items", response_model=ItemOut)
    def create_item(item: Item) -> ItemOut:
        return ItemOut(name=item.name, total=item.price * 2)

    client = TestClient(app)
    response = client.post("/items", json={"name": "widget", "price": "not-a-number"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "msgspec_validation"


def test_msgspec_response_model_by_alias() -> None:
    app = FastAPI()

    @app.post("/items", response_model=ItemAlias)
    def create_item(item: ItemAlias) -> ItemAlias:
        return item

    client = TestClient(app)
    response = client.post("/items", json={"itemName": "widget", "price": 10.0})
    assert response.status_code == 200
    assert response.json() == {"itemName": "widget", "price": 10.0}


def test_msgspec_nested_structs() -> None:
    app = FastAPI()

    @app.post("/items", response_model=Item)
    def create_item(item: Item) -> Item:
        return item

    client = TestClient(app)
    response = client.post(
        "/items",
        json={"name": "widget", "price": 10.0, "address": {"city": "Helsinki"}},
    )
    assert response.status_code == 200
    assert response.json() == {
        "name": "widget",
        "price": 10.0,
        "address": {"city": "Helsinki"},
    }


def test_msgspec_list_request_response() -> None:
    app = FastAPI()

    @app.post("/items", response_model=list[Item])
    def create_items(items: list[Item]) -> list[Item]:
        return items

    client = TestClient(app)
    response = client.post(
        "/items", json=[{"name": "a", "price": 1.0}, {"name": "b", "price": 2.0}]
    )
    assert response.status_code == 200
    assert response.json() == [
        {"name": "a", "price": 1.0, "address": None},
        {"name": "b", "price": 2.0, "address": None},
    ]


def test_msgspec_optional_request_response() -> None:
    app = FastAPI()

    @app.post("/items", response_model=Item | None)
    def create_item(item: Item | None) -> Item | None:
        return item

    client = TestClient(app)
    response = client.post("/items", json={"name": "widget", "price": 10.0})
    assert response.status_code == 200
    assert response.json() == {"name": "widget", "price": 10.0, "address": None}

    response = client.post("/items", json=None)
    assert response.status_code == 200
    assert response.json() is None


def test_msgspec_json_response() -> None:
    app = FastAPI()

    @app.get("/item")
    def get_item() -> MsgspecJSONResponse:
        return MsgspecJSONResponse(content=Item(name="widget", price=10.0))

    client = TestClient(app)
    response = client.get("/item")
    assert response.status_code == 200
    assert response.json() == {"name": "widget", "price": 10.0, "address": None}


def test_msgspec_and_pydantic_coexist() -> None:
    app = FastAPI()

    @app.post("/pydantic", response_model=PydanticItem)
    def create_pydantic(item: PydanticItem) -> PydanticItem:
        return item

    @app.post("/msgspec", response_model=ItemOut)
    def create_msgspec(item: Item) -> ItemOut:
        return ItemOut(name=item.name, total=item.price * 2)

    client = TestClient(app)

    pydantic_response = client.post("/pydantic", json={"name": "x", "price": 1.0})
    assert pydantic_response.status_code == 200
    assert pydantic_response.json() == {"name": "x", "price": 1.0}

    msgspec_response = client.post("/msgspec", json={"name": "x", "price": 1.0})
    assert msgspec_response.status_code == 200
    assert msgspec_response.json() == {"name": "x", "total": 2.0}


def test_msgspec_openapi_schema() -> None:
    app = FastAPI()

    @app.post("/items", response_model=ItemOut)
    def create_item(item: Item) -> ItemOut:
        return ItemOut(name=item.name, total=item.price * 2)

    schema = app.openapi()
    schemas = schema["components"]["schemas"]

    assert schemas["Item"] == IsDict(
        {
            "properties": {
                "name": {"type": "string"},
                "price": {"type": "number", "default": 0.0},
                "address": {
                    "anyOf": [
                        {"type": "null"},
                        {"$ref": "#/components/schemas/Address"},
                    ]
                },
            },
            "type": "object",
            "required": ["name"],
            "title": "Item",
        }
    )
    assert schemas["Address"] == IsDict(
        {
            "properties": {"city": {"type": "string"}},
            "type": "object",
            "required": ["city"],
            "title": "Address",
        }
    )
    assert schemas["ItemOut"] == IsDict(
        {
            "properties": {
                "name": {"type": "string"},
                "total": {"type": "number"},
            },
            "type": "object",
            "required": ["name", "total"],
            "title": "ItemOut",
        }
    )

    paths = schema["paths"]["/items"]
    assert (
        paths["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        == "#/components/schemas/Item"
    )
    assert (
        paths["post"]["responses"]["200"]["content"]["application/json"]["schema"][
            "$ref"
        ]
        == "#/components/schemas/ItemOut"
    )


def test_msgspec_openapi_list_schema() -> None:
    app = FastAPI()

    @app.post("/items", response_model=list[Item])
    def create_items(items: list[Item]) -> list[Item]:
        return items

    schema = app.openapi()
    response_schema = schema["paths"]["/items"]["post"]["responses"]["200"]["content"][
        "application/json"
    ]["schema"]
    assert response_schema == IsDict(
        {
            "type": "array",
            "items": {"$ref": "#/components/schemas/Item"},
            "title": "Response Create Items Items Post",
        }
    )


def test_msgspec_openapi_alias_schema() -> None:
    app = FastAPI()

    @app.post("/items", response_model=ItemAlias)
    def create_item(item: ItemAlias) -> ItemAlias:
        return item

    schema = app.openapi()
    item_schema = schema["components"]["schemas"]["ItemAlias"]
    assert item_schema["properties"]["itemName"] == IsDict({"type": "string"})
    assert "item_name" not in item_schema["properties"]


class Cat(msgspec.Struct, tag=True):
    meow: str


class Dog(msgspec.Struct, tag=True):
    bark: str


def test_msgspec_tagged_union_request_response() -> None:
    app = FastAPI()

    @app.post("/animals", response_model=Cat | Dog)
    def create_animal(animal: Cat | Dog) -> Cat | Dog:
        return animal

    client = TestClient(app)
    cat_response = client.post("/animals", json={"type": "Cat", "meow": "x"})
    assert cat_response.status_code == 200
    assert cat_response.json() == {"type": "Cat", "meow": "x"}

    dog_response = client.post("/animals", json={"type": "Dog", "bark": "y"})
    assert dog_response.status_code == 200
    assert dog_response.json() == {"type": "Dog", "bark": "y"}


def test_msgspec_tagged_union_openapi_schema() -> None:
    app = FastAPI()

    @app.post("/animals", response_model=Cat | Dog)
    def create_animal(animal: Cat | Dog) -> Cat | Dog:
        return animal

    schema = app.openapi()
    request_schema = schema["paths"]["/animals"]["post"]["requestBody"]["content"][
        "application/json"
    ]["schema"]
    assert request_schema == IsDict(
        {
            "anyOf": [
                {"$ref": "#/components/schemas/Cat"},
                {"$ref": "#/components/schemas/Dog"},
            ],
            "discriminator": {
                "propertyName": "type",
                "mapping": {
                    "Cat": "#/components/schemas/Cat",
                    "Dog": "#/components/schemas/Dog",
                },
            },
            "title": "Animal",
        }
    )


def test_msgspec_response_model_from_dict() -> None:
    app = FastAPI()

    @app.post("/items", response_model=Item)
    def create_item() -> dict[str, Any]:
        return {"name": "widget", "price": 10.0}

    client = TestClient(app)
    response = client.post("/items")
    assert response.status_code == 200
    assert response.json() == {"name": "widget", "price": 10.0, "address": None}


def test_msgspec_special_types_round_trip() -> None:
    import base64
    import datetime
    from decimal import Decimal
    from enum import Enum
    from uuid import UUID, uuid4

    class Color(Enum):
        RED = "red"
        GREEN = "green"

    class SpecialItem(msgspec.Struct):
        created_at: datetime.datetime
        updated_on: datetime.date
        identifier: UUID
        payload: bytes
        amount: Decimal
        color: Color
        mapping: dict[int, str]

    app = FastAPI()

    @app.post("/items", response_model=SpecialItem)
    def create_item(item: SpecialItem) -> SpecialItem:
        return item

    client = TestClient(app)
    uid = uuid4()
    b64_payload = base64.b64encode(b"hello").decode("ascii")
    response = client.post(
        "/items",
        json={
            "created_at": "2026-01-01T12:34:56Z",
            "updated_on": "2026-01-01",
            "identifier": str(uid),
            "payload": b64_payload,
            "amount": "123.45",
            "color": "red",
            "mapping": {"1": "one", "2": "two"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["created_at"] == "2026-01-01T12:34:56Z"
    assert data["updated_on"] == "2026-01-01"
    assert data["identifier"] == str(uid)
    assert data["payload"] == b64_payload
    assert data["amount"] == "123.45"
    assert data["color"] == "red"
    assert data["mapping"] == {"1": "one", "2": "two"}


def test_msgspec_datetime_requires_full_rfc3339() -> None:
    import datetime

    class DatedItem(msgspec.Struct):
        created_at: datetime.datetime

    app = FastAPI()

    @app.post("/items", response_model=DatedItem)
    def create_item(item: DatedItem) -> DatedItem:
        return item

    client = TestClient(app)
    # Pydantic accepts "2026-01-01" for a datetime field; msgspec requires full RFC3339.
    response = client.post("/items", json={"created_at": "2026-01-01"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "msgspec_validation"


def test_msgspec_date_requires_date_only() -> None:
    import datetime

    class DatedItem(msgspec.Struct):
        updated_on: datetime.date

    app = FastAPI()

    @app.post("/items", response_model=DatedItem)
    def create_item(item: DatedItem) -> DatedItem:
        return item

    client = TestClient(app)
    # Pydantic accepts a datetime string for a date field; msgspec requires date-only.
    response = client.post("/items", json={"updated_on": "2026-01-01T12:34:56Z"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "msgspec_validation"


def test_msgspec_bytes_requires_base64() -> None:
    class BinaryItem(msgspec.Struct):
        data: bytes

    app = FastAPI()

    @app.post("/items", response_model=BinaryItem)
    def create_item(item: BinaryItem) -> BinaryItem:
        return item

    client = TestClient(app)
    # Pydantic accepts any string and treats it as UTF-8 bytes; msgspec requires base64.
    response = client.post("/items", json={"data": "hello"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "msgspec_validation"


def test_msgspec_enum_keys_encode_limitation() -> None:
    from enum import Enum

    class Color(Enum):
        RED = "red"
        GREEN = "green"

    class MappedItem(msgspec.Struct):
        mapping: dict[Color, str]

    # msgspec can *decode* JSON string keys into Enum keys, but it cannot
    # *encode* a dict with Enum keys back to JSON. Pydantic handles this
    # round-trip; msgspec raises a TypeError during response serialization,
    # which in FastAPI currently surfaces as an unhandled 500 error.
    obj = MappedItem(mapping={Color.RED: "r", Color.GREEN: "g"})
    with pytest.raises(TypeError, match="str-like or number-like keys"):
        msgspec.json.encode(obj)
