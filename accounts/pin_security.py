from dataclasses import dataclass

from django.conf import settings
from django.utils import timezone


@dataclass
class PinResult:
    ok: bool
    locked: bool
    retry_after: float  # seconds until lock expires (0 if not locked)
    attempts_remaining: int


def verify_pin_with_lockout(user, encrypted_pin) -> PinResult:
    """Verify an encrypted transaction PIN while enforcing per-account lockout.

    - Returns `locked=True` if the account is currently locked (no decryption attempted).
    - On success resets the failure counter.
    - On failure increments the counter and locks the account after
      PIN_MAX_ATTEMPTS consecutive failures for PIN_LOCKOUT_MINUTES.
    """
    max_attempts = getattr(settings, "PIN_MAX_ATTEMPTS", 5)
    lockout_minutes = getattr(settings, "PIN_LOCKOUT_MINUTES", 15)

    now = timezone.now()

    # Currently locked?
    if user.pin_locked_until and user.pin_locked_until > now:
        retry_after = (user.pin_locked_until - now).total_seconds()
        return PinResult(
            ok=False, locked=True, retry_after=retry_after, attempts_remaining=0
        )

    # Expired lock -> clear so the user gets a fresh attempt budget.
    if user.pin_locked_until and user.pin_locked_until <= now:
        user.pin_locked_until = None
        user.pin_failed_attempts = 0
        user.save(update_fields=["pin_failed_attempts", "pin_locked_until"])

    verified = user.verify_transaction_pin(encrypted_pin)

    if verified:
        if user.pin_failed_attempts or user.pin_locked_until:
            user.pin_failed_attempts = 0
            user.pin_locked_until = None
            user.save(update_fields=["pin_failed_attempts", "pin_locked_until"])
        return PinResult(
            ok=True, locked=False, retry_after=0, attempts_remaining=max_attempts
        )

    # Failed attempt
    user.pin_failed_attempts = (user.pin_failed_attempts or 0) + 1
    attempts_remaining = max(0, max_attempts - user.pin_failed_attempts)
    locked_now = False
    retry_after = 0.0

    if user.pin_failed_attempts >= max_attempts:
        user.pin_locked_until = now + timezone.timedelta(minutes=lockout_minutes)
        locked_now = True
        retry_after = (user.pin_locked_until - now).total_seconds()

    user.save(update_fields=["pin_failed_attempts", "pin_locked_until"])
    return PinResult(
        ok=False,
        locked=locked_now,
        retry_after=retry_after,
        attempts_remaining=attempts_remaining,
    )
