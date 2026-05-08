"""
research_phase.py — Pre-run database read that surfaces candidate posts for engagement.

No X API calls are made here; the warmup and growth agents already populate
discovered_posts during their normal runs.
"""

from dataclasses import dataclass, field


@dataclass
class ResearchResult:
    posts: list[dict] = field(default_factory=list)


def run_research_phase(db) -> ResearchResult:
    posts = db.get_recent_unevaluated_posts()
    return ResearchResult(posts=posts)
