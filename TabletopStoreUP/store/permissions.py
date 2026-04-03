from rest_framework import permissions

def _get_role_name(user):
    try:
        return user.profile.role.name
    except Exception:
        return None

class IsAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        profile = getattr(request.user, 'profile', None)
        return request.user.is_authenticated and getattr(profile.role, 'name', '') == 'admin'

class IsManagerOrAdmin(permissions.BasePermission):
    def has_permission(self, request, view):
        profile = getattr(request.user, 'profile', None)
        return request.user.is_authenticated and getattr(profile.role, 'name', '') in ['manager', 'admin']

class IsClientOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        profile = getattr(request.user, 'profile', None)
        return request.user.is_authenticated and getattr(profile.role, 'name', '') == 'client'
