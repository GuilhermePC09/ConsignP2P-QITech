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


class IsUserAuthenticated(permissions.BasePermission):
    """
    Permission class for user-specific OAuth2 authentication.
    Requires both valid OAuth2 token AND an authenticated user.
    This is for operations that need to be tied to specific users.
    """

    def has_permission(self, request, view):
        # Must have both OAuth2 token and authenticated user
        has_oauth = hasattr(request, 'auth') and isinstance(
            request.auth, AccessToken)
        has_user = bool(
            request.user and request.user.is_authenticated and not request.user.is_anonymous)

        return has_oauth and has_user


class IsInvestorUser(permissions.BasePermission):
    """
    Permission class for investor-specific operations.
    User must be authenticated and have an investor profile.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Check if user has investor profile
        return hasattr(request.user, 'investor_profile') and request.user.investor_profile is not None

    def has_object_permission(self, request, view, obj):
        """Check if user can access this specific investor object"""
        if not self.has_permission(request, view):
            return False

        # User can only access their own investor data
        return request.user.investor_profile == obj


class IsBorrowerUser(permissions.BasePermission):
    """
    Permission class for borrower-specific operations.
    User must be authenticated and have a borrower profile.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        # Check if user has borrower profile
        return hasattr(request.user, 'borrower_profile') and request.user.borrower_profile is not None

    def has_object_permission(self, request, view, obj):
        """Check if user can access this specific borrower object"""
        if not self.has_permission(request, view):
            return False

        # User can only access their own borrower data
        return request.user.borrower_profile == obj


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission class that allows access to admins or owners of the resource.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # Admin users can access everything
        if request.user.is_staff or request.user.is_superuser:
            return True

        # Check if user owns this resource
        # For Investor objects
        if hasattr(obj, 'investor_id'):
            return hasattr(request.user, 'investor_profile') and request.user.investor_profile == obj

        # For Borrower objects
        if hasattr(obj, 'borrower_id'):
            return hasattr(request.user, 'borrower_profile') and request.user.borrower_profile == obj

        # For objects that belong to investors/borrowers
        if hasattr(obj, 'investor'):
            return hasattr(request.user, 'investor_profile') and request.user.investor_profile == obj.investor

        if hasattr(obj, 'borrower'):
            return hasattr(request.user, 'borrower_profile') and request.user.borrower_profile == obj.borrower

        # For wallets owned by investor
        if hasattr(obj, 'owner_type') and obj.owner_type == 'investor':
            return (hasattr(request.user, 'investor_profile') and
                    request.user.investor_profile and
                    str(request.user.investor_profile.investor_id) == str(obj.owner_id))

        return False
