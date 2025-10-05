from rest_framework import permissions
from oauth2_provider.models import AccessToken


class IsOAuth2Authenticated(permissions.BasePermission):
    """
    Custom permission class for OAuth2 client credentials flow.
    Allows access if the request has a valid OAuth2 access token,
    even if there's no associated user (client credentials flow).
    """

    def has_permission(self, request, view):
        # Check if there's a valid OAuth2 access token
        if hasattr(request, 'auth') and request.auth:
            # For OAuth2, request.auth should be an AccessToken instance
            if isinstance(request.auth, AccessToken):
                return True

        # Fall back to standard user authentication
        return bool(request.user and request.user.is_authenticated)
