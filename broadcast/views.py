import logging

from django.contrib.auth import get_user_model
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
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
ANNOUNCEMENT_TEMPLATE = "broadcast/announcement.html"


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


def _announcement_defaults(request):
    title = request.query_params.get("title") or "Thank You for Celebrating with Us!"
    message = request.query_params.get("message") or (
        "Thank you for coming out on Saturday, October 3rd! Your presence at the "
        "BlueSea Mobile event — red carpet at 2:30pm, main event at 3:00pm, at "
        "Assemblies of God, Testimony Chapel, Oyigbo, Rivers State — meant the "
        "world to us. We're grateful for this community and have so much more in "
        "store. Stay tuned!"
    )
    email_subject = request.query_params.get("email_subject") or "BlueSea Mobile — Thank You!"
    return title, message, email_subject


def _recipient_count():
    return User.objects.filter(is_active=True).count()


class NewMonthBroadcastView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        summary="Broadcast Happy New Month (superuser)",
        description=(
            "Send the monthly greeting to every active user, or preview it first.\n\n"
            "- Without `?confirm=yes`: dry-run preview. Returns the resolved title/message/subject, "
            "the editable template (`broadcast/new_month.html`), the current `month_key` (YYYY-MM), "
            "the active-user `recipient_count`, and whether this month was `already_sent`. Nothing is queued.\n"
            "- With `?confirm=yes`: creates a `Broadcast(kind=new_month)` record and queues delivery via Celery — "
            "one in-app Notification per user plus one email each rendered from the template. "
            "Returns the record immediately with HTTP 202; actual delivery continues in the background.\n\n"
            "Delivery tracking: `total` = recipients targeted, `sent_count` = emails confirmed delivered, "
            "`failed_count` = emails failed after retries. Final `status` is `sent` (all delivered), "
            "`partial` (some failed), or `failed` (none delivered); follow-up detail via `GET /broadcast/`.\n\n"
            "Idempotency: one send per calendar month. Re-sending the same `month_key` returns 400 "
            "unless `?force=yes`. Responses are `Cache-Control: no-store` (safe to re-click). "
            "Requires superuser JWT (`is_superuser=True`); otherwise 403."
        ),
        parameters=[
            OpenApiParameter("confirm", OpenApiTypes.STR, required=False, description="Set to 'yes' to queue the broadcast; omit for preview only"),
            OpenApiParameter("force", OpenApiTypes.STR, required=False, description="Set to 'yes' to resend when this month was already sent"),
            OpenApiParameter("title", OpenApiTypes.STR, required=False, description="Override the greeting title. Default: 'Happy New Month — <Month Year>!'"),
            OpenApiParameter("message", OpenApiTypes.STR, required=False, description="Override the greeting body text"),
            OpenApiParameter("email_subject", OpenApiTypes.STR, required=False, description="Override the email subject. Default: 'BlueSea Mobile — <title>'"),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            202: BroadcastSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Preview",
                summary="Dry-run preview (no confirm)",
                value={
                    "kind": "new_month",
                    "month_key": "2026-10",
                    "title": "Happy New Month — October 2026!",
                    "message": "Happy New Month, and welcome to October 2026! Thank you for choosing BlueSea Mobile.",
                    "email_subject": "BlueSea Mobile — Happy New Month — October 2026!",
                    "template": "broadcast/new_month.html",
                    "recipient_count": 1250,
                    "already_sent": False,
                    "hint": "Add ?confirm=yes to queue the broadcast",
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Queued",
                summary="Broadcast accepted for delivery",
                value={
                    "id": 3,
                    "kind": "new_month",
                    "title": "Happy New Month — October 2026!",
                    "message": "Happy New Month, and welcome to October 2026! Thank you for choosing BlueSea Mobile.",
                    "email_subject": "BlueSea Mobile — Happy New Month — October 2026!",
                    "template": "broadcast/new_month.html",
                    "month_key": "2026-10",
                    "status": "pending",
                    "total": 1250,
                    "sent_count": 0,
                    "failed_count": 0,
                    "created_by": 1,
                    "created_at": "2026-10-01T08:00:00Z",
                    "completed_at": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
            OpenApiExample(
                "Already sent",
                summary="Duplicate for the same month",
                value={"error": "New month broadcast for 2026-10 already sent. Use ?force=yes to resend."},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Forbidden",
                summary="Non-superuser",
                value={"detail": "You do not have permission to perform this action."},
                response_only=True,
                status_codes=["403"],
            ),
        ],
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
            "Send the one-shot domain-change notice to every active user, or preview it first.\n\n"
            "- Without `?confirm=yes`: dry-run preview. Returns the resolved title/message/subject, "
            "the editable template (`broadcast/important.html`), the active-user `recipient_count`, "
            "and whether the notice was `already_sent`. Nothing is queued.\n"
            "- With `?confirm=yes`: creates a `Broadcast(kind=important)` record and queues delivery via Celery — "
            "one in-app Notification per user plus one email each rendered from the template. "
            "Default copy informs users the platform moved from `blueseamobile.com.ng` to `blueseamobile.com` "
            "(accounts, wallet balances, and PINs unchanged). Returns the record immediately with HTTP 202; "
            "actual delivery continues in the background.\n\n"
            "Delivery tracking: `total` = recipients targeted, `sent_count` = emails confirmed delivered, "
            "`failed_count` = emails failed after retries. Final `status` is `sent` (all delivered), "
            "`partial` (some failed), or `failed` (none delivered); follow-up detail via `GET /broadcast/`.\n\n"
            "Idempotency: the notice sends once. Re-sending returns 400 unless `?force=yes`. "
            "Responses are `Cache-Control: no-store` (safe to re-click). "
            "Requires superuser JWT (`is_superuser=True`); otherwise 403."
        ),
        parameters=[
            OpenApiParameter("confirm", OpenApiTypes.STR, required=False, description="Set to 'yes' to queue the broadcast; omit for preview only"),
            OpenApiParameter("force", OpenApiTypes.STR, required=False, description="Set to 'yes' to resend when already sent"),
            OpenApiParameter("title", OpenApiTypes.STR, required=False, description="Override the notice title. Default: 'Important: We have moved to blueseamobile.com'"),
            OpenApiParameter("message", OpenApiTypes.STR, required=False, description="Override the notice body text"),
            OpenApiParameter("email_subject", OpenApiTypes.STR, required=False, description="Override the email subject. Default: 'BlueSea Mobile — Important domain change'"),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            202: BroadcastSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Preview",
                summary="Dry-run preview (no confirm)",
                value={
                    "kind": "important",
                    "title": "Important: We have moved to blueseamobile.com",
                    "message": "Hello from BlueSea Mobile! Please note our platform has moved from blueseamobile.com.ng to blueseamobile.com.",
                    "email_subject": "BlueSea Mobile — Important domain change",
                    "template": "broadcast/important.html",
                    "recipient_count": 1250,
                    "already_sent": False,
                    "hint": "Add ?confirm=yes to queue the broadcast",
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Queued",
                summary="Broadcast accepted for delivery",
                value={
                    "id": 4,
                    "kind": "important",
                    "title": "Important: We have moved to blueseamobile.com",
                    "message": "Hello from BlueSea Mobile! Please note our platform has moved from blueseamobile.com.ng to blueseamobile.com.",
                    "email_subject": "BlueSea Mobile — Important domain change",
                    "template": "broadcast/important.html",
                    "month_key": None,
                    "status": "pending",
                    "total": 1250,
                    "sent_count": 0,
                    "failed_count": 0,
                    "created_by": 1,
                    "created_at": "2026-10-01T08:05:00Z",
                    "completed_at": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
            OpenApiExample(
                "Already sent",
                summary="Duplicate notice",
                value={"error": "Important broadcast already sent. Use ?force=yes to resend."},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Forbidden",
                summary="Non-superuser",
                value={"detail": "You do not have permission to perform this action."},
                response_only=True,
                status_codes=["403"],
            ),
        ],
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


class AnnouncementBroadcastView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        summary="Broadcast general announcement (superuser)",
        description=(
            "Send a reusable general announcement to every active user, or preview it first.\n\n"
            "- Without `?confirm=yes`: dry-run preview. Returns the resolved title/message/subject, "
            "the editable template (`broadcast/announcement.html`), the active-user `recipient_count`, "
            "and whether an announcement was `already_sent`. Nothing is queued. "
            "Both copy and template are meant to change per announcement — override via query params "
            "or edit the template file.\n"
            "- With `?confirm=yes`: creates a `Broadcast(kind=announcement)` record and queues delivery via Celery — "
            "one in-app Notification per user plus one email each rendered from the template. "
            "Returns the record immediately with HTTP 202; actual delivery continues in the background.\n\n"
            "Delivery tracking: `total` = recipients targeted, `sent_count` = emails confirmed delivered, "
            "`failed_count` = emails failed after retries. Final `status` is `sent` (all delivered), "
            "`partial` (some failed), or `failed` (none delivered); follow-up detail via `GET /broadcast/`.\n\n"
            "Idempotency: one-shot. Re-sending returns 400 unless `?force=yes` (use force for the next "
            "announcement). Responses are `Cache-Control: no-store` (safe to re-click). "
            "Requires superuser JWT (`is_superuser=True`); otherwise 403."
        ),
        parameters=[
            OpenApiParameter("confirm", OpenApiTypes.STR, required=False, description="Set to 'yes' to queue the broadcast; omit for preview only"),
            OpenApiParameter("force", OpenApiTypes.STR, required=False, description="Set to 'yes' to send a new announcement when one was already sent"),
            OpenApiParameter("title", OpenApiTypes.STR, required=False, description="Override the announcement title"),
            OpenApiParameter("message", OpenApiTypes.STR, required=False, description="Override the announcement body text"),
            OpenApiParameter("email_subject", OpenApiTypes.STR, required=False, description="Override the email subject"),
        ],
        responses={
            200: OpenApiTypes.OBJECT,
            202: BroadcastSerializer,
            400: OpenApiTypes.OBJECT,
            403: OpenApiTypes.OBJECT,
        },
        examples=[
            OpenApiExample(
                "Preview",
                summary="Dry-run preview (no confirm)",
                value={
                    "kind": "announcement",
                    "title": "Thank You for Celebrating with Us!",
                    "message": "Thank you for coming out on Saturday, October 3rd! Your presence at the BlueSea Mobile event meant the world to us.",
                    "email_subject": "BlueSea Mobile — Thank You!",
                    "template": "broadcast/announcement.html",
                    "recipient_count": 1250,
                    "already_sent": False,
                    "hint": "Add ?confirm=yes to queue the broadcast",
                },
                response_only=True,
                status_codes=["200"],
            ),
            OpenApiExample(
                "Queued",
                summary="Broadcast accepted for delivery",
                value={
                    "id": 5,
                    "kind": "announcement",
                    "title": "Thank You for Celebrating with Us!",
                    "message": "Thank you for coming out on Saturday, October 3rd! Your presence at the BlueSea Mobile event meant the world to us.",
                    "email_subject": "BlueSea Mobile — Thank You!",
                    "template": "broadcast/announcement.html",
                    "month_key": None,
                    "status": "pending",
                    "total": 1250,
                    "sent_count": 0,
                    "failed_count": 0,
                    "created_by": 1,
                    "created_at": "2026-10-03T08:00:00Z",
                    "completed_at": None,
                },
                response_only=True,
                status_codes=["202"],
            ),
            OpenApiExample(
                "Already sent",
                summary="Duplicate announcement",
                value={"error": "Announcement already sent. Use ?force=yes to send a new one."},
                response_only=True,
                status_codes=["400"],
            ),
            OpenApiExample(
                "Forbidden",
                summary="Non-superuser",
                value={"detail": "You do not have permission to perform this action."},
                response_only=True,
                status_codes=["403"],
            ),
        ],
        tags=["Broadcast"],
    )
    def get(self, request):
        title, message, email_subject = _announcement_defaults(request)
        already_sent = Broadcast.objects.filter(
            kind="announcement", status__in=["sending", "sent", "partial"]
        ).exists()

        confirm = (request.query_params.get("confirm") or "").lower() == "yes"
        if not confirm:
            return _no_store(Response({
                "kind": "announcement",
                "title": title,
                "message": message,
                "email_subject": email_subject,
                "template": ANNOUNCEMENT_TEMPLATE,
                "recipient_count": _recipient_count(),
                "already_sent": already_sent,
                "hint": "Add ?confirm=yes to queue the broadcast",
            }))

        force = (request.query_params.get("force") or "").lower() == "yes"
        if already_sent and not force:
            return _no_store(Response(
                {"error": "Announcement already sent. Use ?force=yes to send a new one."},
                status=status.HTTP_400_BAD_REQUEST,
            ))

        broadcast = Broadcast.objects.create(
            kind="announcement",
            title=title,
            message=message,
            email_subject=email_subject,
            template=ANNOUNCEMENT_TEMPLATE,
            status="pending",
            total=_recipient_count(),
            created_by=request.user,
        )
        from .tasks import send_broadcast

        send_broadcast.delay(broadcast.id)
        logger.info(f"Superuser {request.user.email} queued announcement broadcast {broadcast.id}")
        return _no_store(Response(
            BroadcastSerializer(broadcast).data, status=status.HTTP_202_ACCEPTED
        ))


class BroadcastHistoryView(APIView):
    permission_classes = [IsSuperUser]

    @extend_schema(
        summary="List broadcasts (superuser)",
        description=(
            "Newest-first history of queued broadcasts (latest 50). Each entry carries the delivery counters "
            "(`total`, `sent_count`, `failed_count`) and final `status` (`pending`, `sending`, `sent`, "
            "`partial`, `failed`) with `completed_at` set once `sent_count + failed_count` reaches `total`. "
            "Requires superuser JWT (`is_superuser=True`); otherwise 403."
        ),
        responses={200: BroadcastSerializer(many=True), 403: OpenApiTypes.OBJECT},
        examples=[
            OpenApiExample(
                "History",
                summary="Latest broadcasts with delivery status",
                value=[
                    {
                        "id": 4,
                        "kind": "important",
                        "title": "Important: We have moved to blueseamobile.com",
                        "status": "sent",
                        "total": 1250,
                        "sent_count": 1250,
                        "failed_count": 0,
                        "created_at": "2026-10-01T08:05:00Z",
                        "completed_at": "2026-10-01T08:12:00Z",
                    },
                    {
                        "id": 3,
                        "kind": "new_month",
                        "title": "Happy New Month — October 2026!",
                        "status": "partial",
                        "total": 1250,
                        "sent_count": 1248,
                        "failed_count": 2,
                        "created_at": "2026-10-01T08:00:00Z",
                        "completed_at": "2026-10-01T08:09:00Z",
                    },
                ],
                response_only=True,
                status_codes=["200"],
            ),
        ],
        tags=["Broadcast"],
    )
    def get(self, request):
        broadcasts = Broadcast.objects.all().order_by("-created_at")[:50]
        return _no_store(Response(BroadcastSerializer(broadcasts, many=True).data))
