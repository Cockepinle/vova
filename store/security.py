from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from math import ceil

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import AdminLoginAttempt, AdminLoginThrottleBucket


@dataclass(frozen=True)
class LoginThrottleDecision:
    allowed: bool
    retry_after_seconds: int = 0


def _bucket_hashes(username: str, remote_address: str) -> list[str]:
    normalized_username = username.strip().casefold()[:254]
    parts = [f"ip:{remote_address}"]
    if normalized_username:
        parts.append(f"username:{normalized_username}")
    return sorted(sha256(part.encode("utf-8")).hexdigest() for part in parts)


def _locked_buckets(hashes: list[str], now):
    for key_hash in hashes:
        AdminLoginThrottleBucket.objects.get_or_create(
            key_hash=key_hash,
            defaults={"window_started_at": now},
        )
    return list(
        AdminLoginThrottleBucket.objects.select_for_update()
        .filter(key_hash__in=hashes)
        .order_by("key_hash")
    )


def check_admin_login_allowed(username: str, remote_address: str) -> LoginThrottleDecision:
    now = timezone.now()
    window = settings.ADMIN_LOGIN_WINDOW_SECONDS
    hashes = _bucket_hashes(username, remote_address)
    with transaction.atomic():
        buckets = _locked_buckets(hashes, now)
        retry_after = 0
        for bucket in buckets:
            if bucket.locked_until and bucket.locked_until > now:
                retry_after = max(retry_after, ceil((bucket.locked_until - now).total_seconds()))
            elif (now - bucket.window_started_at).total_seconds() >= window:
                bucket.failure_count = 0
                bucket.locked_until = None
                bucket.window_started_at = now
                bucket.save(update_fields=["failure_count", "locked_until", "window_started_at", "updated_at"])
        if retry_after:
            return LoginThrottleDecision(False, retry_after)
    return LoginThrottleDecision(True)


def record_admin_login_attempt(
    username: str,
    remote_address: str,
    outcome: str,
    user=None,
) -> None:
    now = timezone.now()
    with transaction.atomic():
        AdminLoginAttempt.objects.create(
            username=username.strip()[:254],
            remote_address=remote_address or None,
            outcome=outcome,
            user=user,
        )
        hashes = _bucket_hashes(username, remote_address)
        buckets = _locked_buckets(hashes, now)
        for bucket in buckets:
            if outcome == AdminLoginAttempt.OUTCOME_SUCCESS:
                bucket.failure_count = 0
                bucket.locked_until = None
                bucket.window_started_at = now
            elif outcome == AdminLoginAttempt.OUTCOME_FAILURE:
                if (now - bucket.window_started_at).total_seconds() >= settings.ADMIN_LOGIN_WINDOW_SECONDS:
                    bucket.failure_count = 0
                    bucket.window_started_at = now
                bucket.failure_count += 1
                if bucket.failure_count >= settings.ADMIN_LOGIN_MAX_ATTEMPTS:
                    bucket.locked_until = now + timedelta(seconds=settings.ADMIN_LOGIN_LOCKOUT_SECONDS)
            else:
                continue
            bucket.save(update_fields=["failure_count", "locked_until", "window_started_at", "updated_at"])
