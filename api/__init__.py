"""One router per place; shared launch-token boundary and SPA serving."""
import secrets
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

from . import market, sources

router = APIRouter()
router.include_router(sources.router)
router.include_router(market.router)


def install(app: FastAPI, dist: Path, token: str | None = None):
    launch_token = token or secrets.token_urlsafe(32)
    app.include_router(router, prefix='/api')

    @app.middleware('http')
    async def token_boundary(request: Request, call_next):
        # Every /api write needs the token, whatever its method. NiceGUI's internal transport and
        # authenticated launcher endpoints keep their existing protocols.
        if request.method not in ('GET', 'HEAD', 'OPTIONS') and request.url.path.startswith('/api'):
            supplied = request.headers.get('X-Brownstone-Token', '')
            if not secrets.compare_digest(supplied, launch_token):
                return JSONResponse({'detail': 'Missing or invalid launch token.'}, status_code=403)
        return await call_next(request)

    @app.get('/app/{path:path}', include_in_schema=False)
    @app.get('/app', include_in_schema=False)
    def web(path: str = ''):
        candidate = (dist / path).resolve()
        if path and candidate.is_relative_to(dist.resolve()) and candidate.is_file():
            return FileResponse(candidate)
        index = dist / 'index.html'
        if not index.exists():
            return HTMLResponse('Web app unavailable. Run npm ci and npm run build in web/. '
                                '<a href="/">Open Brownstone</a>', status_code=503)
        html = index.read_text(encoding='utf-8').replace(
            '<!-- brownstone-token -->', f'<meta name="brownstone-token" content="{launch_token}">')
        return HTMLResponse(html, headers={'Cache-Control': 'no-store'})


def schema():
    """Stable schema export without starting NiceGUI or reading local data."""
    app = FastAPI()
    app.include_router(router, prefix='/api')
    return jsonable_encoder(app.openapi())
