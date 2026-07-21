# Part 5 Implementation Notes — Monitoring, Evaluation & Safety

## What Was Built

Part 5 adds the three-pillar evaluation framework from the MAF Azure Samples pattern:

```
src/evaluation/
├── __init__.py
├── config.py                     # EvalConfig — loads from env, model_config property
├── monitoring/
│   └── otel_setup.py             # setup_monitoring() via agent_framework.observability
├── evaluators/
│   ├── builtin.py                # Quality evaluator wrappers + message conversion
│   ├── entity_accuracy.py        # Custom: entities exist in knowledge graph?
│   └── relationship_validity.py  # Custom: relationships valid in knowledge graph?
├── datasets/
│   └── golden_questions.jsonl    # 10 test cases for TechVenture knowledge base
└── scripts/
    ├── generate_eval_data.py     # Run agent on golden questions → eval_data.jsonl
    ├── run_batch_evaluation.py   # Batch evaluate with built-in + custom evaluators
    └── run_redteam.py            # Red team safety scan (requires Azure AI Foundry)
```

## Pillar A — Monitoring (OpenTelemetry)

`setup_monitoring()` in `evaluation/monitoring/otel_setup.py` wraps MAF's built-in telemetry:

```python
from agent_framework.observability import configure_otel_providers

# Correct module: agent_framework.observability (NOT agent_framework.telemetry)
# configure_otel_providers() takes NO parameters — all config via env vars
```

**Environment variables:**

- `OTEL_EXPORTER_OTLP_ENDPOINT` — Aspire Dashboard (local dev, default `http://localhost:4317`)
- `APPLICATIONINSIGHTS_CONNECTION_STRING` — Application Insights (production)

**`setup_monitoring()` modes:**

- `use_aspire=True` (default) + no App Insights → sets `OTEL_EXPORTER_OTLP_ENDPOINT` then calls `configure_otel_providers()`
- `use_aspire=False` + App Insights configured → calls `configure_otel_providers()` only (picks up App Insights from env)

MAF agents emit `gen_ai.*` spans automatically for LLM calls, tool invocations, and agent steps. No manual instrumentation needed.

## Pillar B — Quality Evaluation

### Confirmed Quality Evaluators (Azure OpenAI only, no Foundry needed)

| Evaluator                       | Constructor        | Purpose                                   |
| ------------------------------- | ------------------ | ----------------------------------------- |
| `TaskAdherenceEvaluator`        | `model_config=...` | Did agent follow instructions?            |
| `IntentResolutionEvaluator`     | `model_config=...` | Did agent resolve user intent?            |
| `RelevanceEvaluator`            | `model_config=...` | Is the response relevant to the query?    |
| `CoherenceEvaluator`            | `model_config=...` | Is the response logically consistent?     |
| `ResponseCompletenessEvaluator` | `model_config=...` | Does the response cover expected content? |

### Tool behavior evaluator (conditional)

| Evaluator                   | Constructor        | Purpose                      |
| --------------------------- | ------------------ | ---------------------------- |
| `ToolCallAccuracyEvaluator` | `model_config=...` | Right tool + correct params? |

`model_config` dict format:

```python
model_config = {
    "azure_endpoint": "https://<resource>.openai.azure.com/",
    "api_key": "<key>",
    "azure_deployment": "gpt-4o",
}
```

### evaluator_config Column Mapping Gotcha

The `evaluate()` batch function requires column mappings **nested under `"column_mapping"`**:

```python
# Correct ✅
evaluator_config = {
    "task_adherence": {"column_mapping": {"query": "${data.query}", "response": "${data.response}"}},
}

# Wrong ❌ (flattens mapping directly — results in missing column errors)
evaluator_config = {
    "task_adherence": {"query": "${data.query}", "response": "${data.response}"},
}
```

### Custom GraphRAG Evaluators

**`EntityAccuracyEvaluator`** — validates entities mentioned in response exist in the knowledge graph:

- Loads entities from configured path (`ENTITIES_PARQUET_PATH`, default `output/create_final_entities.parquet`) with fallback to `output/entities.parquet`
- Extracts capitalized multi-word phrases + single proper nouns from response text
- Returns `entity_accuracy` score 0–1, `valid_entities`, `invalid_entities`
- Pass threshold: `>= 0.5`

**`RelationshipValidityEvaluator`** — validates entity pairs co-occurring in response have actual relationships:

