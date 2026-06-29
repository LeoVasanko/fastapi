import importlib

import pytest
from fastapi.testclient import TestClient

from tests.utils import needs_py310


@pytest.fixture(
    name="client",
    params=[
        pytest.param("tutorial002_py310", marks=needs_py310),
    ],
)
def get_client(request: pytest.FixtureRequest) -> TestClient:
    mod = importlib.import_module(f"docs_src.msgspec.{request.param}")

    client = TestClient(mod.app)
    client.headers.clear()
    return client


def test_post_item(client: TestClient) -> None:
    response = client.post("/items/", json={"name": "Foo", "price": 3.0, "tax": 0.5})
    assert response.status_code == 200, response.text
    assert response.text == "We got Item(name='Foo', price=3.0, description=None, tax=0.5)"
