from django.shortcuts import redirect
from django.urls import reverse


_ALLOWED_PATHS = {'/login/', '/logout/', '/blocked/'}


class BlockedUserMiddleware:
    """Redirect blocked users to a blocked page on every protected request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if (
            request.user.is_authenticated
            and not request.user.is_staff
            and request.path not in _ALLOWED_PATHS
        ):
            try:
                if request.user.profile.is_blocked:
                    if request.path != '/blocked/':
                        return redirect('/blocked/')
            except Exception:
                pass
        return self.get_response(request)
