"""Explicit local operator identity/membership grant; never invoked by startup."""

import argparse
import sys

from sqlalchemy.orm import Session

from app.cognito import CognitoConfigurationError, configured_issuer
from app.db import SessionLocal, engine
from app.models import MembershipRole, WorkspaceMembership
from app.services.identity import IdentityError, ensure_application_user, validate_identity
from app.services.memberships import MembershipError, ensure_membership, lock_workspace, validate_role


class SafeArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse's normal errors can echo arbitrary submitted values.
        self.print_usage(sys.stderr)
        self.exit(2, "Bootstrap arguments are invalid; use --help for the required options.\n")


def ensure_bootstrap_membership(session: Session, *, issuer: str, subject: str, workspace_slug: str, role: str) -> WorkspaceMembership:
    """Noncommitting operation; supplied issuer is trusted operator configuration."""
    validate_identity(issuer, subject)
    validate_role(role)
    if not workspace_slug or workspace_slug != workspace_slug.strip() or len(workspace_slug) > 64:
        raise MembershipError("Use an existing nonblank workspace slug without surrounding whitespace.")
    # Require and lock the workspace before creating a user. Never seed it here.
    workspace = lock_workspace(session, workspace_slug=workspace_slug)
    user = ensure_application_user(session, issuer, subject)
    return ensure_membership(session, workspace.id, user.id, role)


def bootstrap_membership(session: Session, **values) -> WorkspaceMembership:
    """Transaction owner: one explicit commit, or rollback of the whole grant."""
    try:
        membership = ensure_bootstrap_membership(session, **values)
        session.commit()
        return membership
    except BaseException:
        session.rollback()
        raise


def main(argv: list[str] | None = None) -> int:
    parser = SafeArgumentParser(description=__doc__)
    parser.add_argument("--subject", required=True, help="Copied Cognito sub for the intended person, never an email lookup.")
    parser.add_argument("--workspace-slug", required=True, help="Slug of a workspace that already exists.")
    parser.add_argument("--role", required=True, choices=[role.value for role in MembershipRole])
    args = parser.parse_args(argv)
    try:
        issuer = configured_issuer()
        validate_identity(issuer, args.subject)
        with SessionLocal() as session:
            membership = bootstrap_membership(session, issuer=issuer, subject=args.subject, workspace_slug=args.workspace_slug, role=args.role)
            print(f"Membership ready: application_user_id={membership.application_user_id} workspace_id={membership.workspace_id} role={membership.role}.")
        return 0
    except (CognitoConfigurationError, IdentityError, MembershipError) as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("Membership bootstrap failed; check database availability and apply migrations first. No partial grant was saved.", file=sys.stderr)
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
