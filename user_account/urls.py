from django.urls import path
from . import views

urlpatterns = [
    path('',views.start_page,name = 'start_page'),
    path('send otp/', views.send_otp_view, name='send_otp'),
    path("resend-otp/", views.resend_otp_view, name="resend_otp"),
    path('verify-otp/', views.verify_otp_page, name='verify_otp'),
    path('set-password/', views.set_password_view, name='set_password'),
    path("setup-profile/", views.setup_profile_view, name="setup_profile"),
    path('index/', views.index,name='index'),
    path('signin/', views.login_view,name='login_view'),
    path('logout/',views.logout_view, name='logout_view'),
    path('profile/', views.profile_detail_view, name='my_profile'),
    path('profile/edit/', views.edit_profile_view, name='edit_profile'),
    path('profile/<str:username>/', views.profile_detail_view, name='profile_detail'),
    path("profile/<str:username>/", views.toggle_follow_view, name="toggle_follow"),
    path("<str:username>/followers/", views.followers_list_view, name="followers_list"),
    path("<str:username>/following/", views.following_list_view, name="following_list"),
    path("follow/request/<str:username>/", views.send_follow_request_view, name="follow_user"),
    path("follow-request/<int:request_id>/accept/", views.accept_follow_request_view,),
    path("follow-request/<int:request_id>/reject/", views.reject_follow_request_view,),
    path("follow-request/cancel/<str:username>/", views.cancel_follow_request_view, name="cancel_follow_request"),
    path("follow-requests/", views.follow_requests_view, name="follow_requests_list"),
    

]