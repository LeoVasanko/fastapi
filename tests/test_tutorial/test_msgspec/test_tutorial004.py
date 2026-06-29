import importlib

import pytest
from fastapi.testclient import TestClient

from tests.utils import needs_py310


@pytest.fixture(
    name="client",
    params=[
        pytest.param("tutorial004_py310", marks=needs_py310),
    ],
)
def get_client(request: pytest.FixtureRequest) -> TestClient:
    mod = importlib.import_module(f"docs_src.msgspec.{request.param}")

    client = TestClient(mod.app)
    client.headers.clear()
    return client


def test_get_library(client: TestClient) -> None:
    response = client.get("/libraries/")
    assert response.status_code == 200, response.text
    assert response.json() == {
        "name": "Central Library",
        "books": [
            {"title": "1984", "author": {"name": "George Orwell"}},
            {"title": "Brave New World", "author": {"name": "Aldous Huxley"}},
        ],
        "address": "Main Street",
    }
