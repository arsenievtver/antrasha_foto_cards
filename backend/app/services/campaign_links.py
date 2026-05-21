from urllib.parse import urlencode, urljoin

from app.config import settings
from app.models.marketing_campaign import MarketingCampaign


def normalize_campaign_path(path: str) -> str:
    p = (path or "/").strip()
    if not p.startswith("/"):
        p = f"/{p}"
    if len(p) > 200:
        raise ValueError("path слишком длинный")
    return p


def build_tracking_url(campaign: MarketingCampaign) -> str:
    base = settings.public_app_url.rstrip("/")
    path = normalize_campaign_path(campaign.path)
    url = urljoin(f"{base}/", path.lstrip("/"))
    q = urlencode({"ref": campaign.slug})
    sep = "&" if "?" in url else "?"
    return f"{url}{sep}{q}"