- Loads relationships from configured path (`RELATIONSHIPS_PARQUET_PATH`, default `output/create_final_relationships.parquet`) with fallback to `output/relationships.parquet`
- Bidirectional: A→B and B→A both valid
- Returns `relationship_validity` score 0–1, `valid_relationships`, `invalid_relationships`
- Pass threshold: `>= 0.5`

### Foundry Quality Snapshot (March 2026)

Most recent Step 3 quality run (10 rows):

| Metric                | Score  | Rows  |
| --------------------- | ------ | ----- |
| Task adherence        | 80%    | 8/10  |
| Intent resolution     | 100%   | 10/10 |
| Relevance             | 100%   | 10/10 |
| Coherence             | 100%   | 10/10 |
| Response completeness | 100%   | 10/10 |
| Prompt tokens         | 85,686 | -     |
| Completion tokens     | 5,048  | -     |

Operational note:

- `ToolCallAccuracyEvaluator` is conditional and appears only when `eval_data.jsonl` contains structured `tool_call` entries.

### MAF → Evaluator Message Conversion

MAF uses `function_call`/`function_result` internally, but `azure-ai-evaluation` expects OpenAI-style `tool_call`/`tool_result`:

```python
from evaluation.evaluators.builtin import convert_to_evaluator_messages

# After agent.invoke():
messages = convert_to_evaluator_messages(thread.messages)
# → [{role: "user", ...}, {role: "assistant", content: [{type: "tool_call", ...}]}, ...]
```

### Three-Script Pattern

```
golden_questions.jsonl  →  generate_eval_data.py  →  eval_data.jsonl
                                                            ↓
                                              run_batch_evaluation.py
                                                            ↓
                                              evaluation_results.json + report.md
```

Run commands:

```powershell
# Step 1: Generate (requires running MCP server)
uv run python -m evaluation.scripts.generate_eval_data

# Step 2: Evaluate (requires Azure OpenAI, NOT Foundry)
uv run python -m evaluation.scripts.run_batch_evaluation

# Step 2a: Optional - skip custom graph evaluators
uv run python -m evaluation.scripts.run_batch_evaluation --no-custom

# Step 2b: Optional — log to Foundry dashboard
uv run python -m evaluation.scripts.run_batch_evaluation --foundry

# Step 3: Red team (requires Azure AI Foundry)
uv run python -m evaluation.scripts.run_redteam --flow cloud-model --strategies baseline jailbreak
```

## Pillar C — Safety (Red Teaming)

**Requires Azure AI Foundry project.** Set `AZURE_AI_PROJECT` to a Foundry project endpoint URL:

```
AZURE_AI_PROJECT=https://<account>.services.ai.azure.com/api/projects/<project>
```

**Important API note:** Part 5 now uses **New Foundry URL mode only** for Step 4.
`run_redteam.py` requires `AZURE_AI_PROJECT` and no longer uses old scope-dict fallback.

`run_redteam.py` now supports two execution flows:

- `cloud-model` (default): RedTeam scans the Azure OpenAI model deployment target.
- `local-agent`: RedTeam scans the local agent callback target (`_graphrag_agent_target`).

For migration to New Foundry with minimal operational drift, use `cloud-model` as default.

```python
# New Foundry URL shape ✅
RedTeam(azure_ai_project=os.environ["AZURE_AI_PROJECT"], ...)
```

**Attack strategies:** `AttackStrategy.Baseline`, `.Jailbreak`, `.Crescendo`, `.EASY`, `.MODERATE`, `.DIFFICULT`, `.MultiTurn`.

## Infrastructure

`infra/main.tf` now provisions:

- **`azurerm_log_analytics_workspace`** — backing store for Application Insights
- **`azurerm_application_insights`** — production telemetry collection
- **`azurerm_ai_services`** + `azurerm_cognitive_account_project` — New Foundry-compatible project endpoint

Foundry project creation is controlled by `enable_foundry` (default: `true`).
Application Insights output is included in `env_file_content`.

New outputs: `application_insights_connection_string`, `application_insights_instrumentation_key`.
New Foundry output: `azure_ai_project_endpoint`.

The `env_file_content` output includes:

- `APPLICATIONINSIGHTS_CONNECTION_STRING`
- `AZURE_AI_PROJECT` (when `enable_foundry = true`)

## New Dependencies

```toml
azure-ai-evaluation = { version = ">=1.18.1", extras = ["redteam"] }
opentelemetry-api = "~1.43.0"
opentelemetry-sdk = "~1.43.0"
azure-monitor-opentelemetry-exporter = "~1.0.0b55"
```

