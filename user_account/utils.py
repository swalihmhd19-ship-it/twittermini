import random
import time
from django.conf import settings
from django.core.mail import send_mail


def generate_and_send_otp(email, request):
    # Generate a random 6-digit OTP
    otp = str(random.randint(100000, 999999))

    # Save OTP, email, and current time directly in session
    request.session['otp'] = otp
    request.session['otp_email'] = email
    request.session['otp_time'] = time.time()   # current time in seconds

    # Send OTP to user's email
    send_mail(
        subject="Your Twitter Mini Verification Code",
        message=f"Your verification code is: {otp}\n\nThis code expires in 10 minutes.",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def verify_otp(request, submitted_otp):
    # Get OTP data from session
    otp         = request.session.get('otp')
    otp_email   = request.session.get('otp_email')
    otp_time    = request.session.get('otp_time')

    # Check if OTP exists in session
    if not otp:
        return False, "OTP expired or not found. Please try again."

    # Check if 10 minutes have passed
    time_passed = time.time() - otp_time          # difference in seconds
    if time_passed > 10 * 60:                     # 10 minutes = 600 seconds
        del request.session['otp']
        return False, "OTP has expired. Please request a new one."

    # Check if OTP matches
    if submitted_otp.strip() != otp:
        return False, "Wrong OTP. Please try again."

    # OTP is correct — clear it from session so it can't be reused
    del request.session['otp']
    del request.session['otp_email']
    del request.session['otp_time']

    return True, "ok"