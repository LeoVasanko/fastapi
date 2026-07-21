from fastapi import FastAPI
from fastapi.middleware.errors import ServerErrorMiddleware
from fastapi.testclient import TestClient


async def asgi_app(scope, receive, send):
    raise RuntimeError("boom")


def get_client(**middleware_kwargs) -> TestClient:
    return TestClient(
        ServerErrorMiddleware(asgi_app, **middleware_kwargs),
        raise_server_exceptions=False,
    )


def test_debug_mode_through_fastapi_app():
    debug_app = FastAPI(debug=True)

    @debug_app.get("/")
    def broken_debug():
        raise RuntimeError("boom")

    client = TestClient(debug_app, raise_server_exceptions=False)
    response = client.get("/", headers={"accept": "text/html"})
    assert response.status_code == 500, response.text
    assert response.headers["content-type"].startswith("text/html")
    assert "FastAPI debugger" in response.text
    assert "RuntimeError" in response.text


def test_debug_html_response():
    client = get_client(debug=True)
    response = client.get("/", headers={"accept": "text/html"})
    assert response.status_code == 500, response.text
    assert response.headers["content-type"].startswith("text/html")
    assert "RuntimeError" in response.text


def test_debug_plain_text_response():
    client = get_client(debug=True)
    response = client.get("/")
    assert response.status_code == 500, response.text
    assert response.headers["content-type"].startswith("text/plain")
    assert "RuntimeError" in response.text


def test_debug_json_response():
    client = get_client(debug=True, json=True)
    response = client.get("/", headers={"accept": "application/json"})
    assert response.status_code == 500, response.text
    data = response.json()
    assert data["detail"] == "Internal Server Error"
    assert "RuntimeError" in data["traceback"]["header"]


def test_error_response():
    client = get_client()
    response = client.get("/")
    assert response.status_code == 500, response.text
    assert response.text == "Internal Server Error"


def test_error_json_response():
    client = get_client(json=True)
    response = client.get("/", headers={"accept": "application/json"})
    assert response.status_code == 500, response.text
    assert response.json() == {"detail": "Internal Server Error"}
