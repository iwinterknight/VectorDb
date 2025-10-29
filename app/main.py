# app/main.py
import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.api import libraries, documents, chunks, search
from app.api import indexing
from app.domain.errors import NotFoundError, ConflictError, BadRequestError
from pydantic import ValidationError as PydanticValidationError

def _configure_logging():
    logger = logging.getLogger("vectordb")
    logger.setLevel(logging.INFO)
    # If nothing attached yet, add a simple stream handler
    if not logger.handlers:
        h = logging.StreamHandler()
        fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s - %(message)s")
        h.setFormatter(fmt)
        logger.addHandler(h)
    # Also make sure uvicorn's level isn't hiding ours
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)


def create_app() -> FastAPI:
    _configure_logging()
    app = FastAPI(title="VectorDB (Day 2)")

    # Routers
    app.include_router(libraries.router)
    app.include_router(documents.router)
    app.include_router(chunks.router)
    app.include_router(search.router)
    app.include_router(indexing.router)

    # Exception handlers
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND,
                            content={"error":"NotFound","detail":exc.what})

    @app.exception_handler(ConflictError)
    async def conflict_handler(_: Request, exc: ConflictError):
        return JSONResponse(status_code=status.HTTP_409_CONFLICT,
                            content={"error":"Conflict","detail":exc.detail})

    @app.exception_handler(BadRequestError)
    async def badreq_handler(_: Request, exc: BadRequestError):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={"error":"BadRequest","detail":exc.detail})

    # Optional but helpful: make ValidationError JSON-safe
    @app.exception_handler(PydanticValidationError)
    async def pydantic_validation_handler(_: Request, exc: PydanticValidationError):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=jsonable_encoder({"error":"ValidationError","detail":exc.errors()}),
        )

    return app

# Keep this for non-factory runs (harmless even if you use --factory)
app = create_app()
