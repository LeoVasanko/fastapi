import io
from typing import Any

import tracerite
from starlette._utils import is_async_callable
from starlette.concurrency import run_in_threadpool
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.types import (
    ASGIApp,
    HTTPExceptionHandler,
    Message,
    Receive,
    Scope,
    Send,
)

INGRESS = """This page is shown for your guidance because the application is \
running in debug mode and has crashed handling this request."""


class ServerErrorMiddleware:
    """Return 500 responses when a server error occurs, formatted with TraceRite.

    If 'debug' is set, traceback responses are returned, otherwise any designated
    'handler' returns the response, or an Internal Server Error message is returned.

    If `json` is set, we respect `accept: application/json` to respond in JSON.
    """

    def __init__(
        self,
        app: ASGIApp,
        handler: HTTPExceptionHandler | None = None,
        *,
        debug: bool = False,
        json: bool = True,
    ) -> None:
        self.app = app
        self.handler = handler
        self.debug = debug
        self.json = json

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # This function is directly from Starlette
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        response_started = False

        async def _send(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception as exc:
            request = Request(scope)
            response: Response
            if self.debug:
                response = self.debug_response(request, exc)
            elif self.handler is None:
                response = self.error_response(request, exc)
            elif is_async_callable(self.handler):
                response = await self.handler(request, exc)  # ty: ignore[invalid-assignment]
            else:
                response = await run_in_threadpool(self.handler, request, exc)  # type: ignore

            if not response_started:
                await response(scope, receive, send)

            raise exc

    def generate_html(self, exc: Exception, request: Request | None = None) -> str:
        """Render an HTML traceback page for the given exception."""
        return tracerite.html_page(
            exc,
            title="FastAPI debugger",
            heading="500 Server Error",
            ingress=INGRESS,
        )

    def generate_plain_text(self, exc: Exception) -> str:
        """Render a plain-text traceback for the given exception."""
        buffer = io.StringIO()
        tracerite.tty_traceback(exc, file=buffer)
        return buffer.getvalue()

    def generate_json(self, exc: Exception) -> dict[str, Any]:
        """Render a structured JSON traceback for the given exception."""
        chain = tracerite.extract_chain(exc)
        return {"detail": "Internal Server Error", "traceback": chain}

    def debug_response(self, request: Request, exc: Exception) -> Response:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            content = self.generate_html(exc, request=request)
            return HTMLResponse(content, status_code=500)
        if self.json and "application/json" in accept:
            return JSONResponse(self.generate_json(exc), status_code=500)
        content = self.generate_plain_text(exc)
        return PlainTextResponse(content, status_code=500)

    def error_response(self, request: Request, exc: Exception) -> Response:
        if self.json and "application/json" in request.headers.get("accept", ""):
            return JSONResponse({"detail": "Internal Server Error"}, status_code=500)
        return PlainTextResponse("Internal Server Error", status_code=500)
