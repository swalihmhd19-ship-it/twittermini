from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth import login, logout
from django.urls import reverse
from django.views.decorators.http import require_POST, require_http_methods
from django.db import transaction
from django.db.models import Q
from django.contrib.auth import authenticate
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.http import JsonResponse,HttpResponse

from .utils import generate_and_send_otp, verify_otp
from .models import *
from post.views import feed_view


from datetime import datetime, timedelta
import uuid
import random
import re
from post.models import Post, Like, Comment


# ============================================================
# CONSTANTS
# ============================================================

OTP_RESEND_TIMEOUT = 30
OTP_EXPIRY_TIME = 300
OTP_MAX_ATTEMPTS = 5

MINIMUM_AGE = 13
MAXIMUM_AGE = 120


# ============================================================
# USERNAME GENERATOR
# ============================================================

def generate_unique_username(email):
    base = email.split("@")[0][:20]
    for _ in range(10):
        username = f"{base}{random.randint(1000,9999)}"
        if not CustomUser.objects.filter(username=username).exists():
            return username
    return f"user_{uuid.uuid4().hex[:10]}"


# ============================================================
# START PAGE
# ============================================================

def start_page(request):
    if request.user.is_authenticated:
        if request.user.has_usable_password():
            return redirect("index")
        return redirect("set_password")
    return render(request, 'auth/start_page.html')


# ============================================================
# INDEX
# ============================================================
@login_required
def index(request):
    return feed_view(request)


# ============================================================
# SEND OTP
# ============================================================

@require_POST
def send_otp_view(request):
    name  = request.POST.get("name",  "").strip()
    email = request.POST.get("email", "").strip()
    month = request.POST.get("month")
    day   = request.POST.get("day")
    year  = request.POST.get("year")

    if not all([name, email, month, day, year]):
        messages.error(request, "All fields required.")
        return redirect("start_page")

    try:
        validate_email(email)
    except ValidationError:
        messages.error(request, "Invalid email.")
        return redirect("start_page")

    if CustomUser.objects.filter(email=email).exists():
        messages.error(request, "Email already registered.")
        return redirect("start_page")

    try:
        dob_date = datetime(int(year), int(month), int(day)).date()
        today = timezone.now().date()
        min_allowed = today - timedelta(days=365 * MINIMUM_AGE)
        max_allowed = today - timedelta(days=365 * MAXIMUM_AGE)
        if not (max_allowed < dob_date < min_allowed):
            messages.error(request, "Invalid date of birth.")
            return redirect("start_page")
    except ValueError:
        messages.error(request, "Invalid date.")
        return redirect("start_page")

    dob = dob_date.isoformat()

    last_sent = request.session.get("otp_timestamp", 0)
    now = timezone.now().timestamp()
    if now - last_sent < OTP_RESEND_TIMEOUT:
        remaining = int(OTP_RESEND_TIMEOUT - (now - last_sent))
        messages.warning(request, f"Wait {remaining} seconds before requesting OTP.")
        return redirect("start_page")

    request.session["reg_name"]      = name
    request.session["reg_email"]     = email
    request.session["reg_dob"]       = dob
    request.session["otp_timestamp"] = now
    request.session["otp_attempts"]  = 0

    generate_and_send_otp(email, request)
    messages.success(request, "OTP sent.")
    return redirect("verify_otp")


# ============================================================
# VERIFY OTP
# ============================================================