Install: `uv sync --dev`

## EvalConfig

`EvalConfig.from_env()` loads all evaluation configuration:

| Env Var                                 | Required                              | Purpose                                     |
| --------------------------------------- | ------------------------------------- | ------------------------------------------- |
| `AZURE_OPENAI_ENDPOINT`                 | Yes                                   | LLM-as-judge endpoint                       |
| `AZURE_OPENAI_API_KEY`                  | Yes                                   | LLM-as-judge key                            |
| `AZURE_OPENAI_CHAT_DEPLOYMENT`          | No (default: `gpt-4o`)                | Evaluator model                             |
| `AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT`     | No                                    | Optional evaluator-only deployment override |
| `AZURE_OPENAI_EVAL_API_VERSION`         | No (default: `2025-04-01-preview`)    | Evaluator-only Azure OpenAI API version     |
| `AZURE_AI_PROJECT`                      | No                                    | Foundry project URL (red team + dashboard)  |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | No                                    | Production monitoring                       |
| `OTEL_TRACING_ENDPOINT`                 | No (default: `http://localhost:4317`) | Aspire OTLP endpoint                        |
| `ENTITIES_PARQUET_PATH`                 | No                                    | Custom entities Parquet path                |
| `RELATIONSHIPS_PARQUET_PATH`            | No                                    | Custom relationships Parquet path           |

Configuration note:

- Keep `AZURE_OPENAI_API_VERSION` and `AZURE_OPENAI_EVAL_API_VERSION` separate.
- `AZURE_OPENAI_API_VERSION` is used by the agent/workflow runtime.
- `AZURE_OPENAI_EVAL_API_VERSION` is used by Azure AI Evaluation built-in evaluators.
- Reusing `2024-11-20` for evaluators can return `404 Resource not found` in this project setup; `2025-04-01-preview` is the validated evaluator value.

## Real-World Challenges Observed (Part 5)

These were the most relevant issues seen during implementation and validation of Part 5:

1. **Evaluator/model parameter mismatch (`max_tokens` vs `max_completion_tokens`)**
   - `IntentResolutionEvaluator` can fail on deployments that reject `max_tokens`.
   - Mitigation: Step 3 probes compatibility and conditionally skips `IntentResolutionEvaluator` when incompatible, while continuing with remaining evaluators.
   - Optional override: `AZURE_OPENAI_EVAL_CHAT_DEPLOYMENT` for an evaluator-specific deployment.

2. **`evaluator_config` mapping shape errors**
   - Batch runs fail or mis-bind data when mappings are not nested under `column_mapping`.
   - Mitigation: standardized all evaluator mappings to:
     `{"<name>": {"column_mapping": {...}}}`.

3. **Legacy Foundry fallback ambiguity**
   - Mixed old/new Foundry behavior made Step 4 troubleshooting harder.
   - Mitigation: URL-only New Foundry contract for Step 4 (`AZURE_AI_PROJECT` required), with old fallback behavior removed.

4. **Remote publish fragility after local evaluation success**
   - Step 3 can complete local scoring and still fail on remote publish due to network/DNS/endpoint issues.
   - Mitigation: local artifact persistence remains the primary success path; New Foundry publish is treated as a secondary integration step.

5. **Red team `0/0` false-success in unsupported regions**
   - Step 4 may complete without evaluated attacks, yielding no meaningful safety signal.
   - Mitigation: explicit fail-fast when total evaluated attacks is zero, with guidance to move the project to a supported region.

For the expanded write-up, see `docs/lessons-learned.md` (Challenges 17-21).

## Tests

Part 5 test suite currently has **64 tests** in `tests/evaluation/`:

| File                         | Tests | Coverage                                                  |
| ---------------------------- | ----- | --------------------------------------------------------- |
| `test_config.py`             | 16    | `EvalConfig.from_env()`, properties, validation           |
| `test_builtin_evaluators.py` | 21    | Tool definitions, message conversion, extraction helpers  |
| `test_custom_evaluators.py`  | 14    | Entity accuracy, relationship validity, entity extraction |
| `test_monitoring.py`         | 6     | OTel setup modes, env var setting                         |
| `test_run_redteam.py`        | 7     | New Foundry flow helpers and target resolution            |

No Azure credentials needed for tests — all use mocks and temporary Parquet fixtures.


