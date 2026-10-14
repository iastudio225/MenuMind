from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

WIDGET_DIR = Path(__file__).parent.parent / "static" / "widget"

router = APIRouter(tags=["embed"])


@router.get("/widget.js", include_in_schema=False)
async def widget_js():
    return FileResponse(WIDGET_DIR / "widget.js", media_type="application/javascript; charset=utf-8")


@router.get("/widget-frame.html", include_in_schema=False)
async def widget_frame():
    return FileResponse(WIDGET_DIR / "widget-frame.html", media_type="text/html; charset=utf-8")
