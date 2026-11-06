from django.urls import path

from . import cabinet, views

urlpatterns = [
    path("auth/csrf", views.CsrfView.as_view()),
    path("auth/session", views.SessionView.as_view()),
    path("auth/register", views.RegisterView.as_view()),
    path("auth/login", views.LoginView.as_view()),
    path("auth/logout", views.LogoutView.as_view()),
    path("auth/verify-email", views.VerifyEmailView.as_view()),
    path("auth/resend-verification", views.ResendVerificationView.as_view()),
    path("auth/password-reset", views.PasswordResetRequestView.as_view()),
    path("auth/password-reset/confirm", views.PasswordResetConfirmView.as_view()),
    path("auth/password-change", views.PasswordChangeView.as_view()),
    path("me", views.MeView.as_view()),
    path("me/become-seller", views.BecomeSellerView.as_view()),
    path("me/purchases", cabinet.MyPurchases.as_view()),
    path("me/sales", cabinet.MySales.as_view()),
    path("me/accounts", cabinet.MyAccounts.as_view()),
    path("me/networks", cabinet.MyNetworks.as_view()),
    path("me/reviews", cabinet.MyReviews.as_view()),
    path("me/tickets", cabinet.MyTickets.as_view()),
    path("me/notifications", cabinet.MyNotifications.as_view()),
    path("me/notifications/<uuid:pk>/read", cabinet.NotificationRead.as_view()),
    path("me/notifications/unread-count", cabinet.NotificationsUnread.as_view()),
    path("me/notifications/read-all", cabinet.NotificationsReadAll.as_view()),
    path("me/activity", cabinet.MyActivity.as_view()),
    path("staff/users/<uuid:user_id>/roles", views.StaffUserRolesView.as_view()),
]
