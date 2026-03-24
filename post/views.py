from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.db import transaction
from django.db.models import Q
from django.contrib import messages

from .models import Post, PostImage, Like, Comment
from hashtag.utils import extract_hashtags
from hashtag.services import get_trending_hashtags
from user_account.utils_privacy import can_view_user_posts


#==============================================================
#                 Post Views
#==============================================================

#==============================================================
#create Post view
#==============================================================
@login_required
@require_POST
def create_post_view(request):
    content = request.POST.get("content", "").strip()
    parent_id = request.POST.get("parent_id")
    images = request.FILES.getlist("images")

    if not content and not images:
        messages.error(request, "Post cannot be empty.")
        return redirect("feed")

    parent_post = None
    if parent_id:
        parent_post = get_object_or_404(Post, id=parent_id)

    try:
        with transaction.atomic():
            post = Post.objects.create(
                user=request.user,
                content=content,
                parent=parent_post
            )

            for image in images[:4]:  # limit 4 images
                PostImage.objects.create(post=post, image=image)

            # Extract and associate hashtags
            hashtags = extract_hashtags(content)
            post.hashtags.set(hashtags)


        messages.success(request, "Post created successfully.")

    except Exception:
        messages.error(request, "Something went wrong while creating the post.")

    return redirect("feed")

#==============================================================
#Feed View  —  shows new posts since last login first,
#              falls back to recent posts if nothing new.
#==============================================================
@login_required
def feed_view(request):

    following_ids = request.user.following.values_list(
        "following_id", flat=True
    )

    trending_hashtags = get_trending_hashtags()

    posts = Post.objects.filter(
        Q(user=request.user) |
        Q(user_id__in=following_ids),
        is_deleted=False
    ).select_related("user", "parent") \
     .prefetch_related("images", "likes", "comments", "hashtags") \
     .order_by("-created_at")[:40]

    liked_ids = set(
        Like.objects.filter(user=request.user)
        .values_list("post_id", flat=True)
    )

    reshared_ids = set(
        Post.objects.filter(
            user=request.user,
            parent__isnull=False
        ).values_list("parent_id", flat=True)
    )

    return render(request, "index/index.html", {
        "posts": posts,
        "liked_ids": liked_ids,
        "reshared_ids": reshared_ids,
        "has_new": False,
        "new_count": 0,
        "trending_hashtags": trending_hashtags,
    })


#==============================================================
#Post Detail View
#==============================================================
@login_required
def post_detail_view(request, post_id):

    post = get_object_or_404(Post, id=post_id, is_deleted=False)

    if not can_view_user_posts(request.user, post.user):
        messages.error(request, "This account is private.")
        return redirect("index")

    comments = post.comments.filter(
        parent__isnull=True,
        is_deleted=False
    ).select_related("user").prefetch_related("replies")

    liked_ids = set(
        Like.objects.filter(user=request.user)
        .values_list("post_id", flat=True)
    )

    reshared_ids = set(
        Post.objects.filter(
            user=request.user,
            parent__isnull=False
        ).values_list("parent_id", flat=True)
    )

    return render(request, "posts/post_detail.html", {
        "post": post,
        "comments": comments,
        "liked_ids": liked_ids,
        "reshared_ids": reshared_ids,
    })
#==============================================================
#Delete Post View
#==============================================================
@login_required
@require_POST
def delete_post_view(request, post_id):
    post = get_object_or_404(Post, id=post_id, user=request.user)

    post.is_deleted = True
    post.save()

    return redirect(request.META.get("HTTP_REFERER", "feed"))


#==============================================================
#toggle Like View
#==============================================================

@login_required
@require_POST
def toggle_like_view(request, post_id):

    post = get_object_or_404(Post, id=post_id)

    if not can_view_user_posts(request.user, post.user):
        return JsonResponse({
            "success": False,
            "message": "Private account"
        }, status=403)

    like = Like.objects.filter(user=request.user, post=post).first()

    if like:
        like.delete()
        liked = False
    else:
        Like.objects.create(user=request.user, post=post)
        liked = True

    return JsonResponse({
        "success": True,
        "liked": liked,
        "likes_count": post.likes.count()
    })
#==============================================================
#add comment view  — also handles inline feed comments via AJAX
#==============================================================
@login_required
@require_POST
def add_comment_view(request, post_id):

    post = get_object_or_404(Post, id=post_id)

    if not can_view_user_posts(request.user, post.user):
        return JsonResponse({
            "success": False,
            "message": "Private account"
        }, status=403)

    content = request.POST.get("content", "").strip()

    if not content:
        return JsonResponse({
            "success": False,
            "message": "Comment cannot be empty."
        }, status=400)

    comment = Comment.objects.create(
        user=request.user,
        post=post,
        content=content
    )

    return JsonResponse({
        "success": True,
        "comment": {
            "id": comment.id,
            "content": comment.content,
            "username": comment.user.username
        },
        "comments_count": post.comments.count()
    })
#==============================================================
#Delete Comment View
#==============================================================
@login_required
@require_POST
def delete_comment_view(request, comment_id):
    comment = get_object_or_404(Comment, id=comment_id, user=request.user)

    comment.is_deleted = True
    comment.save()

    return JsonResponse({"success": True})

#==============================================================
# toggle Reshare View
#==============================================================
@login_required
@require_POST
def toggle_reshare_view(request, post_id):

    original_post = get_object_or_404(Post, id=post_id)

    if not can_view_user_posts(request.user, original_post.user):
        return JsonResponse({
            "success": False,
            "message": "Private account"
        }, status=403)

    existing = Post.objects.filter(
        user=request.user,
        parent=original_post
    ).first()

    if existing:
        existing.delete()
        reshared = False
    else:
        Post.objects.create(
            user=request.user,
            parent=original_post,
            content=""
        )
        reshared = True

    return JsonResponse({
        "success": True,
        "reshared": reshared,
        "reshares_count": original_post.reshares.count()
    })