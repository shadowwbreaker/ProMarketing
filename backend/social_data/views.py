from django.conf import settings
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from audit.services import record
from common.crypto import encrypt
from common.exceptions import DomainError
from common.permissions import HasPerm

from .core import errors
from .core.registry import get_provider, platform_enabled
from .core.url_parser import detect_platform
from .models import SocialAccount, SocialAccountConnection, SocialAccountStatistics, StatsRefreshJob
from . import consent
from .services import refresh_service as svc


class CreateAccountSerializer(serializers.Serializer):
    profile_url = serializers.URLField(max_length=500)
    title = serializers.CharField(max_length=120, required=False, allow_blank=True)
    category = serializers.CharField(max_length=64, required=False, allow_blank=True)
    language = serializers.CharField(max_length=8, required=False, default="ru")
    geo = serializers.CharField(max_length=64, required=False, allow_blank=True)
    description = serializers.CharField(max_length=4000, required=False, allow_blank=True)
    manual = serializers.BooleanField(default=False, help_text="Добавить без API, со статистикой MANUAL")


class ManualStatsSerializer(serializers.Serializer):
    followers = serializers.IntegerField(min_value=0)
    video_views = serializers.ListField(child=serializers.IntegerField(min_value=0), max_length=50)


class OAuthCallbackSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=1000)
    state = serializers.CharField(max_length=200)


class VideoSerializer(serializers.Serializer):
    external_video_id = serializers.CharField()
    url = serializers.URLField()
    published_at = serializers.DateTimeField(allow_null=True)
    views = serializers.IntegerField()
    is_short_heuristic = serializers.BooleanField()


class StatsHistorySerializer(serializers.ModelSerializer):
    videos = VideoSerializer(many=True)

    class Meta:
        model = SocialAccountStatistics
        fields = ["id", "followers", "avg_views", "videos_in_sample", "source", "trust_status", "fetched_at", "notes", "videos"]


def account_payload(account: SocialAccount, *, for_owner: bool) -> dict:
    last_job = account.refresh_jobs.order_by("-created_at").first()
    nxt = svc.next_allowed_at(account)
    data = {
        "id": str(account.pk), "platform": account.platform, "handle": account.handle, "profile_url": account.profile_url,
        "title": account.title, "category": account.category, "language": account.language, "geo": account.geo,
        "description": account.description, "status": account.status, "is_listed": account.is_listed,
        "ownership_verified": account.ownership_verified,
        "statistics": svc.display_status(account.current_statistics, account.platform, for_owner=for_owner),
    }
    if for_owner:
        from .core.registry import provider_mode

        data["demo_data"] = provider_mode(account.platform) == "fake"  # dev without API keys: numbers are generated
        data["ownership_code"] = account.ownership_code
        data["ownership_check_supported"] = account.platform in ("youtube",)
        data["refresh"] = {
            "last_requested_at": account.last_refresh_requested_at,
            "next_allowed_at": nxt if nxt and nxt > timezone.now() else None,
            "interval_hours": settings.STATS_REFRESH_INTERVAL_HOURS,
            "last_job": None if not last_job else {
                "id": str(last_job.pk), "status": last_job.status, "error_code": last_job.error_code,
                "error_message": last_job.error_message, "finished_at": last_job.finished_at,
            },
        }
    return data


def _owned(request, pk) -> SocialAccount:
    return get_object_or_404(SocialAccount.objects.select_related("current_statistics"), pk=pk, owner=request.user)


