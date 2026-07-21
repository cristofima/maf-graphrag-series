"""
Generate evaluation data by running the agent on golden questions.

Runs the Knowledge Captain agent on each test case in golden_questions.jsonl,
converts the conversation to evaluator format, and writes results to
eval_data.jsonl for batch evaluation.

Usage:
    uv run python -m evaluation.scripts.generate_eval_data
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)

# Paths
DATASETS_DIR = Path(__file__).resolve().parent.parent / "datasets"
GOLDEN_QUESTIONS_PATH = DATASETS_DIR / "golden_questions.jsonl"
EVAL_DATA_PATH = DATASETS_DIR / "eval_data.jsonl"


async def generate_eval_data(
    input_path: str | Path = GOLDEN_QUESTIONS_PATH,
    output_path: str | Path = EVAL_DATA_PATH,
) -> int:
    """Run agent on golden questions and write evaluation data.

    Args:
        input_path: Path to golden_questions.jsonl.
        output_path: Path to write eval_data.jsonl.

    Returns:
        Number of test cases processed.
    """
    from agent_framework import AgentSession

    from agents.supervisor import create_knowledge_captain
    from evaluation.evaluators.builtin import GRAPHRAG_TOOL_DEFINITIONS, convert_to_evaluator_messages

    input_path = Path(input_path)
    output_path = Path(output_path)

    if not input_path.exists():
        raise FileNotFoundError(f"Golden questions file not found: {input_path}")

    # Load test cases using a thread so the async event loop is not blocked
    def _read_jsonl(path: Path) -> list[dict]:
        with open(path, encoding="utf-8") as fh:
            return [json.loads(line.strip()) for line in fh if line.strip()]

    test_cases: list[dict] = await asyncio.to_thread(_read_jsonl, input_path)
    logger.info("Loaded %d test cases from %s", len(test_cases), input_path)

    # Run agent on each test case; collect records in memory, then flush once
    records: list[str] = []
    agent = create_knowledge_captain()
    async with agent:
        for i, case in enumerate(test_cases, 1):
                query = case["query"]
                logger.info("[%d/%d] Processing: %s", i, len(test_cases), query)

                session = AgentSession()
                result = await agent.run(query, session=session)

                session_msgs = list(session.state.get("messages", []))
                response_msgs = list(result.messages) if result.messages else []
                all_msgs = session_msgs + [m for m in response_msgs if m not in session_msgs]

                messages = convert_to_evaluator_messages(all_msgs)

                eval_record = {
                    "query": query,
                    "response": messages,
                    "ground_truth": case.get("ground_truth", ""),
                    "tool_definitions": GRAPHRAG_TOOL_DEFINITIONS,
                }

                records.append(json.dumps(eval_record, ensure_ascii=False) + "\n")

    processed = len(records)

    def _write_jsonl(path: Path, lines: list[str]) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            fh.writelines(lines)

    await asyncio.to_thread(_write_jsonl, output_path, records)

    logger.info("Wrote %d evaluation records to %s", processed, output_path)
    return processed


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    # Suppress noisy loggers
    for name in ("litellm", "httpx", "httpcore", "openai", "azure", "mcp", "agent_framework", "asyncio"):
        logging.getLogger(name).setLevel(logging.ERROR)

    count = asyncio.run(generate_eval_data())
    print(f"\nGenerated {count} evaluation records in {EVAL_DATA_PATH}")
