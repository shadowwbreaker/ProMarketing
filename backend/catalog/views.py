from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasPerm
from orders.models import OrderItem
from social_data.models import SocialAccount
from social_data.views import account_payload

from . import services
from .models import AccountNetwork, AdFormat, AdvertisingOffer, NetworkItem

OWNER = [HasPerm("account.manage_own")]


class OfferSerializer(serializers.ModelSerializer):
    ad_format_label = serializers.CharField(source="get_ad_format_display", read_only=True)

    class Meta:
        model = AdvertisingOffer
        fields = ["id", "social_account", "ad_format", "ad_format_label", "title", "price_minor", "currency", "conditions",
                  "placement_days", "publish_within_days", "is_active", "created_at"]
        read_only_fields = ["id", "social_account", "currency", "created_at"]
        extra_kwargs = {"price_minor": {"min_value": 100}, "placement_days": {"min_value": 1, "max_value": 365},
                        "publish_within_days": {"min_value": 1, "max_value": 90}}


class AccountUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SocialAccount
        fields = ["title", "category", "language", "geo", "description"]


class NetworkItemSerializer(serializers.ModelSerializer):
    account = serializers.SerializerMethodField()

    class Meta:
        model = NetworkItem
        fields = ["id", "social_account", "offer", "price_minor", "account"]

    def get_account(self, obj):
        a = obj.social_account
        return {"id": str(a.pk), "platform": a.platform, "handle": a.handle, "title": a.title}


class NetworkSerializer(serializers.ModelSerializer):
    items = NetworkItemSerializer(many=True, read_only=True)
    stats = serializers.SerializerMethodField()

    class Meta:
        model = AccountNetwork
        fields = ["id", "title", "description", "total_price_minor", "currency", "conditions", "allow_partial_purchase",
                  "is_active", "items", "stats", "created_at"]
        read_only_fields = ["id", "currency", "items", "stats", "created_at"]
        extra_kwargs = {"total_price_minor": {"min_value": 100}}

    def get_stats(self, obj):
        return services.network_stats(obj, for_owner=self.context.get("for_owner", False))


class AddItemSerializer(serializers.Serializer):
    offer = serializers.UUIDField()
    price_minor = serializers.IntegerField(min_value=100, required=False)


class ListingSerializer(serializers.Serializer):
    listed = serializers.BooleanField()


def _account(request, pk):
    return get_object_or_404(SocialAccount, pk=pk, owner=request.user)


class AdFormatsView(APIView):
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        return Response([{"value": v, "label": label} for v, label in AdFormat.choices])


class AccountManageView(APIView):
    permission_classes = OWNER

    @extend_schema(request=AccountUpdateSerializer, responses={200: dict})
    def patch(self, request, pk):
        acc = _account(request, pk)
        s = AccountUpdateSerializer(acc, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
        return Response(account_payload(acc, for_owner=True))

    def delete(self, request, pk):
        services.remove_account(_account(request, pk), user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class AccountListingView(APIView):
    permission_classes = OWNER

    @extend_schema(request=ListingSerializer, responses={200: dict})
    def post(self, request, pk):
        s = ListingSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        acc = services.set_listing(_account(request, pk), user=request.user, listed=s.validated_data["listed"])
        return Response(account_payload(acc, for_owner=True))


class AccountOffersView(APIView):
    permission_classes = OWNER

    def get(self, request, pk):
        acc = _account(request, pk)
        return Response(OfferSerializer(acc.offers.order_by("-is_active", "-created_at"), many=True).data)

    @extend_schema(request=OfferSerializer, responses={201: OfferSerializer})
    def post(self, request, pk):
        acc = _account(request, pk)
        s = OfferSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        offer = services.create_offer(acc, user=request.user, **s.validated_data)
        return Response(OfferSerializer(offer).data, status=201)


class AccountOrdersView(APIView):
    permission_classes = OWNER

    def get(self, request, pk):
        acc = _account(request, pk)
        items = OrderItem.objects.filter(social_account=acc).select_related("order").order_by("-created_at")[:100]
        return Response([{"id": str(i.pk), "order": str(i.order_id), "status": i.status, "price_minor": i.price_minor,
                          "created_at": i.created_at} for i in items])


class OfferDetailView(APIView):
    permission_classes = OWNER

    @extend_schema(request=OfferSerializer, responses={200: OfferSerializer})
    def patch(self, request, pk):
        offer = get_object_or_404(AdvertisingOffer.objects.select_related("social_account"), pk=pk, social_account__owner=request.user)
        s = OfferSerializer(offer, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        offer = services.update_offer(offer, user=request.user, **s.validated_data)
        return Response(OfferSerializer(offer).data)


class NetworkListCreate(APIView):
    permission_classes = OWNER

    def get(self, request):
        qs = AccountNetwork.objects.filter(owner=request.user).prefetch_related("items__social_account").order_by("-created_at")
        return Response(NetworkSerializer(qs, many=True, context={"for_owner": True}).data)

    @extend_schema(request=NetworkSerializer, responses={201: NetworkSerializer})
    def post(self, request):
        s = NetworkSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        net = services.create_network(user=request.user, **s.validated_data)
        return Response(NetworkSerializer(net, context={"for_owner": True}).data, status=201)


class NetworkDetail(APIView):
    permission_classes = OWNER

    def _get(self, request, pk):
        return get_object_or_404(AccountNetwork, pk=pk, owner=request.user)

    def get(self, request, pk):
        return Response(NetworkSerializer(self._get(request, pk), context={"for_owner": True}).data)

    @extend_schema(request=NetworkSerializer, responses={200: NetworkSerializer})
    def patch(self, request, pk):
        net = self._get(request, pk)
        s = NetworkSerializer(net, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        net = services.update_network(net, user=request.user, **s.validated_data)
        return Response(NetworkSerializer(net, context={"for_owner": True}).data)


class NetworkItems(APIView):
    permission_classes = OWNER

    @extend_schema(request=AddItemSerializer, responses={201: NetworkSerializer})
    def post(self, request, pk):
        net = get_object_or_404(AccountNetwork, pk=pk, owner=request.user)
        s = AddItemSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        offer = get_object_or_404(AdvertisingOffer.objects.select_related("social_account"), pk=s.validated_data["offer"])
        services.add_network_item(net, user=request.user, offer=offer, price_minor=s.validated_data.get("price_minor"))
        return Response(NetworkSerializer(net, context={"for_owner": True}).data, status=201)


class NetworkItemDelete(APIView):
    permission_classes = OWNER

    def delete(self, request, pk, item_id):
        item = get_object_or_404(NetworkItem.objects.select_related("network"), pk=item_id, network_id=pk, network__owner=request.user)
        services.remove_network_item(item, user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