class SocialAccountListCreate(APIView):
    permission_classes = [HasPerm("account.manage_own")]

    @extend_schema(request=CreateAccountSerializer, responses={201: dict})
    def post(self, request):
        s = CreateAccountSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        d = s.validated_data
        try:
            platform, _ = detect_platform(d["profile_url"])
        except errors.ProviderError as e:
            raise DomainError(e.user_message, code=e.code, status_code=400) from e
        if not platform_enabled(platform):
            raise DomainError("Платформа недоступна на сервисе", code="platform_disabled", status_code=400)
        if not d["manual"]:
            consent.require(request.data)  # D-024: the owner allows the API request before it is made
        if d["manual"]:
            from .providers.manual.provider import ManualProvider

            resolved = ManualProvider(platform).resolve_account(d["profile_url"])
        else:
            try:
                resolved = get_provider(platform).resolve_account(d["profile_url"])
            except errors.AuthorizationRequired as e:
                raise DomainError("Для этой платформы подключите канал через вход на платформе",
                                  code="oauth_required", status_code=400, details={"oauth_start": f"/social-accounts/oauth/{platform}/start"}) from e
            except errors.ProviderError as e:
                raise DomainError(e.user_message, code=e.code, status_code=400,
                                  details={"manual_allowed": True}) from e
        existing = SocialAccount.objects.filter(platform=resolved.platform, external_id=resolved.external_id).first()
        if existing and existing.owner_id != request.user.pk:
            from .services.ownership import find_claimable

            if find_claimable(resolved.platform, resolved.external_id, request.user):
                raise DomainError("Этот канал уже добавил другой пользователь, не подтвердив владение. Если канал ваш — подтвердите это кодом в описании, и он перейдёт к вам.",
                                  code="account_claimable", status_code=409, details={"account_id": str(existing.pk)})
        account = _create_account(request.user, resolved, d, manual=d["manual"])
        if not d["manual"]:
            consent.record_consent(user=request.user, request=request, platform=account.platform,
                                   profile_url=account.profile_url, purpose="add", account=account)
            svc.request_refresh(account.pk, user=request.user, trigger=StatsRefreshJob.Trigger.ACCOUNT_ADDED)
            account.refresh_from_db()
        return Response(account_payload(account, for_owner=True), status=status.HTTP_201_CREATED)


def _create_account(user, resolved, d, *, manual: bool, ownership_verified: bool = False) -> SocialAccount:
    try:
        with transaction.atomic():
            account = SocialAccount.objects.create(
                owner=user, platform=resolved.platform, external_id=resolved.external_id, handle=resolved.handle,
                profile_url=resolved.profile_url, title=d.get("title") or resolved.title or resolved.handle,
                category=d.get("category", ""), language=d.get("language", "ru"), geo=d.get("geo", ""),
                description=d.get("description", ""), ownership_verified=ownership_verified,
            )
    except IntegrityError as e:
        raise DomainError("Этот канал уже добавлен на платформу", code="account_exists", status_code=400) from e
    record(action="social_account.created", subject_type="social_account", subject_id=account.pk, actor=user,
           after={"platform": account.platform, "manual": manual})
    return account


class SocialAccountDetail(APIView):
    permission_classes = [HasPerm("account.manage_own")]

    def get(self, request, pk):
        return Response(account_payload(_owned(request, pk), for_owner=True))


class SocialAccountRefresh(APIView):
    permission_classes = [HasPerm("account.manage_own")]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "stats_refresh"

    @extend_schema(request=None, responses={202: dict})
    def post(self, request, pk):
        account = _owned(request, pk)
        consent.require(request.data)
        job = svc.request_refresh(account.pk, user=request.user)
        consent.record_consent(user=request.user, request=request, platform=account.platform,
                               profile_url=account.profile_url, purpose="refresh", account=account)
        account.refresh_from_db()
        return Response({"job_id": str(job.pk), "account": account_payload(account, for_owner=True)}, status=202)


class SocialAccountStatsHistory(APIView):
    permission_classes = [HasPerm("account.manage_own")]

    def get(self, request, pk):
        account = _owned(request, pk)
        qs = account.statistics.order_by("-fetched_at").prefetch_related("videos")[:50]
        return Response({"results": StatsHistorySerializer(qs, many=True).data,
                         "failed_jobs": list(account.refresh_jobs.filter(status="failed").order_by("-created_at")
                                             .values("id", "error_code", "error_message", "finished_at")[:20])})


class SocialAccountManualStats(APIView):
    permission_classes = [HasPerm("account.manage_own")]

    @extend_schema(request=ManualStatsSerializer, responses={201: dict})
    def post(self, request, pk):
        account = _owned(request, pk)
        s = ManualStatsSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        svc.save_manual_statistics(account, user=request.user, **s.validated_data)
        account.refresh_from_db()
        return Response(account_payload(account, for_owner=True), status=201)