@require_http_methods(["GET", "POST"])
def verify_otp_page(request):
    purpose = request.session.get("otp_purpose")

    if purpose == "password_reset":
        email = request.session.get("reset_email")
    else:
        email = request.session.get("reg_email")

    if not email:
        messages.error(request, "Session expired.")
        return redirect("start_page")

    otp_time = request.session.get("otp_timestamp")
    if not otp_time or timezone.now().timestamp() - otp_time > OTP_EXPIRY_TIME:
        request.session.flush()
        messages.error(request, "OTP expired.")
        return redirect("start_page")

    if request.method == "POST":
        attempts = request.session.get("otp_attempts", 0)
        if attempts >= OTP_MAX_ATTEMPTS:
            request.session.flush()
            messages.error(request, "Too many attempts.")
            return redirect("start_page")

        user_otp = request.POST.get("otp")
        valid, message = verify_otp(request, user_otp)

        if not valid:
            request.session["otp_attempts"] = attempts + 1
            messages.error(request, message)
            return redirect("verify_otp")
        
        purpose = request.session.get("otp_purpose")

        if purpose == "password_reset":
            request.session["otp_verified"] = True
            return redirect("password_reset_set")


        if CustomUser.objects.filter(email=email).exists():
            messages.error(request, "Account already exists.")
            return redirect("start_page")

        name = request.session.get("reg_name")
        dob  = request.session.get("reg_dob")
        username = generate_unique_username(email)

        try:
            with transaction.atomic():
                user = CustomUser.objects.create_user(
                    username=username,
                    email=email,
                    dob=dob,
                    password=None
                )
                user.first_name = name
                user.is_active  = True
                user.save()
        except Exception:
            messages.error(request, "Error creating account.")
            return redirect("start_page")

        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.cycle_key()

        for key in ["reg_name", "reg_email", "reg_dob", "otp_timestamp", "otp_attempts"]:
            request.session.pop(key, None)

        messages.success(request, "Account created.")
        return redirect("set_password")

    remaining_time = max(0, int(OTP_RESEND_TIMEOUT - (timezone.now().timestamp() - otp_time)))
    return render(request, "auth/verify_otp.html", {"remaining_time": remaining_time})


@require_POST
def resend_otp_view(request):
    email = request.session.get("reg_email")
    if not email:
        messages.error(request, "Session expired.")
        return redirect("start_page")

    last_sent = request.session.get("otp_timestamp", 0)
    now = timezone.now().timestamp()

    if now - last_sent < OTP_RESEND_TIMEOUT:
        remaining = int(OTP_RESEND_TIMEOUT - (now - last_sent))
        messages.warning(request, f"Wait {remaining} seconds.")
        return redirect("verify_otp")

    generate_and_send_otp(email, request)
    request.session["otp_timestamp"] = now
    messages.success(request, "OTP resent.")
    return redirect("verify_otp")

#=====================================
# PASSWORD VALLIDATION
# ====================================

def is_password_valid(password):
    if len(password) < 8:             return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"[0-9]", password): return False
    if not re.search(r"[^A-Za-z0-9]", password): return False
    return True

# ===================================
# SET PASSWORD
# ===================================

@login_required(login_url="start_page")
def set_password_view(request):
    user = request.user
    if user.has_usable_password():
        return redirect("setup_profile")

    if request.method == "POST":
        password = request.POST.get("password")
        confirm  = request.POST.get("confirm_password")

        if not password or not confirm:
            messages.error(request, "All fields required.")
            return render(request, "auth/set_password.html")

        if password != confirm:
            messages.error(request, "Passwords do not match.")
            return render(request, "auth/set_password.html")

        if not is_password_valid(password):
            messages.error(request, "Password must include uppercase, lowercase, number, symbol.")
            return render(request, "auth/set_password.html")

        try:
            validate_password(password, user)
        except ValidationError as e:
            messages.error(request, e.messages[0])
            return render(request, "auth/set_password.html")

        try:
            with transaction.atomic():
                user.set_password(password)
                user.save()
                login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        except Exception:
            messages.error(request, "Error setting password.")
            return render(request, "auth/set_password.html")

        request.session.cycle_key()
        messages.success(request, "Password set successfully.")
        return redirect("setup_profile")

    return render(request, "auth/set_password.html", {
    "form_action": reverse("set_password"),
    "title": "Set your password"
})



# ============================================================
# PROFILE SETUP VIEW
# ============================================================

