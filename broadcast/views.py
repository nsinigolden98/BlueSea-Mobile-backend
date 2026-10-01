import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Broadcast
from .serializers import BroadcastSerializer

logger = logging.getLogger(__name__)

User = get_user_model()

NEW_MONTH_TEMPLATE = "broadcast/new_month.html"
IMPORTANT_TEMPLATE = "broadcast/important.html"


class IsSuperUser(IsAuthenticated):
    def has_permission(self, request, view):
        return super().has_permission(request, view) and bool(
            getattr(request.user, "is_superuser", False)
        )


def _no_store(response):
    response["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response["Pragma"] = "no-cache"
    return response


def _current_month_key():
    return timezone.now().strftime("%Y-%m")


def _current_month_name():
    return timezone.now().strftime("%B %Y")


def _new_month_defaults(request):
    month_name = _current_month_name()
    title = request.query_params.get("title") or f"Happy New Month — {month_name}!"
    message = request.query_params.get("message") or (
        f"Happy New Month, and welcome to {month_name}! "
        "Thank you for choosing BlueSea Mobile. May this new month bring you joy, "
        "growth, and seamless transactions."
    )
    email_subject = request.query_params.get("email_subject") or f"BlueSea Mobile — {title}"
    return title, message, email_subject


def _important_defaults(request):
    title = request.query_params.get("title") or "Important: We have moved to blueseamobile.com"
    message = request.query_params.get("message") or (
        "Hello from BlueSea Mobile! Please note our platform has moved from "
        "blueseamobile.com.ng to blueseamobile.com. "
        "Please update your bookmarks and always use blueseamobile.com going forward. "
        "Your account, wallet balance, and PIN remain unchanged."
    )
    email_subject = request.query_params.get("email_subject") or "BlueSea Mobile — Important domain change"
    return title, message, email_subject


def _recipient_count():
    return User.objects.filter(is_active=True).count()


class NewMonthBroadcastView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        summary="Broadcast Happy New Month (superuser)",
        description=(
            "GET without ?confirm=yes returns a preview (recipient count, defaults, already-sent flag). "
            "GET with ?confirm=yes queues Happy New Month emails + in-app notifications to all active users via Celery. "
            "Idempotent per calendar month unless ?force=yes. Superuser (is_superuser) only."
        ),
        parameters=[
            OpenApiParameter("confirm", OpenApiTypes.STR, required=False, description="Set to 'yes' to send"),
            OpenApiParameter("force", OpenApiTypes.STR, required=False, description="Set to 'yes' to resend same month"),
            OpenApiParameter("title", OpenApiTypes.STR, required=False),
            OpenApiParameter("message", OpenApiTypes.STR, required=False),
            OpenApiParameter("email_subject", OpenApiTypes.STR, required=False),
        ],
        responses={200: OpenApiTypes.OBJECT, 202: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Broadcast"],
    )
    def get(self, request):
        month_key = _current_month_key()
        title, message, email_subject = _new_month_defaults(request)
        already_sent = Broadcast.objects.filter(
            kind="new_month", month_key=month_key, status__in=["sending", "sent", "partial"]
        ).exists()

        confirm = (request.query_params.get("confirm") or "").lower() == "yes"
        if not confirm:
            return _no_store(Response({
                "kind": "new_month",
                "month_key": month_key,
                "title": title,
                "message": message,
                "email_subject": email_subject,
                "template": NEW_MONTH_TEMPLATE,
                "recipient_count": _recipient_count(),
                "already_sent": already_sent,
                "hint": "Add ?confirm=yes to queue the broadcast",
            }))

        force = (request.query_params.get("force") or "").lower() == "yes"
        if already_sent and not force:
            return _no_store(Response(
                {"error": f"New month broadcast for {month_key} already sent. Use ?force=yes to resend."},
                status=status.HTTP_400_BAD_REQUEST,
            ))

        broadcast = Broadcast.objects.create(
            kind="new_month",
            title=title,
            message=message,
            email_subject=email_subject,
            template=NEW_MONTH_TEMPLATE,
            month_key=month_key,
            status="pending",
            total=_recipient_count(),
            created_by=request.user,
        )
        from .tasks import send_broadcast

        send_broadcast.delay(broadcast.id)
        logger.info(f"Superuser {request.user.email} queued new-month broadcast {broadcast.id}")
        return _no_store(Response(
            BroadcastSerializer(broadcast).data, status=status.HTTP_202_ACCEPTED
        ))


class ImportantBroadcastView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        summary="Broadcast important notice (superuser)",
        description=(
            "GET without ?confirm=yes returns a preview. GET with ?confirm=yes queues the domain-change notice "
            "(blueseamobile.com.ng to blueseamobile.com) to all active users via Celery. "
            "Blocked if already sent unless ?force=yes. Superuser (is_superuser) only."
        ),
        parameters=[
            OpenApiParameter("confirm", OpenApiTypes.STR, required=False, description="Set to 'yes' to send"),
            OpenApiParameter("force", OpenApiTypes.STR, required=False, description="Set to 'yes' to resend"),
            OpenApiParameter("title", OpenApiTypes.STR, required=False),
            OpenApiParameter("message", OpenApiTypes.STR, required=False),
            OpenApiParameter("email_subject", OpenApiTypes.STR, required=False),
        ],
        responses={200: OpenApiTypes.OBJECT, 202: OpenApiTypes.OBJECT, 400: OpenApiTypes.OBJECT},
        tags=["Broadcast"],
    )
    def get(self, request):
        title, message, email_subject = _important_defaults(request)
        already_sent = Broadcast.objects.filter(
            kind="important", status__in=["sending", "sent", "partial"]
        ).exists()

        confirm = (request.query_params.get("confirm") or "").lower() == "yes"
        if not confirm:
            return _no_store(Response({
                "kind": "important",
                "title": title,
                "message": message,
                "email_subject": email_subject,
                "template": IMPORTANT_TEMPLATE,
                "recipient_count": _recipient_count(),
                "already_sent": already_sent,
                "hint": "Add ?confirm=yes to queue the broadcast",
            }))

        force = (request.query_params.get("force") or "").lower() == "yes"
        if already_sent and not force:
            return _no_store(Response(
                {"error": "Important broadcast already sent. Use ?force=yes to resend."},
                status=status.HTTP_400_BAD_REQUEST,
            ))

        broadcast = Broadcast.objects.create(
            kind="important",
            title=title,
            message=message,
            email_subject=email_subject,
            template=IMPORTANT_TEMPLATE,
            status="pending",
            total=_recipient_count(),
            created_by=request.user,
        )
        from .tasks import send_broadcast

        send_broadcast.delay(broadcast.id)
        logger.info(f"Superuser {request.user.email} queued important broadcast {broadcast.id}")
        return _no_store(Response(
            BroadcastSerializer(broadcast).data, status=status.HTTP_202_ACCEPTED
        ))


class BroadcastHistoryView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        summary="List broadcasts (superuser)",
        responses={200: BroadcastSerializer(many=True)},
        tags=["Broadcast"],
    )
    def get(self, request):
        broadcasts = Broadcast.objects.all().order_by("-created_at")[:50]
        return _no_store(Response(BroadcastSerializer(broadcasts, many=True).data))