SESSION_STATE_KEY = "oauth_state_tiktok"


class TikTokOAuthStart(APIView):
    """Owner authorization via TikTok Login Kit (D-003)."""

    permission_classes = [HasPerm("account.manage_own")]

    def get(self, request):
        from .providers.tiktok.provider import TikTokProvider

        try:
            provider = TikTokProvider.from_settings()
        except errors.ProviderNotConfigured as e:
            raise DomainError(e.user_message, code=e.code, status_code=503) from e
        if request.query_params.get("consent") != "1":
            consent.require({})
        consent.record_consent(user=request.user, request=request, platform="tiktok", profile_url="", purpose="add")
        url, state = provider.authorize_url()
        request.session[SESSION_STATE_KEY] = state
        return Response({"authorize_url": url})


class TikTokOAuthCallback(APIView):
    permission_classes = [HasPerm("account.manage_own")]

    @extend_schema(request=OAuthCallbackSerializer, responses={201: dict})
    def post(self, request):
        from .providers.tiktok.provider import TikTokProvider
        from .services.refresh_service import Credentials

        s = OAuthCallbackSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        expected = request.session.pop(SESSION_STATE_KEY, None)
        if not expected or expected != s.validated_data["state"]:
            raise DomainError("Сессия авторизации устарела, начните заново", code="oauth_state_mismatch", status_code=400)
        provider = TikTokProvider.from_settings()
        try:
            tokens = provider.exchange_code(s.validated_data["code"])
            resolved = provider.resolve_account(credentials=Credentials(tokens.access_token))
        except errors.ProviderError as e:
            raise DomainError(e.user_message, code=e.code, status_code=400) from e
        existing = SocialAccount.objects.filter(platform="tiktok", external_id=resolved.external_id).first()
        if existing and existing.owner_id != request.user.pk:
            raise DomainError("Этот канал уже добавлен другим пользователем. Обратитесь в поддержку.",
                              code="account_owned_by_other", status_code=400)
        account = existing or _create_account(request.user, resolved, {}, manual=False, ownership_verified=True)
        SocialAccountConnection.objects.update_or_create(social_account=account, defaults={
            "oauth_scopes": tokens.scope, "access_token_enc": encrypt(tokens.access_token),
            "refresh_token_enc": encrypt(tokens.refresh_token), "expires_at": tokens.expires_at, "revoked_at": None,
        })
        if not account.ownership_verified:
            account.ownership_verified = True
            account.save(update_fields=["ownership_verified", "updated_at"])
        if not existing:
            svc.request_refresh(account.pk, user=request.user, trigger=StatsRefreshJob.Trigger.ACCOUNT_ADDED)
        account.refresh_from_db()
        return Response(account_payload(account, for_owner=True), status=201)


class SocialAccountOwnership(APIView):
    """POST /social-accounts/{id}/ownership/{start|check} (D-020)."""

    permission_classes = [HasPerm("account.manage_own")]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ownership"

    def post(self, request, pk, action):
        from .services import ownership

        account = _owned(request, pk)
        if action == "start":
            code = ownership.start(account, user=request.user)
            return Response({"code": code})
        if action == "check":
            ok = ownership.check(account, user=request.user)
            account.refresh_from_db()
            return Response({"verified": ok, "account": account_payload(account, for_owner=True)})
        raise DomainError("Неизвестное действие", code="bad_action", status_code=404)


class SocialAccountClaim(APIView):
    """POST /social-accounts/{id}/claim/{start|check} — the real owner takes over an unverified account (D-020)."""

    permission_classes = [HasPerm("account.manage_own")]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "ownership"

    def post(self, request, pk, action):
        from .services import ownership

        account = get_object_or_404(SocialAccount, pk=pk)
        if action == "start":
            return Response({"code": ownership.start_claim(account, user=request.user)})
        if action == "check":
            ok = ownership.check_claim(account, user=request.user)
            account.refresh_from_db()
            return Response({"claimed": ok, "account": account_payload(account, for_owner=True) if ok else None})
        raise DomainError("Неизвестное действие", code="bad_action", status_code=404)
