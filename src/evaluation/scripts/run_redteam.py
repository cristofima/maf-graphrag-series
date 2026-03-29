"""
Run red team safety scan against the GraphRAG agent.

Uses Azure AI Evaluation SDK's RedTeam class with attack strategies
to probe the agent for safety vulnerabilities.

REQUIRES Azure AI Foundry project — the RedTeam class needs a Foundry
project connection for adversarial LLM generation.

Usage:
    poetry run python -m evaluation.scripts.run_redteam
    poetry run python -m evaluation.scripts.run_redteam --strategies baseline jailbreak
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from dotenv import load_dotenv

load_dotenv()

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from evaluation.config import EvalConfig

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
DEFAULT_RISK_CATEGORIES = ("Violence", "HateUnfairness", "Sexual", "SelfHarm")
DEFAULT_RETEAM_FLOW = "cloud-model"
SUPPORTED_REDTEAM_FLOWS = ("cloud-model", "local-agent")
AI_SCOPE = "https://ai.azure.com/.default"
NEW_FOUNDRY_TIMEOUT_SECONDS = 300
NEW_FOUNDRY_POLL_SECONDS = 5
NEW_FOUNDRY_DEFAULT_ATTACK_STRATEGIES = ["Base64", "Flip"]
ZERO_ATTACKS_ERROR = (
    "Red team scan completed but produced zero evaluated attacks. "
    "This usually means the selected Azure AI Foundry region does not support the required "
    "RAI safety capability (for example content harm scoring). "
    "Move the Foundry project to a supported region and rerun Step 4."
)


def _normalize_redteam_flow(flow: str | None) -> str:
    """Resolve and validate red team execution flow.

    Args:
        flow: Explicit CLI flow value. When omitted, falls back to REDTEAM_FLOW
            env var, then to the default cloud flow.

    Returns:
        Normalized flow identifier.

    Raises:
        ValueError: If the provided flow is not supported.
    """
    resolved_flow = flow or os.environ.get("REDTEAM_FLOW", DEFAULT_RETEAM_FLOW)
    normalized_flow = resolved_flow.strip().lower()

    if normalized_flow not in SUPPORTED_REDTEAM_FLOWS:
        supported = ", ".join(SUPPORTED_REDTEAM_FLOWS)
        raise ValueError(f"Unsupported red team flow '{resolved_flow}'. Supported flows: {supported}.")

    return normalized_flow


def _build_strategy_map(attack_strategy_cls: Any) -> dict[str, Any]:
    """Build strategy-name mapping to AttackStrategy enum values."""
    return {
        "baseline": attack_strategy_cls.Baseline,
        "jailbreak": attack_strategy_cls.Jailbreak,
        "crescendo": attack_strategy_cls.Crescendo,
        "easy": attack_strategy_cls.EASY,
        "moderate": attack_strategy_cls.MODERATE,
        "difficult": attack_strategy_cls.DIFFICULT,
        "multiturn": attack_strategy_cls.MultiTurn,
    }


def _resolve_attack_strategies(
    strategies: list[str] | None,
    strategy_map: dict[str, Any],
    attack_strategy_cls: Any,
) -> list[Any]:
    """Resolve CLI strategy names to SDK AttackStrategy values."""
    if strategies:
        return [strategy_map[s.lower()] for s in strategies if s.lower() in strategy_map]
    return [attack_strategy_cls.Baseline, attack_strategy_cls.EASY]


def _resolve_azure_ai_project(config: EvalConfig) -> str:
    """Resolve Azure AI project URL for red teaming."""
    if config.azure_ai_project:
        logger.info("Using Azure AI project endpoint for red teaming: %s", config.azure_ai_project)
        return str(config.azure_ai_project)

    raise ValueError("AZURE_AI_PROJECT is required for Step 4 red teaming.")


def _build_cloud_model_target(config: EvalConfig) -> dict[str, str]:
    """Build cloud-model red team target from Azure OpenAI config.

    Args:
        config: Evaluation configuration loaded from environment.

    Returns:
        Model target dictionary accepted by ``RedTeam.scan(target=...)``.
    """
    return {
        "azure_endpoint": config.azure_endpoint,
        "api_key": config.api_key,
        "azure_deployment": config.chat_deployment,
        "api_version": config.api_version,
    }


def _resolve_scan_target(config: EvalConfig, flow: str) -> Any:
    """Resolve scan target based on selected red teaming flow.

    Args:
        config: Evaluation configuration.
        flow: Red teaming flow, normalized by ``_normalize_redteam_flow``.

    Returns:
        Target value accepted by ``RedTeam.scan``.
    """
    if flow == "cloud-model":
        logger.info(
            "Running Step 4 in cloud-model flow against Azure OpenAI deployment '%s'.",
            config.chat_deployment,
        )
        return _build_cloud_model_target(config)

    logger.info("Running Step 4 in local-agent flow against Knowledge Captain callback target.")
    return _graphrag_agent_target


def _extract_text_from_item(item: object) -> str:
    """Extract text from a chat content item."""
    if isinstance(item, str):
        return item

    if isinstance(item, dict):
        if item.get("type") in {"text", "input_text", "output_text"}:
            return str(item.get("text", ""))
        return ""

    return str(getattr(item, "text", "") or "")


def _extract_query_from_messages(messages: list[object]) -> str:
    """Extract the latest user query from OpenAI chat-protocol messages."""
    if not messages:
        return ""

    latest = messages[-1]
    latest_content = latest.get("content", "") if isinstance(latest, dict) else getattr(latest, "content", "")

    if isinstance(latest_content, str):
        return latest_content

    if not isinstance(latest_content, list):
        return ""

    text_chunks = [_extract_text_from_item(item) for item in latest_content]
    return "\n".join(chunk for chunk in text_chunks if chunk)


async def _run_agent_query(query: str) -> str:
    """Run the Knowledge Captain agent for one query and return plain text."""
    from agent_framework import AgentSession

    from agents.supervisor import create_knowledge_captain

    agent = create_knowledge_captain()
    async with agent:
        session = AgentSession()
        result = await agent.run(query, session=session)
    return result.text if hasattr(result, "text") else str(result)


async def _graphrag_agent_target(
    messages: list[object],
    stream: bool = False,
    session_state: dict[str, object] | None = None,
    context: object | None = None,
) -> dict[str, list[dict[str, str]]]:
    """OpenAI chat-protocol callback target for red team SDK."""
    del stream, session_state, context

    query = _extract_query_from_messages(messages)
    response_text = await _run_agent_query(query)

    return {
        "messages": [
            {
                "role": "assistant",
                "content": response_text,
            }
        ]
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    """Write JSON payload to disk."""
    with open(path, "w", encoding="utf-8") as file_handle:
        json.dump(payload, file_handle, indent=2, default=str)


def _serialize_redteam_result(result: object) -> dict[str, object]:
    """Convert SDK result object to a JSON-serializable dictionary."""
    if isinstance(result, dict):
        return result

    to_json = getattr(result, "to_json", None)
    if callable(to_json):
        serialized = to_json()
        if isinstance(serialized, dict):
            return serialized

        if isinstance(serialized, str):
            try:
                payload = json.loads(serialized)
                if isinstance(payload, dict):
                    return payload
            except json.JSONDecodeError:
                logger.warning("Red team result JSON parsing failed. Persisting raw payload instead.")

    return {"raw_result": str(result)}


def _extract_total_from_scorecard(scorecard: object) -> int | None:
    """Extract overall_total from scorecard.risk_category_summary if available."""
    if not isinstance(scorecard, dict):
        return None

    risk_summary = scorecard.get("risk_category_summary")
    if not isinstance(risk_summary, list) or not risk_summary:
        return None

    first_entry = risk_summary[0]
    if not isinstance(first_entry, dict):
        return None

    overall_total = first_entry.get("overall_total")
    return overall_total if isinstance(overall_total, int) else None


def _extract_total_from_aoai_summary(aoai_summary: object) -> int | None:
    """Extract result_counts.total from AOAI-compatible summary if available."""
    if not isinstance(aoai_summary, dict):
        return None

    result_counts = aoai_summary.get("result_counts")
    if not isinstance(result_counts, dict):
        return None

    total = result_counts.get("total")
    return total if isinstance(total, int) else None


def _extract_total_evaluated_attacks(result_payload: dict[str, object]) -> int | None:
    """Extract total evaluated attacks from RedTeam payload, if present."""
    total_from_scorecard = _extract_total_from_scorecard(result_payload.get("scorecard"))
    if total_from_scorecard is not None:
        return total_from_scorecard

    return _extract_total_from_aoai_summary(result_payload.get("AOAI_Compatible_Summary"))


def _map_new_foundry_attack_strategies(strategies: list[str] | None) -> list[str]:
    """Map CLI strategy names to New Foundry red-team strategy names."""
    strategy_mapping = {
        "baseline": "Baseline",
        "jailbreak": "IndirectJailbreak",
        "crescendo": "Crescendo",
        "easy": "Base64",
        "moderate": "ROT13",
        "difficult": "UnicodeConfusable",
        "multiturn": "Flip",
    }

    if not strategies:
        return list(NEW_FOUNDRY_DEFAULT_ATTACK_STRATEGIES)

    mapped: list[str] = []
    for strategy in strategies:
        normalized = strategy.strip().lower()
        resolved = strategy_mapping.get(normalized)
        if resolved and resolved not in mapped:
            mapped.append(resolved)

    if not mapped:
        return list(NEW_FOUNDRY_DEFAULT_ATTACK_STRATEGIES)

    return mapped


def _publish_new_foundry_redteam_reference(
    config: EvalConfig,
    strategies: list[str] | None,
    risk_categories: list[str],
) -> dict[str, object]:
    """Publish an additional Step 4 run to New Foundry evals v1 for nextgen visibility.

    The primary scan still uses the Azure AI Evaluation RedTeam SDK (full scorecard output).
    This helper creates an equivalent New Foundry run so the report is navigable from
    New Foundry evaluations UX.
    """
    import httpx
    from azure.identity import DefaultAzureCredential

    if not config.azure_ai_project:
        raise ValueError("AZURE_AI_PROJECT is required to publish New Foundry Step 4 references.")

    base_url = f"{config.azure_ai_project.rstrip('/')}/openai/v1"
    eval_name = f"graphrag-redteam-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}"
    mapped_strategies = _map_new_foundry_attack_strategies(strategies)

    eval_payload = {
        "name": eval_name,
        "data_source_config": {"type": "azure_ai_source", "scenario": "red_team"},
        "testing_criteria": [
            {"type": "azure_ai_evaluator", "name": "violence", "evaluator_name": "builtin.violence"},
            {
                "type": "azure_ai_evaluator",
                "name": "hate_unfairness",
                "evaluator_name": "builtin.hate_unfairness",
            },
            {"type": "azure_ai_evaluator", "name": "sexual", "evaluator_name": "builtin.sexual"},
            {"type": "azure_ai_evaluator", "name": "self_harm", "evaluator_name": "builtin.self_harm"},
        ],
    }

    run_payload = {
        "name": f"{eval_name}-run",
        "data_source": {
            "type": "azure_ai_red_team",
            "item_generation_params": {
                "type": "red_team",
                "attack_strategies": mapped_strategies,
                "risk_categories": risk_categories,
                "num_turns": 2,
            },
            "target": {"type": "azure_ai_model", "model": config.chat_deployment},
        },
    }

    token = DefaultAzureCredential().get_token(AI_SCOPE).token
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=60.0, headers=headers) as client:
        eval_response = client.post(f"{base_url}/evals", json=eval_payload)
        eval_response.raise_for_status()
        eval_id = str(eval_response.json()["id"])

        run_response = client.post(f"{base_url}/evals/{eval_id}/runs", json=run_payload)
        run_response.raise_for_status()
        run_id = str(run_response.json()["id"])

        deadline = time.monotonic() + NEW_FOUNDRY_TIMEOUT_SECONDS
        latest_run: dict[str, Any] = run_response.json()

        while time.monotonic() < deadline:
            status = str(latest_run.get("status", "")).lower()
            if status in {"completed", "failed", "canceled"}:
                break

            time.sleep(NEW_FOUNDRY_POLL_SECONDS)
            poll_response = client.get(f"{base_url}/evals/{eval_id}/runs/{run_id}")
            poll_response.raise_for_status()
            latest_run = poll_response.json()

        error_message = ""
        if isinstance(latest_run.get("error"), dict):
            error_message = str(latest_run["error"].get("message", ""))

        return {
            "eval_id": eval_id,
            "run_id": run_id,
            "status": latest_run.get("status", "unknown"),
            "report_url": latest_run.get("report_url", ""),
            "error": error_message,
            "attack_strategies": mapped_strategies,
            "risk_categories": risk_categories,
        }


async def run_redteam_scan(
    strategies: list[str] | None = None,
    risk_categories: list[str] | None = None,
    output_dir: str | Path = RESULTS_DIR,
    flow: str | None = None,
) -> dict[str, object]:
    """Run red team safety scan against the GraphRAG agent.

    Args:
        strategies: List of attack strategy names (default: Baseline + EASY).
        risk_categories: Risk categories to test (default: all four).
        output_dir: Directory for scan results.
        flow: Red teaming flow. Supported values: ``cloud-model`` (default)
            and ``local-agent``.

    Returns:
        Dict with red team scan results.

    Raises:
        ValueError: If Azure AI Foundry project is not configured.
    """
    from azure.ai.evaluation.red_team import AttackStrategy, RedTeam
    from azure.identity import DefaultAzureCredential

    from evaluation.config import EvalConfig

    config = EvalConfig.from_env()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not config.has_foundry_project:
        raise ValueError(
            "Azure AI Foundry project required for red teaming. Set AZURE_AI_PROJECT environment variable."
        )

    strategy_map = _build_strategy_map(AttackStrategy)
    attack_strategies = _resolve_attack_strategies(strategies, strategy_map, AttackStrategy)
    risk_categories = risk_categories or list(DEFAULT_RISK_CATEGORIES)
    redteam_flow = _normalize_redteam_flow(flow)

    credential = DefaultAzureCredential()

    azure_ai_project = _resolve_azure_ai_project(config)
    target = _resolve_scan_target(config, redteam_flow)

    red_team = RedTeam(
        azure_ai_project=azure_ai_project,
        credential=credential,
    )

    logger.info("Starting red team scan with strategies: %s", [str(s) for s in attack_strategies])
    logger.info("Risk categories: %s", risk_categories)
    logger.info("Step 4 flow: %s", redteam_flow)

    result = await red_team.scan(
        target=target,
        scan_name="graphrag-agent-safety-scan",
        attack_strategies=attack_strategies,
        risk_categories=risk_categories,
    )

    result_payload = _serialize_redteam_result(result)

    total_attacks = _extract_total_evaluated_attacks(result_payload)
    if total_attacks == 0:
        logger.error(ZERO_ATTACKS_ERROR)
        raise RuntimeError(ZERO_ATTACKS_ERROR)

    if redteam_flow == "cloud-model" and config.azure_ai_project:
        try:
            new_foundry = _publish_new_foundry_redteam_reference(
                config=config,
                strategies=strategies,
                risk_categories=risk_categories,
            )
            result_payload["new_foundry"] = new_foundry
            logger.info("New Foundry Step 4 reference report: %s", new_foundry.get("report_url", ""))
        except Exception:
            logger.exception("Failed to publish New Foundry Step 4 reference run.")

    # Save results
    result_path = output_dir / "redteam_results.json"
    await asyncio.to_thread(_write_json, result_path, result_payload)
    logger.info("Red team results saved to %s", result_path)

    return result_payload


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    for name in ("litellm", "httpx", "httpcore", "openai", "azure", "mcp", "agent_framework", "asyncio"):
        logging.getLogger(name).setLevel(logging.ERROR)

    parser = argparse.ArgumentParser(description="Run red team safety scan")
    parser.add_argument(
        "--strategies",
        nargs="+",
        default=None,
        help="Attack strategies: baseline, jailbreak, crescendo, easy, moderate, difficult, multiturn",
    )
    parser.add_argument(
        "--risks",
        nargs="+",
        default=None,
        help="Risk categories: Violence, HateUnfairness, Sexual, SelfHarm",
    )
    parser.add_argument(
        "--flow",
        choices=SUPPORTED_REDTEAM_FLOWS,
        default=DEFAULT_RETEAM_FLOW,
        help="Step 4 execution flow: cloud-model (default) or local-agent",
    )
    args = parser.parse_args()

    result = asyncio.run(run_redteam_scan(strategies=args.strategies, risk_categories=args.risks, flow=args.flow))
    print(f"\nRed team scan complete. Results saved to {RESULTS_DIR / 'redteam_results.json'}")
