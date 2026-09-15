# api/cache_helper.py
import os
import requests
import logging

logger = logging.getLogger(__name__)

VERCEL_DOMAIN = "https://restfullapis-cdn.vercel.app"

CACHE_PATHS = [
    "/api/products/top",
    "/api/products",
    "/api/categories",
    "/api/ads",
]


def purge_vercel_cache(paths: list = None):
    """Purge Vercel CDN cache for specific paths."""
    token = os.getenv("VERCEL_TOKEN")
    if not token:
        logger.warning("VERCEL_TOKEN not set — skipping cache purge")
        return

    paths_to_purge = paths if paths else CACHE_PATHS

    try:
        response = requests.post(
            "https://api.vercel.com/v1/purge-cache",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"paths": paths_to_purge},
            timeout=10,
        )

        if response.status_code in [200, 201, 204]:
            logger.info(f"✅ Vercel cache purged: {paths_to_purge}")
        else:
            logger.warning(f"⚠️ Vercel purge failed: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"❌ Vercel purge exception: {e}")