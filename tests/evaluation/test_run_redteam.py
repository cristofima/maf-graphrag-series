"""Unit tests for evaluation/scripts/run_redteam.py flow selection helpers."""

import json
from pathlib import Path

import pytest

from evaluation.config import EvalConfig
from evaluation.scripts.run_redteam import (
    _build_cloud_model_target,
    _build_redteam_failure_payload,
    _build_strategy_map,
    _extract_query_from_messages,
    _extract_total_evaluated_attacks,
    _map_new_foundry_attack_strategies,
    _normalize_redteam_flow,
    _resolve_attack_strategies,
    _resolve_scan_target,
    _serialize_redteam_result,
    run_redteam_scan,
)


class TestNormalizeRedteamFlow:
    def test_default_flow_when_not_provided(self, monkeypatch):
        monkeypatch.delenv("REDTEAM_FLOW", raising=False)

        resolved = _normalize_redteam_flow(None)

        assert resolved == "cloud-model"

    def test_reads_flow_from_environment(self, monkeypatch):
        monkeypatch.setenv("REDTEAM_FLOW", "local-agent")

        resolved = _normalize_redteam_flow(None)

        assert resolved == "local-agent"

    def test_cli_flow_overrides_environment(self, monkeypatch):
        monkeypatch.setenv("REDTEAM_FLOW", "local-agent")

        resolved = _normalize_redteam_flow("cloud-model")

        assert resolved == "cloud-model"

    def test_raises_on_invalid_flow(self, monkeypatch):
        monkeypatch.delenv("REDTEAM_FLOW", raising=False)

        with pytest.raises(ValueError, match="Unsupported red team flow"):
            _normalize_redteam_flow("invalid-flow")


class TestResolveScanTarget:
    @staticmethod
    def _make_config() -> EvalConfig:
        return EvalConfig(
            azure_endpoint="https://example.openai.azure.com/",
            api_key="test-key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o",
            redteam_chat_deployment="gpt-4o-redteam",
            api_version="2024-08-01-preview",
        )

    def test_build_cloud_model_target(self):
        config = self._make_config()

        target = _build_cloud_model_target(config)

        assert target == {
            "azure_endpoint": "https://example.openai.azure.com/",
            "api_key": "test-key",
            "azure_deployment": "gpt-4o-redteam",
            "api_version": "2024-08-01-preview",
        }

    def test_resolve_scan_target_cloud_model(self):
        config = self._make_config()

        target = _resolve_scan_target(config, "cloud-model")

        assert isinstance(target, dict)
        assert target["azure_deployment"] == "gpt-4o-redteam"

    def test_resolve_scan_target_local_agent(self):
        config = self._make_config()

        target = _resolve_scan_target(config, "local-agent")

        assert callable(target)
        assert target.__name__ == "_graphrag_agent_target"

    def test_build_failure_payload_for_invalid_secret(self):
        config = self._make_config()

        payload = _build_redteam_failure_payload(
            error=RuntimeError("AADSTS7000215: Invalid client secret provided."),
            flow="cloud-model",
            config=config,
            risk_categories=["Violence"],
            strategies=["AttackStrategy.Baseline"],
        )

        assert payload["status"] == "failed"
        assert payload["target_deployment"] == "gpt-4o-redteam"
        assert payload["eval_deployment"] == "gpt-4o"
        assert any("AZURE_CLIENT_SECRET" in item for item in payload["remediation"])


class _FakeAttackStrategy:
    Baseline = "Baseline"
    Jailbreak = "Jailbreak"
    Crescendo = "Crescendo"
    EASY = "EASY"
    MODERATE = "MODERATE"
    DIFFICULT = "DIFFICULT"
    MultiTurn = "MultiTurn"


class _SerializableResult:
    def __init__(self, payload: dict[str, object] | str) -> None:
        self._payload = payload

    def to_json(self):
        return self._payload


