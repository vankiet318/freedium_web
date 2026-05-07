from pathlib import Path

from fastapi import Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from html5lib import serialize  # type: ignore
from html5lib.html5parser import parse  # type: ignore
from loguru import logger

from server import config
from server.handlers.iframe import iframe_proxy
from server.handlers.miro import miro_proxy
from server.handlers.misc import delete_from_cache, report_problem
from server.handlers.post import render_homepage, render_medium_post_link
from server.services.jinja import base_template, main_template
from server.utils.logger_trace import trace

# Mirrors caddy/static assets for deployments without a reverse proxy (e.g. Railway).
PUBLIC_ROOT = Path(__file__).resolve().parent.parent / "public"


def maybe_public_file_response(rel_path: str) -> FileResponse | None:
    # Only single-segment names under PUBLIC_ROOT; avoids path traversal.
    if not rel_path or "/" in rel_path or "\\" in rel_path or rel_path.startswith("."):
        return None
    candidate = PUBLIC_ROOT / rel_path
    try:
        resolved = candidate.resolve()
        resolved.relative_to(PUBLIC_ROOT.resolve())
    except (ValueError, RuntimeError):
        return None
    if not resolved.is_file():
        return None
    media_type: str | None = None
    if rel_path.endswith(".webmanifest"):
        media_type = "application/manifest+json"
    elif rel_path.endswith(".js"):
        media_type = "application/javascript"
    return FileResponse(path=str(resolved), media_type=media_type)


@trace
async def route_processing(path: str, request: Request):
    if not path:
        return await main_page()

    query_params = request.query_params
    redis = "no-redis" not in query_params
    db_cache = "no-db-cache" not in query_params

    logger.trace(f"no_cache: {db_cache}, no_redis: {redis}")

    path = path.removeprefix("/")

    public_file = maybe_public_file_response(path)
    if public_file is not None:
        return public_file

    url = str(request.url)

    logger.debug(f"Path: {path}, URL: {url}")
    logger.trace(request.url.netloc)
    logger.trace(request.url.scheme)

    url = url.removeprefix(f"{request.url.scheme}://{request.url.netloc}/")
    logger.trace(url)

    if not db_cache or not redis:
        key_data = request.headers.get("ADMIN_SECRET_KEY")

        if key_data != config.ADMIN_SECRET_KEY:
            return JSONResponse({"message": f"Wrong secret key: {key_data}"}, status_code=403)

    if path.startswith("@miro/"):
        miro_data = path.removeprefix("@miro/")
        return await miro_proxy(miro_data)
    if path.startswith("render_iframe/"):
        iframe_id = path.removeprefix("render_iframe/")
        return await iframe_proxy(iframe_id)

    return await render_medium_post_link(url, db_cache, redis)


@trace
async def main_page():
    homepage_template = await render_homepage(as_html=True)
    main_template_rendered = main_template.render(postleter=homepage_template)
    base_template_rendered = base_template.render(
        body_template=main_template_rendered, host_address=config.HOST_ADDRESS
    )
    parsed_template = parse(base_template_rendered)
    serialized_template = serialize(parsed_template, encoding="utf-8")
    return HTMLResponse(serialized_template)


def register_main_router(app):
    app.add_api_route(path="/delete-from-cache", endpoint=delete_from_cache, methods=["POST"])
    app.add_api_route(path="/report-problem", endpoint=report_problem, methods=["POST"])
    app.add_api_route(
        path="/{path:path}",
        endpoint=route_processing,
        methods=["GET", "HEAD"],
        tags=["pages"],
        summary=None,
        description=None,
    )