@login_required(login_url="start_page")
@require_http_methods(["GET", "POST"])
def setup_profile_view(request):
    user = request.user

    if request.method == "POST":
        display_name = request.POST.get("display_name", "").strip()
        username     = request.POST.get("username", "").strip()
        bio          = request.POST.get("bio", "").strip()
        avatar       = request.FILES.get("avatar")

        if not display_name:
            messages.error(request, "Display name is required.")
            return render(request, "auth/profile_setup.html")

        if not username:
            messages.error(request, "Username is required.")
            return render(request, "auth/profile_setup.html")

        if len(username) < 3:
            messages.error(request, "Username must be at least 3 characters.")
            return render(request, "auth/profile_setup.html")

        if not re.match(r'^[A-Za-z0-9_]+$', username):
            messages.error(request, "Username can only contain letters, numbers, and underscore.")
            return render(request, "auth/profile_setup.html")

        if CustomUser.objects.filter(username__iexact=username).exclude(id=user.id).exists():
            messages.error(request, "This username is already taken. Please choose another.")
            return render(request, "auth/profile_setup.html")

        try:
            with transaction.atomic():
                user.first_name = display_name
                user.username   = username
                user.bio        = bio
                if avatar:
                    if user.profile_picture:
                        user.profile_picture.delete(save=False)
                    user.profile_picture = avatar
                user.save()
        except Exception:
            messages.error(request, "Something went wrong.")
            return render(request, "auth/profile_setup.html")

        messages.success(request, "Profile setup completed.")
        return redirect("index")

    return render(request, "auth/profile_setup.html")




# ============================================================
# LOGIN VIEW
# ============================================================

@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        if request.user.has_usable_password():
            return redirect("index")
        return redirect("set_password")

    if request.method == "POST":
        identifier = request.POST.get("identifier", "").strip()
        password   = request.POST.get("password", "")

        if not identifier or not password:
            messages.error(request, "Please enter both identifier and password.")
            return render(request, "auth/signin.html")

        user = CustomUser.objects.filter(
            Q(email__iexact=identifier) | Q(username__iexact=identifier)
        ).first()

        if not user:
            messages.error(request, "User not found.")
            return render(request, "auth/signin.html")

        authenticated_user = authenticate(request, username=user.username, password=password)

        if authenticated_user is None:
            messages.error(request, "Invalid password.")
            return render(request, "auth/signin.html")

        if not authenticated_user.is_active:
            messages.error(request, "Account is inactive.")
            return render(request, "auth/signin.html")

        login(request, authenticated_user, backend="django.contrib.auth.backends.ModelBackend")
        request.session.cycle_key()
        messages.success(request, "Logged in successfully.")
        return redirect("index")

    return render(request, "auth/signin.html")

# ====================================
# LOGOUT VIEW
# ====================================

@login_required(login_url="start_page")
@require_POST
def logout_view(request):
    logout(request)
    request.session.flush()
    messages.success(request, "you have been logged out successfully.")
    return redirect("start_page")

# ============================================================
# PROFILE DETAIL VIEW
# ============================================================
         
