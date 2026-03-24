from django.db import models
from django.conf import settings

class Post(models.Model):
    """
    Core Post model.
    Supports:
    - Original post
    - Reshare (retweet style)
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='posts'
    )

    content = models.TextField(max_length=280, blank=True)

    hashtags = models.ManyToManyField(
        'hashtag.Hashtag',
        blank=True,
        related_name='posts'
    )

    # For reshare support
    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='reshares'
    )

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['created_at']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f"{self.user} - {self.content[:30]}"

    # -------- Counts --------
    def likes_count(self):
        return self.likes.count()

    def comments_count(self):
        return self.comments.filter(parent__isnull=True).count()

    def reshares_count(self):
        return self.reshares.count()

    @property
    def is_reshare(self):
        return self.parent is not None
    

class PostImage(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='images'
    )

    image = models.ImageField(
        upload_to='posts/images/'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=['post']),
        ]

    def __str__(self):
        return f"Image for Post {self.post.id}"
    


class Like(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='likes'
    )

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='likes'
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'post'],
                name='unique_like_per_user'
            )
        ]
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['post']),
        ]

    def __str__(self):
        return f"{self.user} liked {self.post.id}"
    


class Comment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='comments'
    )

    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name='comments'
    )

    content = models.TextField(max_length=500)

    parent = models.ForeignKey(
        'self',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='replies'
    )

    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['post']),
            models.Index(fields=['user']),
            models.Index(fields=['parent']),
        ]

    def __str__(self):
        return f"{self.user} commented on {self.post.id}"
