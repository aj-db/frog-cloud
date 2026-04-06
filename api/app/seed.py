"""Seed dev tenant and default crawl profiles. Run: python -m app.seed (from api/)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure `api/` is on path when executed as script
_API_ROOT = Path(__file__).resolve().parent.parent
if str(_API_ROOT) not in sys.path:
    sys.path.insert(0, str(_API_ROOT))

from sqlalchemy import select  # noqa: E402

from app.db import session_scope  # noqa: E402
from app.models import CrawlProfile, Tenant  # noqa: E402


def _repo_root() -> Path:
    return _API_ROOT.parent


def _default_profiles() -> list[tuple[str, str, str]]:
    """Name, description, relative path under repo configs/."""
    cfg = _repo_root() / "configs"
    patterns = [
        ("Standard audit", "Balanced technical SEO audit", "standard-audit.seospiderconfig"),
        ("Full JS rendering", "Render JavaScript-heavy sites", "full-js-rendering.seospiderconfig"),
        ("Content focus", "Content-oriented crawl", "content-focus.seospiderconfig"),
        ("Links only", "Fast link discovery", "links-only.seospiderconfig"),
    ]
    out: list[tuple[str, str, str]] = []
    for name, desc, fname in patterns:
        path = cfg / fname
        if path.exists():
            out.append((name, desc, str(path.resolve())))
    return out


def main() -> None:
    clerk_org = os.environ.get("DEV_CLERK_ORG_ID", "org_dev_frog")
    tenant_name = os.environ.get("DEV_TENANT_NAME", "Development Tenant")

    profiles = _default_profiles()
    with session_scope() as db:
        existing = db.execute(select(Tenant).where(Tenant.clerk_org_id == clerk_org)).scalar_one_or_none()
        if existing:
            tenant = existing
            tenant.name = tenant_name
            db.add(tenant)
        else:
            tenant = Tenant(clerk_org_id=clerk_org, name=tenant_name, plan="dev", settings={})
            db.add(tenant)
        db.flush()
        for name, desc, config_path in profiles:
            prof = db.execute(
                select(CrawlProfile).where(
                    CrawlProfile.tenant_id == tenant.id,
                    CrawlProfile.name == name,
                )
            ).scalar_one_or_none()
            if prof:
                prof.description = desc
                prof.config_path = config_path
                db.add(prof)
            else:
                db.add(
                    CrawlProfile(
                        tenant_id=tenant.id,
                        name=name,
                        description=desc,
                        config_path=config_path,
                    )
                )

    print(f"Seeded tenant clerk_org_id={clerk_org!r} with {len(profiles)} profiles.")


if __name__ == "__main__":
    main()
