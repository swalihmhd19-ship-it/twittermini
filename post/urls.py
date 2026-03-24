from django.urls import path
from . import views

urlpatterns = [
    path("", views.feed_view, name="feed"),
    path("create/", views.create_post_view, name="create_post"),
    path("<int:post_id>/", views.post_detail_view, name="post_detail"),
    path("<int:post_id>/delete/", views.delete_post_view, name="delete_post"),

    path("<int:post_id>/like/", views.toggle_like_view, name="toggle_like"),
    path("<int:post_id>/reshare/", views.toggle_reshare_view, name="toggle_reshare"),

    path("<int:post_id>/comment/", views.add_comment_view, name="add_comment"),
    path("comment/<int:comment_id>/delete/", views.delete_comment_view, name="delete_comment"),
]