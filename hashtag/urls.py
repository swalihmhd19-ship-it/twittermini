from django.urls import path
from . import views 

urlpatterns = [
    path("<str:tag>/", views.hashtag_posts_view, name="hashtag_posts"),

    path("suggest/", views.hashtag_suggestions, name="hashtag_suggestions"),
]