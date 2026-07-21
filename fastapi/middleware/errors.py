from __future__ import annotations

import io
from typing import Any

import tracerite
from starlette.middleware.errors import (
    ServerErrorMiddleware as StarletteServerErrorMiddleware,
)
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from starlette.types import ASGIApp, ExceptionHandler

INGRESS = (
    "This page is shown for your guidance because the application is "
    "running in debug mode and has crashed handling this request."
)


class ServerErrorMiddleware(StarletteServerErrorMiddleware):
    """
    A drop in replacement for Starlette's ServerErrorMiddleware, with TraceRite
    formatting for the error responses.

    Handles returning 500 responses when a server error occurs.

    If 'debug' is set, then traceback responses will be returned,
    otherwise the designated 'handler' will be called.

    This middleware class should generally be used to wrap *everything*
    else up, so that unhandled exceptions anywhere in the stack
    always result in an appropriate 500 response.
    """

    def __init__(
        self,
        app: ASGIApp,
        handler: ExceptionHandler | None = None,
        debug: bool = False,
        json: bool = False,
    ) -> None:
        super().__init__(app, handler=handler, debug=debug)
        self.json = json

    def generate_html(
        self,
        exc: Exception,
        limit: int = 7,
        request: Request | None = None,
    ) -> str:
        """Render an HTML traceback page for the given exception.

        ``limit`` is accepted for signature compatibility with Starlette's
        implementation but is unused: TraceRite determines the relevant
        context to show internally, so no frame limit is needed.
        """
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
        return {
            "detail": "Internal Server Error",
            "traceback": chain,
        }

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
