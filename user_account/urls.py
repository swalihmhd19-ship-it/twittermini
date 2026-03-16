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

]