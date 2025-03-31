from django.contrib.auth import views as auth_views
from django.urls import path
from .views import (
    ProfileDetailedView,
    UserManagementView,
    CreateUserView,
    EditUserView,
    AdminPasswordChangeModalView,
    DeleteUserView,
    CustomPasswordChangeView,
)
from .views import login_redirect_view, delete_from_queue


urlpatterns = [
    path('login-redirect/', login_redirect_view, name='login-redirect'),
    path('password_change/', CustomPasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('users/', UserManagementView.as_view(), name='user_management'),
    path('create-user/', CreateUserView.as_view(), name='create_user'),
    path('edit-user/<int:pk>/', EditUserView.as_view(), name='edit_user'),
    path('change-password/<int:pk>/', AdminPasswordChangeModalView.as_view(), name='change_password'),
    path('delete-user/<int:pk>/', DeleteUserView.as_view(), name='delete_user'),
    path('profile/', ProfileDetailedView.as_view(), name='profile'),
    path('profile/<int:pk>/delete/', delete_from_queue, name='delete_from_queue'),
]