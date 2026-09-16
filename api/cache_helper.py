# api/cache_helper.py
import os
import requests
import logging

logger = logging.getLogger(__name__)

# ✅ Your Vercel project name (matches restfullapis-cdn.vercel.app)
VERCEL_PROJECT_NAME = "restfullapis-cdn"

# ✅ Cache tags to invalidate (these must match Vercel-Cache-Tag headers)
CACHE_TAGS = [
    "products",
    "categories",
    "ads",
]


def purge_vercel_cache(tags: list = None):
    """
    Invalidate Vercel CDN cache by tag.
    On Hobby plan, path-based purge returns 404. Tag-based invalidation
    is the supported method on all plans.
    """
    token = os.getenv("VERCEL_TOKEN")
    if not token:
        logger.warning("VERCEL_TOKEN not set — skipping cache purge")
        return

    tags_to_purge = tags if tags else CACHE_TAGS

    try:
        # ✅ CORRECT endpoint for tag-based invalidation
        response = requests.post(
            f"https://api.vercel.com/v1/edge-cache/invalidate-by-tags?projectIdOrName={VERCEL_PROJECT_NAME}",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={
                "tags": tags_to_purge,
                "target": "production",
            },
            timeout=10,
        )

        if response.status_code in [200, 201, 204]:
            logger.info(f"✅ Vercel cache invalidated by tags: {tags_to_purge}")
        else:
            logger.warning(f"⚠️ Vercel purge failed: {response.status_code} - {response.text}")

    except Exception as e:
        logger.error(f"❌ Vercel purge exception: {e}")