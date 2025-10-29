from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi import status
from app.api import libraries, documents, chunks, search
from app.domain.errors import NotFoundError, ConflictError, BadRequestError

def create_app() -> FastAPI:
    app = FastAPI(title="VectorDB (Day 1)")

    # Routers
    app.include_router(libraries.router)
    app.include_router(documents.router)
    app.include_router(chunks.router)
    app.include_router(search.router)

    # Exception handlers
    @app.exception_handler(NotFoundError)
    async def not_found_handler(_: Request, exc: NotFoundError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "NotFound", "detail": exc.what},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(_: Request, exc: ConflictError):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"error": "Conflict", "detail": exc.detail},
        )

    @app.exception_handler(BadRequestError)
    async def badreq_handler(_: Request, exc: BadRequestError):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "BadRequest", "detail": exc.detail},
        )

    # Last-resort KeyError → 404 (from repo lookups)
    @app.exception_handler(KeyError)
    async def keyerror_to_404(_: Request, exc: KeyError):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "NotFound", "detail": f"{exc.args[0]} not found"},
        )

    return app

app = create_app()
