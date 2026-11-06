from rest_framework.throttling import ScopedRateThrottle
from django.shortcuts import get_object_or_404
from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasPerm, IsActiveUser

from . import services
from .models import Review, ReviewComplaint


def _r(r: Review, staff=False):
    d = {"id": str(r.pk), "order_item": str(r.order_item_id), "rating": r.rating, "text": r.text, "seller_reply": r.seller_reply,
         "moderation_status": r.moderation_status, "author": r.author.profile.display_name, "created_at": r.created_at}
    if staff:
        d["complaints"] = [{"id": str(c.pk), "reason": c.reason, "status": c.status, "author": c.author.email} for c in r.complaints.all()]
        d["target"] = r.target_user.email
    return d


class CreateReview(APIView):
    permission_classes = [IsActiveUser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "review"

    def post(self, request, pk, item_id):
        try:
            rating = int(request.data.get("rating"))
        except (TypeError, ValueError):
            rating = 0
        r = services.create_review(pk, item_id, actor=request.user, rating=rating, text=request.data.get("text", ""))
        return Response(_r(r), status=201)


class Reply(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, pk):
        return Response(_r(services.reply(pk, actor=request.user, text=request.data.get("text", ""))))


class Complain(APIView):
    permission_classes = [IsActiveUser]

    def post(self, request, pk):
        get_object_or_404(Review, pk=pk)
        c = services.complain(pk, actor=request.user, reason=request.data.get("reason", ""))
        return Response({"id": str(c.pk), "status": c.status}, status=201)


class StaffReviews(APIView):
    permission_classes = [HasPerm("moderation.content")]

    def get(self, request):
        qs = Review.objects.select_related("author__profile", "target_user").prefetch_related("complaints__author").order_by("-created_at")
        if request.query_params.get("complaints") == "1":
            qs = qs.filter(complaints__status=ReviewComplaint.Status.OPEN).distinct()
        return Response([_r(r, staff=True) for r in qs[:200]])


class StaffModerate(APIView):
    permission_classes = [HasPerm("moderation.content")]

    def post(self, request, pk, action):
        r = services.moderate(pk, actor=request.user, action=action, comment=request.data.get("comment", ""),
                              complaint_id=request.data.get("complaint"))
        return Response(_r(r, staff=True))