@login_required(login_url="start_page")
def profile_detail_view(request, username=None):
    if username:
        profile_user = get_object_or_404(CustomUser, username=username)
    else:
        profile_user = request.user

    is_following = False
    if request.user.is_authenticated and request.user != profile_user:
        is_following = profile_user.followers.filter(follower=request.user).exists()

    # Privacy check for private accounts
    if profile_user.is_private and profile_user != request.user:
        if not is_following:
            context = {
                "profile_user": profile_user,
                "is_following": False,
                "followers_count": profile_user.followers.count(),
                "following_count": profile_user.following.count(),
                "is_own_profile": request.user == profile_user,

                # empty data
                "posts": [],
                "replies": [],
                "media_posts": [],
                "liked_posts": [],

                "viewer_liked_ids": set(),
                "viewer_reshared_ids": set(),
            }

            return render(request, "profile/profile_detail.html", context)

    # ── Posts (original posts + reshares, excluding deleted) ──
    posts = Post.objects.filter(
        user=profile_user,
        is_deleted=False
    ).select_related("user", "parent").prefetch_related("images", "likes", "comments").order_by("-created_at")

    # ── Replies (comments made by this user on other posts) ──
    replies = Comment.objects.filter(
        user=profile_user,
        is_deleted=False,
        parent__isnull=True          # top-level replies only
    ).select_related("user", "post", "post__user").order_by("-created_at")

    # ── Media (posts that have at least one image) ──
    media_posts = Post.objects.filter(
        user=profile_user,
        is_deleted=False,
        images__isnull=False         # has at least one PostImage
    ).distinct().select_related("user").prefetch_related("images").order_by("-created_at")

    # ── Likes (posts this user has liked) ──
    liked_posts = Post.objects.filter(
        likes__user=profile_user,
        is_deleted=False
    ).select_related("user").prefetch_related("images", "likes").order_by("-likes__created_at")

    # ── Viewer's interaction sets (for like/reshare state) ──
    viewer_liked_ids    = set(Like.objects.filter(user=request.user).values_list("post_id", flat=True))
    viewer_reshared_ids = set(
        Post.objects.filter(user=request.user, parent__isnull=False).values_list("parent_id", flat=True)
    )

    has_pending_request = FollowRequest.objects.filter(
    sender=request.user,
    receiver=profile_user
).exists()
    
    is_locked = profile_user.is_private and request.user != profile_user and not is_following


    context = {
        "profile_user":       profile_user,
        "is_following":       is_following,
        "followers_count":    profile_user.followers.count(),
        "following_count":    profile_user.following.count(),
        "is_own_profile":     request.user == profile_user,
        # tab data
        "posts":              posts,
        "replies":            replies,
        "media_posts":        media_posts,
        "liked_posts":        liked_posts,
        # viewer interaction state
        "viewer_liked_ids":    viewer_liked_ids,
        "viewer_reshared_ids": viewer_reshared_ids,
        "has_pending_request": has_pending_request,
        "is_locked": is_locked,
    }

    return render(request, "profile/profile_detail.html", context)
# ============================================================
# EDIT PROFILE VIEW
# ============================================================

@login_required(login_url="start_page")
@require_http_methods(["GET", "POST"])
def edit_profile_view(request):
    user = request.user

    if request.method == "POST":
        display_name = request.POST.get("display_name", "").strip()
        username     = request.POST.get("username", "").strip()
        bio          = request.POST.get("bio", "").strip()
        avatar       = request.FILES.get("avatar")
        banner       = request.FILES.get("banner")
        is_private   = request.POST.get("is_private") == "on"

        if not display_name:
            messages.error(request, "Display name required.")
            return redirect("edit_profile")

        if len(username) < 3:
            messages.error(request, "Username must be at least 3 characters.")
            return redirect("edit_profile")

        if not re.match(r'^[A-Za-z0-9_]+$', username):
            messages.error(request, "Username can only contain letters, numbers and underscore.")
            return redirect("edit_profile")

        if CustomUser.objects.filter(username__iexact=username).exclude(id=user.id).exists():
            messages.error(request, "Username already taken.")
            return redirect("edit_profile")

        try:
            with transaction.atomic():
                user.first_name = display_name
                user.username   = username
                user.bio        = bio
                user.is_private = is_private
                if avatar:
                    if user.profile_picture:
                        user.profile_picture.delete(save=False)
                    user.profile_picture = avatar
                if banner and hasattr(user, 'banner_picture'):
                    if user.banner_picture:
                        user.banner_picture.delete(save=False)
                    user.banner_picture = banner
                user.save()

            messages.success(request, "Profile updated successfully.")
            return redirect("profile_detail", username=user.username)

        except Exception:
            messages.error(request, "Error updating profile.")
            return redirect("edit_profile")

    return render(request, "profile/edit_profile.html", {"user": user})


