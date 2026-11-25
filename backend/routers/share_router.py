"""Open Graph share cards for public restaurant links.

Links shared in WhatsApp groups point to ``/s/<public_id>`` (nginx proxies this
route to the backend). Crawlers get a small HTML page carrying the Open Graph
tags; real visitors are redirected to the SPA experience.

WhatsApp (and most crawlers) never execute JavaScript, so the tags must be
served server-side. The page also self-redirects so that an in-app browser
misdetected as a crawler still lands on the experience.
"""
import html
import json
import logging
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from database import db
from services.attribution import normalize_source

logger = logging.getLogger(__name__)

router = APIRouter(tags=["share"])

# User agents that fetch the page only to build a link preview.
CRAWLER_MARKERS = (
    "whatsapp", "facebookexternalhit", "facebookcatalog", "twitterbot",
    "linkedinbot", "slackbot", "telegrambot", "discordbot", "pinterest",
    "googlebot", "bingbot",
)

DEFAULT_DESCRIPTION = "Commandez en quelques secondes avec notre assistant."


def _frontend_url(request: Request | None = None) -> str:
    """Public frontend origin: FRONTEND_URL, or the proxied request host."""
    configured = (os.environ.get("FRONTEND_URL") or "").strip().rstrip("/")
    if configured:
        return configured
    if request is not None:
        host = request.headers.get("x-forwarded-host") or request.headers.get("host")
        proto = request.headers.get("x-forwarded-proto") or request.url.scheme
        if host:
            return f"{proto}://{host}"
    return ""


def _is_crawler(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    return any(marker in ua for marker in CRAWLER_MARKERS)


def _og_image(restaurant: dict, base: str) -> str:
    logo = (restaurant.get("logo") or "").strip()
    if logo.startswith(("http://", "https://")):
        return logo
    return f"{base}/og-default.png" if base else ""


def _experience_url(base: str, public_id: str, source: str) -> str:
    target = f"{base}/experience/{public_id}"
    return f"{target}?src={source}" if source != "direct" else target


def _not_found_page() -> str:
    return (
        "<!doctype html><html lang=\"fr\"><head><meta charset=\"utf-8\">"
        "<meta name=\"robots\" content=\"noindex\"><title>Lien indisponible</title></head>"
        "<body style=\"font-family:system-ui;padding:2rem;text-align:center\">"
        "<p>Ce lien n'est plus disponible.</p></body></html>"
    )


def _share_page(title: str, description: str, image: str, url: str, target: str) -> str:
    esc = html.escape
    image_tag = f'<meta property="og:image" content="{esc(image)}" />' if image else ""
    image_alt = '<meta property="og:image:alt" content="Logo du restaurant" />' if image else ""
    # JSON-encoded for the inline script; "<" is escaped so the payload can
    # never close the <script> tag (public IDs are user-controlled path data).
    script_target = json.dumps(target).replace("<", "\\u003c")
    return f"""<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}" />
<link rel="canonical" href="{esc(target)}" />
<meta property="og:type" content="website" />
<meta property="og:site_name" content="MenuMind" />
<meta property="og:title" content="{esc(title)}" />
<meta property="og:description" content="{esc(description)}" />
<meta property="og:url" content="{esc(url)}" />
{image_tag}
{image_alt}
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="{esc(title)}" />
<meta name="twitter:description" content="{esc(description)}" />
<script>window.location.replace({script_target});</script>
<noscript><meta http-equiv="refresh" content="0; url={esc(target)}" /></noscript>
</head>
<body style="font-family:system-ui;padding:2rem;text-align:center">
<p>Redirection vers <a href="{esc(target)}">{esc(title)}</a>…</p>
</body>
</html>"""


@router.get("/share/{public_id}", include_in_schema=False)
async def share_card(public_id: str, request: Request):
    """Open Graph card for ``/s/<public_id>`` links shared on social channels."""
    base = _frontend_url(request)
    source = normalize_source(request.query_params.get("src"))
    target = _experience_url(base, public_id, source)

    doc = await db.restaurants.find_one({"public_id": public_id, "status": "active"})
    if not doc:
        return HTMLResponse(_not_found_page(), status_code=404)

    if not _is_crawler(request.headers.get("user-agent", "")):
        return RedirectResponse(target, status_code=302)

    name = (doc.get("name") or "").strip() or "Votre restaurant"
    description = (doc.get("description") or "").strip()[:160] or DEFAULT_DESCRIPTION
    title = f"Commandez chez {name}"
    image = _og_image(doc, base)
    url = f"{base}/s/{public_id}"
    if source != "direct":
        url = f"{url}?src={source}"

    page = _share_page(title, description, image, url, target)
    return HTMLResponse(page, headers={"Cache-Control": "public, max-age=300"})
