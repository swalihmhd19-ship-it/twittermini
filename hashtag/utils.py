import re
from .models import Hashtag


HASHTAG_PATTERN = r"#(\w+)"


def extract_hashtags(content):

    tags = re.findall(HASHTAG_PATTERN, content.lower())

    hashtag_objects = []

    for tag in set(tags):

        hashtag, created = Hashtag.objects.get_or_create(name=tag)

        if not created:
            hashtag.posts_count += 1 
            hashtag.save(update_fields=["posts_count"])

        else:
            hashtag.posts_count = 1
            hashtag.save()

        hashtag_objects.append(hashtag)

    return hashtag_objects