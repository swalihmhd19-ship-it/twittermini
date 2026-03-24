from django.core.cache import cache
from .models import Hashtag


def get_trending_hashtags(limit=10):

    cache_key = "trending_hashtags"

    trending = cache.get(cache_key)

    if not trending:

        trending = list(
            Hashtag.objects.order_by("-posts_count")[:limit]
        )
        cache.set(cache_key, trending, 300) 

    return trending