from django.db import models

class Hashtag(models.Model):

    name = models.CharField(
        max_length=100, 
        unique=True,
        db_index=True
    )

    posts_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["posts_count"]),
        ]

    def __str__(self):
        return  f"#{self.name}"