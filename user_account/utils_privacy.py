def can_view_user_posts(viewer, owner):
    """
        determine whether viewer can see owner's posts
    """



    if viewer == owner:
        return True

    if not owner.is_private:
        return True

    return owner.followers.filter(followers=viewer).exists()