from fastapi import APIRouter, FastAPI
from sqlalchemy import text

from app.deps import DbDep
from app.errors import install_error_handlers
from app.routers import auth, projects


def create_app() -> FastAPI:
    app = FastAPI(
        title="TaskFlow API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    install_error_handlers(app)

    api = APIRouter(prefix="/api")
    api.include_router(auth.router)
    api.include_router(projects.router)

    @api.get("/health", tags=["meta"])
    def health(db: DbDep):
        db.execute(text("select 1"))
        return {"status": "ok"}

    app.include_router(api)
    return app


app = create_app()
