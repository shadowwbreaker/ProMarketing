from django.db import transaction

from common.hashchain import compute_hash

from .models import AuditLog

GENESIS = "0" * 64
_LOCK_KEY = 7_202_611  # advisory lock id for the audit chain


def record(*, action: str, subject_type: str, subject_id, actor=None, is_staff_action: bool = False, order_id=None,
           before: dict | None = None, after: dict | None = None, reason: str = "", comment: str = "", ip=None) -> AuditLog:
    """Append a hash-chained audit entry. Serialised by a PostgreSQL advisory lock."""
    from django.db import connection

    with transaction.atomic():
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", [_LOCK_KEY])
        last = AuditLog.objects.order_by("-seq").values("seq", "hash").first()
        seq = (last["seq"] + 1) if last else 1
        prev_hash = last["hash"] if last else GENESIS
        payload = {
            "seq": seq, "action": action, "subject_type": subject_type, "subject_id": str(subject_id),
            "actor": str(actor.pk) if actor else None, "order_id": str(order_id) if order_id else None,
            "before": before or {}, "after": after or {}, "reason": reason, "comment": comment,
        }
        return AuditLog.objects.create(
            actor=actor, is_staff_action=is_staff_action, action=action, subject_type=subject_type,
            subject_id=str(subject_id), order_id=order_id, before=before or {}, after=after or {},
            reason=reason, comment=comment, ip=ip, seq=seq, prev_hash=prev_hash, hash=compute_hash(prev_hash, payload),
        )


def verify_chain() -> tuple[bool, int | None]:
    """Recompute the chain. Returns (ok, first_broken_seq)."""
    prev = GENESIS
    for e in AuditLog.objects.order_by("seq").iterator():
        payload = {
            "seq": e.seq, "action": e.action, "subject_type": e.subject_type, "subject_id": e.subject_id,
            "actor": str(e.actor_id) if e.actor_id else None, "order_id": str(e.order_id) if e.order_id else None,
            "before": e.before, "after": e.after, "reason": e.reason, "comment": e.comment,
        }
        if e.prev_hash != prev or compute_hash(prev, payload) != e.hash:
            return False, e.seq
        prev = e.hash
    return True, None
