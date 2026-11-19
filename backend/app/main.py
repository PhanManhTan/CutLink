import logging

from fastapi import Depends, FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import auth, health, links
from app.auth import current_user
from app.config import get_settings
from app.not_found import unavailable_link
from app.schemas import UserOut

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
settings = get_settings()
app = FastAPI(title="Cutlink", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(StarletteHTTPException)
async def missing_short_link(request: Request, exc: StarletteHTTPException):
    if exc.status_code == 404 and request.url.path.startswith("/r/"):
        return unavailable_link()
    return await http_exception_handler(request, exc)


@app.middleware("http")
async def browser_security(request: Request, call_next):
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        if request.headers.get("origin") not in settings.allowed_origins:
            return JSONResponse(
                {"detail": "Origin is not allowed"},
                status_code=403,
                headers={"Cache-Control": "no-store"},
            )
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    if request.url.path.startswith(("/api/", "/r/")):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(SQLAlchemyError)
async def database_unavailable(request: Request, exc: SQLAlchemyError):
    logging.getLogger(__name__).error("Database operation failed", exc_info=exc)
    return JSONResponse({"detail": "Database temporarily unavailable"}, status_code=503)


app.include_router(auth.router)
app.include_router(links.router)
app.include_router(health.router)


@app.get("/api/auth/me", response_model=UserOut, tags=["auth"])
def me(user=Depends(current_user)):
    return user
