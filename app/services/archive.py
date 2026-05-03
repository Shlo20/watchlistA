"""Auto-archive service: marks stale pending requests as DONE."""
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.models.request import Request, RequestHistory, RequestStatus


def archive_stale_pending_requests(db: Session, max_age_hours: int = 48) -> int:
    """Set status=DONE on every PENDING request older than max_age_hours.

    Records a RequestHistory entry with changed_by=None to indicate this was
    a system action, not a user action. Returns the number of requests archived.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    stale = (
        db.query(Request)
        .filter(Request.status == RequestStatus.PENDING, Request.created_at < cutoff)
        .all()
    )

    for req in stale:
        req.status = RequestStatus.DONE
        db.add(RequestHistory(
            request_id=req.id,
            status=RequestStatus.DONE,
            changed_by=None,
        ))

    db.commit()
    return len(stale)
