from rest_framework.response import Response
from rest_framework.views import APIView

from common.permissions import HasPerm

from .signals import collect


class Signals(APIView):
    permission_classes = [HasPerm("staff.access", "moderation.stats")]

    def get(self, request):
        data = collect()
        if t := request.query_params.get("type"):
            data = [s for s in data if s["type"] == t]
        return Response({"count": len(data), "results": data,
                         "note": "Сигналы требуют проверки человеком и не являются доказательством нарушения."})
