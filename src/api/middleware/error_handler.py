# src/api/middleware/error
from __future__ import annotations
from typing import Any, Dict
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_422_UNPROCESSABLE_ENTITY, HTTP_500_INTERNAL_SERVER_ERROR
from src.logging_conf import get_logger

logger = get_logger(__name__)

# Si ya tienes PipelineError en otro módulo, impórtalo.
try:
    from src.orchestration.runner import PipelineError
except Exception:
    class PipelineError(RuntimeError):
        code: str = "INTERNAL"
        def __init__(self, message: str, code: str = "INTERNAL", details: dict | None = None):
            super().__init__(message)
            self.code = code
            self.details = details or {}

class ErrorMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response

        except RequestValidationError as e:
            payload = {"error": {"code": "BAD_REQUEST", "message": "Validación de entrada fallida.", "details": e.errors()}}
            return JSONResponse(status_code=HTTP_422_UNPROCESSABLE_ENTITY, content=payload)

        except PipelineError as e:
            status = HTTP_500_INTERNAL_SERVER_ERROR
            if e.code in ("BAD_REQUEST", "AUTH_ERROR", "NOT_FOUND"):
                status = HTTP_400_BAD_REQUEST
            elif e.code in ("PROHIBITED_CONTENT",):
                status = HTTP_422_UNPROCESSABLE_ENTITY

            logger.exception("PipelineError: code=%s msg=%s details=%s", e.code, str(e), e.details)
            return JSONResponse(status_code=status, content={"error": {"code": e.code, "message": str(e), "details": e.details}})

        except Exception as e:
            logger.exception("Unhandled error: %s", e)
            return JSONResponse(
                status_code=HTTP_500_INTERNAL_SERVER_ERROR,
                content={"error": {"code": "INTERNAL", "message": "Error interno del servidor.", "details": {}}}
            )

def register_exception_handlers(app) -> None:
    # Si prefieres, además del middleware puedes registrar handlers específicos.
    app.add_middleware(ErrorMiddleware)
