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

ORCHESTRATOR_PROMPT = f"""
You are a strategy orchestrator for an ADHD tips X account.
Assess the account's current state and call the correct strategy tool.

Decision criteria:
- Under {WARMUP_THRESHOLD} posts → warmup strategy (post more, follow less)
- {WARMUP_THRESHOLD}+ posts → growth strategy (balanced posting and following)

Always provide a clear reason for your choice.
"""


def run_orchestrator(x_client, db) -> None:
    stats = db.get_account_stats()
    post_count = stats["post_count"]
    logger.info(f"Orchestrator starting. Account stats: {stats}")

    def make_orchestrator_tools(x_client, db):
        @beta_tool
        def run_warmup_strategy(reason: str) -> str:
            """Run the warmup agent. Use for new accounts with fewer than 50 posts."""
            logger.info(f"Running warmup strategy. Reason: {reason}")
            db.log_agent_run("warmup", reason, post_count)
            agent = WarmupAgent(x_client, db)
            summary = agent.run("Run your warmup tasks now.")
            logger.info(f"Warmup agent summary: {summary}")
            return f"Warmup agent completed. Summary: {summary}"

        @beta_tool
        def run_growth_strategy(reason: str) -> str:
            """Run the growth agent. Use for established accounts with 50+ posts."""
            logger.info(f"Running growth strategy. Reason: {reason}")
            db.log_agent_run("growth", reason, post_count)
            agent = GrowthAgent(x_client, db)
            summary = agent.run("Run your growth tasks now.")
            logger.info(f"Growth agent summary: {summary}")
            return f"Growth agent completed. Summary: {summary}"

        return [run_warmup_strategy, run_growth_strategy]

    client = Anthropic()
    tools = make_orchestrator_tools(x_client, db)

    runner = client.beta.messages.tool_runner(
        model=MODEL,
        system=ORCHESTRATOR_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Account stats: {json.dumps(stats)}. Select and run the best strategy.",
        }],
        tools=tools,
        max_tokens=ORCHESTRATOR_MAX_TOKENS,
    )
    runner.until_done()
    logger.info("Orchestrator run complete.")
