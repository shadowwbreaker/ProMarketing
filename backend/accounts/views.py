from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.password_validation import validate_password
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.services import record
from common.exceptions import DomainError
from common.permissions import HasPerm, IsActiveUser

from . import services
from .models import User
from .serializers import (
    LoginSerializer,
    MeSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegisterSerializer,
    RolesUpdateSerializer,
    TokenSerializer,
)


class AuthThrottleMixin:
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


def _ip(request):
    return request.META.get("REMOTE_ADDR")


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the csrftoken cookie for the SPA."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict})
    def get(self, request):
        return Response({"ok": True})


@method_decorator(ensure_csrf_cookie, name="dispatch")
class SessionView(APIView):
    """Current session for the SPA: {"user": Me | null}. Always 200, sets CSRF cookie."""

    permission_classes = [AllowAny]

    @extend_schema(responses={200: dict})
    def get(self, request):
        u = request.user
        active = u.is_authenticated and u.is_active and u.status != User.Status.BLOCKED
        return Response({"user": MeSerializer(u).data if active else None})


class RegisterView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=RegisterSerializer, responses={201: MeSerializer})
    def post(self, request):
        s = RegisterSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        user = services.register_user(email=d["email"], password=d["password"], display_name=d["display_name"],
                                      as_seller=d["as_seller"])
        login(request, user, backend="django.contrib.auth.backends.ModelBackend")
        return Response(MeSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=LoginSerializer, responses={200: MeSerializer})
    def post(self, request):
        s = LoginSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = authenticate(request, email=s.validated_data["email"].lower(), password=s.validated_data["password"])
        if user is None:
            raise DomainError("Неверный email или пароль", code="invalid_credentials", status_code=400)
        if user.status == User.Status.BLOCKED:
            record(action="user.login_blocked", subject_type="user", subject_id=user.pk, actor=user, ip=_ip(request))
            raise DomainError("Аккаунт заблокирован. Обратитесь в поддержку.", code="account_blocked", status_code=403)
        login(request, user)  # rotates session key (session fixation protection)
        record(action="user.login", subject_type="user", subject_id=user.pk, actor=user, ip=_ip(request))
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        if request.user.is_authenticated:
            record(action="user.logout", subject_type="user", subject_id=request.user.pk, actor=request.user, ip=_ip(request))
        logout(request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    permission_classes = [IsActiveUser]

    @extend_schema(responses={200: MeSerializer})
    def get(self, request):
        return Response(MeSerializer(request.user).data)

    @extend_schema(request=MeSerializer, responses={200: MeSerializer})
    def patch(self, request):
        s = MeSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(MeSerializer(request.user).data)


class VerifyEmailView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=TokenSerializer, responses={200: dict})
    def post(self, request):
        s = TokenSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.verify_email(s.validated_data["token"])
        return Response({"ok": True})


class ResendVerificationView(AuthThrottleMixin, APIView):
    permission_classes = [IsActiveUser]

    def post(self, request):
        if not request.user.is_email_verified:
            services.send_verification_email(request.user)
        return Response({"ok": True})


class PasswordResetRequestView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetRequestSerializer, responses={200: dict})
    def post(self, request):
        s = PasswordResetRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.request_password_reset(s.validated_data["email"])
        return Response({"ok": True})  # same answer whether or not the email exists


class PasswordResetConfirmView(AuthThrottleMixin, APIView):
    permission_classes = [AllowAny]

    @extend_schema(request=PasswordResetConfirmSerializer, responses={200: dict})
    def post(self, request):
        s = PasswordResetConfirmSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.reset_password(s.validated_data["token"], s.validated_data["new_password"])
        return Response({"ok": True})


class PasswordChangeView(AuthThrottleMixin, APIView):
    permission_classes = [IsActiveUser]

    @extend_schema(request=PasswordChangeSerializer, responses={200: dict})
    def post(self, request):
        s = PasswordChangeSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = request.user
        if not user.check_password(s.validated_data["old_password"]):
            raise DomainError("Текущий пароль указан неверно", code="invalid_password", status_code=400)
        validate_password(s.validated_data["new_password"], user=user)
        user.set_password(s.validated_data["new_password"])
        user.save(update_fields=["password", "updated_at"])
        update_session_auth_hash(request, user)  # keep this session, invalidate all others
        record(action="user.password_changed", subject_type="user", subject_id=user.pk, actor=user, ip=_ip(request))
        return Response({"ok": True})


class BecomeSellerView(APIView):
    permission_classes = [IsActiveUser]

    @extend_schema(responses={200: MeSerializer})
    def post(self, request):
        services.become_seller(request.user)
        return Response(MeSerializer(request.user).data)


class StaffUserRolesView(APIView):
    permission_classes = [HasPerm("user.manage_roles")]

    @extend_schema(request=RolesUpdateSerializer, responses={200: MeSerializer})
    def put(self, request, user_id):
        target = get_object_or_404(User, pk=user_id)
        s = RolesUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        services.set_roles(target=target, roles=s.validated_data["roles"], actor=request.user,
                           comment=s.validated_data["comment"])
        return Response(MeSerializer(target).data)
