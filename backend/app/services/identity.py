"""Identity persistence for trusted callers. The caller owns commit/rollback."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import ApplicationUser


class IdentityError(ValueError):
    pass


def validate_identity(issuer: str, subject: str) -> None:
    for value, maximum in ((issuer, 512), (subject, 255)):
        if not isinstance(value, str) or not value or value != value.strip() or len(value) > maximum:
            raise IdentityError("Identity must contain a nonblank, bounded issuer and subject without surrounding whitespace.")


def ensure_application_user(session: Session, issuer: str, subject: str) -> ApplicationUser:
    """Insert or find the exact identity; never commit, rename, or reactivate it.

    The operator or a future verified-token boundary supplies these strings.
    This function itself does not authenticate their origin.
    """
    validate_identity(issuer, subject)
    session.execute(insert(ApplicationUser).values(issuer=issuer, subject=subject).on_conflict_do_nothing(
        constraint="uq_application_users_issuer_subject",
    ))
    user = session.scalar(select(ApplicationUser).where(
        ApplicationUser.issuer == issuer, ApplicationUser.subject == subject,
    ).execution_options(populate_existing=True))
    if not user.is_active:
        raise IdentityError("The application user is inactive; bootstrap cannot reactivate it.")
    return user