# ============================================================
# TOGGLE FOLLOW VIEW
# ============================================================

@login_required
@require_POST
def toggle_follow_view(request, username):
    target_user = get_object_or_404(CustomUser, username=username)

    if request.user == target_user:
        return JsonResponse({"success": False, "message": "You cannot follow yourself."}, status=400)

    follow_instance = Follow.objects.filter(follower=request.user, following=target_user).first()

    try:
        with transaction.atomic():
            if follow_instance:
                follow_instance.delete()
                is_following = False
            else:
                Follow.objects.create(follower=request.user, following=target_user)
                is_following = True
    except Exception:
        return JsonResponse({"success": False, "message": "Something went wrong."}, status=500)

    return JsonResponse({
        "success":         True,
        "is_following":    is_following,
        "followers_count": target_user.followers.count(),
        "following_count": request.user.following.count(),
    })


# ============================================================
# FOLLOWERS LIST VIEW
# ============================================================

@login_required
def followers_list_view(request, username):
    user      = get_object_or_404(CustomUser, username=username)
    followers = user.followers.select_related("follower")
    return render(request, "profile/followers_list.html", {"profile_user": user, "followers": followers})


# ============================================================
# FOLLOWING LIST VIEW
# ============================================================

@login_required
def following_list_view(request, username):
    user      = get_object_or_404(CustomUser, username=username)
    following = user.following.select_related("following")
    return render(request, "profile/following_list.html", {"profile_user": user, "following": following})

# ============================================================
# send follow request view (for private accounts)
# ============================================================
@login_required
@require_POST
def send_follow_request_view(request, username):

    target_user = get_object_or_404(CustomUser, username=username)

    if request.user == target_user:
        return JsonResponse({"success": False, "message": "Cannot follow yourself."}, status=400)

    # Already following
    if Follow.objects.filter(follower=request.user, following=target_user).exists():
        return JsonResponse({"success": False, "message": "Already following."})

    # PUBLIC ACCOUNT → follow instantly
    if not target_user.is_private:
        Follow.objects.create(follower=request.user, following=target_user)

        return JsonResponse({
            "success": True,
            "status": "following",
            "followers_count": target_user.followers.count()
        })

    # PRIVATE ACCOUNT → create request
    obj, created = FollowRequest.objects.get_or_create(
        sender=request.user,
        receiver=target_user
    )

    return JsonResponse({
        "success": True,
        "status": "requested"
    })


@login_required
@require_POST
def accept_follow_request_view(request, request_id):

    follow_request = get_object_or_404(
        FollowRequest,
        id=request_id,
        receiver=request.user
    )

    try:
        with transaction.atomic():

            Follow.objects.create(
                follower=follow_request.sender,
                following=follow_request.receiver
            )

            follow_request.delete()

    except Exception:
        return JsonResponse({"success": False})

    return JsonResponse({"success": True})




@login_required
@require_POST
def reject_follow_request_view(request, request_id):

    follow_request = get_object_or_404(
        FollowRequest,
        id=request_id,
        receiver=request.user
    )

    follow_request.delete()

    return JsonResponse({"success": True})


@login_required
@require_POST
def cancel_follow_request_view(request, username):

    target_user = get_object_or_404(CustomUser, username=username)

    FollowRequest.objects.filter(
        sender=request.user,
        receiver=target_user
    ).delete()

    return JsonResponse({"success": True})



@login_required
def follow_requests_view(request):

    requests = (
        FollowRequest.objects
        .filter(receiver=request.user)
        .select_related("sender")
        .order_by("-created_at")
    )

    return render(request, "profile/follow_requests.html", {
        "requests": requests
    })


def can_view_user_posts(viewer, owner):

    if viewer == owner:
        return True

    if not owner.is_private:
        return True

    return owner.followers.filter(follower=viewer).exists()
            