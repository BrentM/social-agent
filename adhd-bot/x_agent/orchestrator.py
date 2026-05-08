"""
orchestrator.py — Top-level strategy selection agent.

Reads account stats from Supabase, reasons about the best strategy,
and delegates to WarmupAgent or GrowthAgent.
"""

import json
from anthropic import Anthropic, beta_tool
from loguru import logger
from x_agent.config import MODEL, ORCHESTRATOR_MAX_TOKENS, WARMUP_THRESHOLD
from x_agent.agents.warmup_agent import WarmupAgent
from x_agent.agents.growth_agent import GrowthAgent
from x_agent.agents.engagement_agent import EngagementAgent
from x_agent.research_phase import run_research_phase

ORCHESTRATOR_PROMPT = f"""
You are a strategy orchestrator for an ADHD tips X account.
Assess the account's current state and call the correct strategy tool.

Decision criteria:
- Under {WARMUP_THRESHOLD} posts → warmup strategy (post more, follow less)
- {WARMUP_THRESHOLD}+ posts → growth strategy (balanced posting and following)

If high-performing posts are provided, also run the engagement strategy after the posting strategy.

Always provide a clear reason for your choices.
"""


def run_orchestrator(x_client, db) -> None:
    stats = db.get_account_stats()
    post_count = stats["post_count"]
    research = run_research_phase(db)
    logger.info(f"Orchestrator starting. Account stats: {stats}. Research posts found: {len(research.posts)}")

    def make_orchestrator_tools(x_client, db):
        @beta_tool
        def run_warmup_strategy(reason: str) -> str:
            """Run the warmup agent. Use for new accounts with fewer than 12 posts."""
            logger.info(f"Running warmup strategy. Reason: {reason}")
            db.log_agent_run("warmup", reason, post_count)
            agent = WarmupAgent(x_client, db)
            summary = agent.run("Run your warmup tasks now.")
            logger.info(f"Warmup agent summary: {summary}")
            return f"Warmup agent completed. Summary: {summary}"

        @beta_tool
        def run_growth_strategy(reason: str) -> str:
            """Run the growth agent. Use for established accounts with 12+ posts."""
            logger.info(f"Running growth strategy. Reason: {reason}")
            db.log_agent_run("growth", reason, post_count)
            agent = GrowthAgent(x_client, db)
            summary = agent.run("Run your growth tasks now.")
            logger.info(f"Growth agent summary: {summary}")
            return f"Growth agent completed. Summary: {summary}"

        @beta_tool
        def run_engagement_strategy(reason: str, candidate_post_ids: list[str]) -> str:
            """Run the engagement agent to evaluate and optionally reply to high-performing posts.
            Pass the x_post_id values of candidate posts found during research.
            Use when research surfaced one or more posts with strong engagement."""
            logger.info(f"Running engagement strategy. Candidates: {candidate_post_ids}. Reason: {reason}")
            agent = EngagementAgent(x_client, db)
            agent.run(reason=reason, candidate_ids=candidate_post_ids)
            return "Engagement agent completed."

        return [run_warmup_strategy, run_growth_strategy, run_engagement_strategy]

    user_message = f"""Account stats: {json.dumps(stats)}

High-performing posts found during research ({len(research.posts)} total):
{json.dumps(research.posts)}

Select and run the correct posting strategy. If high-performing posts are listed above, also run the engagement strategy."""

    client = Anthropic()
    tools = make_orchestrator_tools(x_client, db)

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        system=ORCHESTRATOR_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=tools,
        max_tokens=ORCHESTRATOR_MAX_TOKENS,
    )
    runner.until_done()
    logger.info("Orchestrator run complete.")