class TestRedteamHelpers:
    def test_strategy_map_and_resolution(self) -> None:
        strategy_map = _build_strategy_map(_FakeAttackStrategy)

        assert strategy_map["baseline"] == "Baseline"
        assert strategy_map["multiturn"] == "MultiTurn"

        resolved = _resolve_attack_strategies(["baseline", "easy", "unknown"], strategy_map, _FakeAttackStrategy)
        assert resolved == ["Baseline", "EASY"]

        default_resolved = _resolve_attack_strategies(None, strategy_map, _FakeAttackStrategy)
        assert default_resolved == ["Baseline", "EASY"]

    def test_extract_query_from_messages(self) -> None:
        assert _extract_query_from_messages([]) == ""

        messages: list[object] = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "hello"},
                    {"type": "input_text", "text": "world"},
                ],
            }
        ]
        assert _extract_query_from_messages(messages) == "hello\nworld"

    def test_serialize_redteam_result_variants(self) -> None:
        as_dict = {"status": "completed"}
        assert _serialize_redteam_result(as_dict) == as_dict

        from_json_dict = _SerializableResult({"ok": True})
        assert _serialize_redteam_result(from_json_dict) == {"ok": True}

        from_json_string = _SerializableResult(json.dumps({"from": "string"}))
        assert _serialize_redteam_result(from_json_string) == {"from": "string"}

        from_invalid_json = _SerializableResult("not-json")
        assert "raw_result" in _serialize_redteam_result(from_invalid_json)

    def test_extract_total_evaluated_attacks(self) -> None:
        payload_with_scorecard = {
            "scorecard": {
                "risk_category_summary": [
                    {"overall_total": 7},
                ]
            }
        }
        assert _extract_total_evaluated_attacks(payload_with_scorecard) == 7

        payload_with_aoai = {
            "AOAI_Compatible_Summary": {
                "result_counts": {
                    "total": 3,
                }
            }
        }
        assert _extract_total_evaluated_attacks(payload_with_aoai) == 3

    def test_map_new_foundry_attack_strategies(self) -> None:
        assert _map_new_foundry_attack_strategies(None) == ["Base64", "Flip"]
        assert _map_new_foundry_attack_strategies(["baseline", "easy", "baseline"]) == ["Baseline", "Base64"]
        assert _map_new_foundry_attack_strategies(["unknown"]) == ["Base64", "Flip"]


class _ScanResult:
    def to_json(self) -> dict[str, object]:
        return {
            "scorecard": {
                "risk_category_summary": [{"overall_total": 2}],
            }
        }


class _RedTeamSuccess:
    def __init__(self, *, azure_ai_project, credential) -> None:
        self.azure_ai_project = azure_ai_project
        self.credential = credential

    async def scan(self, **kwargs):
        return _ScanResult()


class _RedTeamFailure:
    def __init__(self, *, azure_ai_project, credential) -> None:
        self.azure_ai_project = azure_ai_project
        self.credential = credential

    async def scan(self, **kwargs):
        raise RuntimeError("boom")


@pytest.mark.asyncio
class TestRunRedteamScan:
    @staticmethod
    def _make_config(has_project: bool = True) -> EvalConfig:
        return EvalConfig(
            azure_endpoint="https://example.openai.azure.com/",
            api_key="test-key",
            chat_deployment="gpt-4o",
            eval_chat_deployment="gpt-4o-eval",
            redteam_chat_deployment="gpt-4o-redteam",
            api_version="2024-08-01-preview",
            azure_ai_project=("https://example.services.ai.azure.com/api/projects/demo" if has_project else None),
        )

    async def test_raises_when_foundry_project_is_missing(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("evaluation.config.EvalConfig.from_env", lambda: self._make_config(has_project=False))

        with pytest.raises(ValueError, match="Foundry project required"):
            await run_redteam_scan(output_dir=tmp_path)

    async def test_writes_failure_payload_on_scan_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        monkeypatch.setattr("evaluation.config.EvalConfig.from_env", lambda: self._make_config())
        monkeypatch.setattr("azure.ai.evaluation.red_team.RedTeam", _RedTeamFailure, raising=False)
        monkeypatch.setattr("azure.ai.evaluation.red_team.AttackStrategy", _FakeAttackStrategy, raising=False)
        monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: object(), raising=False)

        with pytest.raises(RuntimeError, match="boom"):
            await run_redteam_scan(output_dir=tmp_path, flow="cloud-model")

        payload = json.loads((tmp_path / "redteam_results.json").read_text(encoding="utf-8"))
        assert payload["status"] == "failed"
        assert payload["flow"] == "cloud-model"

    async def test_returns_completed_payload_for_successful_scan(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        monkeypatch.setattr("evaluation.config.EvalConfig.from_env", lambda: self._make_config())
        monkeypatch.setattr("azure.ai.evaluation.red_team.RedTeam", _RedTeamSuccess, raising=False)
        monkeypatch.setattr("azure.ai.evaluation.red_team.AttackStrategy", _FakeAttackStrategy, raising=False)
        monkeypatch.setattr("azure.identity.DefaultAzureCredential", lambda: object(), raising=False)
        monkeypatch.setattr(
            "evaluation.scripts.run_redteam._publish_new_foundry_redteam_reference",
            lambda **_: {
                "run_id": "run_1",
                "status": "completed",
                "report_url": "https://ai.azure.com/report",
            },
        )

        result = await run_redteam_scan(output_dir=tmp_path, flow="cloud-model")

        assert result["status"] == "completed"
        assert result["flow"] == "cloud-model"
        assert result["new_foundry"]["status"] == "completed"
        assert (tmp_path / "redteam_results.json").exists()
