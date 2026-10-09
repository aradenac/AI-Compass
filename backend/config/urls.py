from django.urls import path

from . import auth_views
from .api import api

urlpatterns = [
    path("api/v1/auth/csrf", auth_views.csrf_token),
    path("api/v1/auth/me", auth_views.account),
    path("api/v1/auth/login", auth_views.sign_in),
    path("api/v1/auth/logout", auth_views.sign_out),
    path("api/v1/auth/sandbox", auth_views.sandbox),
    path("api/v1/auth/sandbox/write", auth_views.sandbox_update),
    path("api/v1/auth/maintenance", auth_views.maintenance_landing),
    path("api/v1/auth/user-admin", auth_views.user_admin_landing),
    path("api/v1/auth/platform", auth_views.platform_landing),
    path("api/v1/", api.urls),
]
