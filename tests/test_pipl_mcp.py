"""Tests for the PIPL MCP server — runs without a live MCP transport.

Validates:
- All 4 MCP tools return valid JSON
- classify_obligations() correctly maps characteristics to articles
- audit_content_pipeline() catches PI fields, cross-border flows, weak consent
- sign_attestation() returns a graceful fallback without MEOK_API_KEY
- crosswalk_pipl_to_gdpr() returns the 10 expected rows

Run:  cd pipl-mcp && pytest tests/test_pipl_mcp.py -v
"""

from __future__ import annotations

import json
import sys
import os
import importlib.util
from pathlib import Path

# Import the server module directly (avoids needing the mcp package at test time)
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))


def load_server_module():
    spec = importlib.util.spec_from_file_location(
        "meok_pipl_mcp", HERE / "meok_pipl_mcp" / "server.py"
    )
    mod = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(mod)
    except ImportError as e:
        # mcp not installed — skip the test gracefully
        pytest.skip(f"mcp not installed: {e}")
    return mod


import pytest  # noqa: E402

mod = load_server_module()


def _call(tool_name: str, **kwargs):
    """Call a tool function and return parsed JSON."""
    tool_obj = getattr(mod.mcp._tool_manager, "_tools", {}).get(tool_name)
    if tool_obj is None:
        # Fallback: the mcp library exposes tools differently across versions
        for attr in dir(mod):
            obj = getattr(mod, attr)
            if callable(obj) and getattr(obj, "__name__", "") == tool_name:
                tool_obj = obj
                break
    if tool_obj is None:
        pytest.skip(f"tool {tool_name} not found in this mcp version")
    # mcp 1.x wraps functions in a Tool object; .fn is the callable
    tool_fn = getattr(tool_obj, "fn", tool_obj)
    if not callable(tool_fn):
        pytest.skip(f"tool {tool_name} is not callable in this mcp version")
    result = tool_fn(**kwargs)
    return json.loads(result) if isinstance(result, str) else result


# ---------- 1. pipi_overview ------------------------------------------------

def test_pipi_overview_returns_4_articles_and_meta():
    out = _call("pipi_overview")
    assert out["law"]["short_name"] == "PIPL"
    assert out["law"]["effective_date"] == "2021-11-01"
    assert len(out["articles_covered"]) == 4
    assert "art_13_consent" in out["articles_covered"]
    assert "art_38_cross_border_transfer" in out["articles_covered"]
    assert "GDPR" in out["crosswalk_to_other_regimes"]


# ---------- 2. classify_obligations -----------------------------------------

def test_classify_handles_chinese_pi_triggers_consent():
    out = _call(
        "classify_pipl_obligations",
        handles_chinese_pi=True,
    )
    assert out["in_scope"] is True
    assert "art_13_consent" in out["triggered_obligations"]


def test_classify_cross_border_triggers_art_38():
    out = _call(
        "classify_pipl_obligations",
        handles_chinese_pi=True,
        cross_border_transfers_pi=True,
    )
    assert "art_13_consent" in out["triggered_obligations"]
    assert "art_38_cross-border-transfer" in out["triggered_obligations"]


def test_classify_high_volume_triggers_cac_assessment_and_dpo():
    out = _call(
        "classify_pipl_obligations",
        handles_chinese_pi=True,
        pi_volume_above_1m_individuals=True,
    )
    assert out["cac_security_assessment_required"] is True
    assert out["annual_security_assessment_required"] is True
    assert out["designated_dpo_required"] is True


def test_classify_sensitive_pi_requires_separate_consent():
    out = _call(
        "classify_pipl_obligations",
        handles_chinese_pi=True,
        processes_sensitive_pi=True,
    )
    assert out["separate_consent_required"] is True


def test_classify_minors_under_14_requires_guardian_consent():
    out = _call(
        "classify_pipl_obligations",
        handles_chinese_pi=True,
        handles_minor_data_under_14=True,
    )
    assert out["minor_guardian_consent_required"] is True
    assert out["separate_consent_required"] is True


def test_classify_out_of_scope():
    out = _call("classify_pipl_obligations")
    assert out["in_scope"] is False
    assert "No PIPL obligations triggered" in out["next_step"]


# ---------- 3. audit_content_pipeline ---------------------------------------

def test_audit_detects_id_card_in_sample_text():
    out = _call(
        "audit_content_pipeline",
        tenant_id="t1",
        sample_text="user 110101199003078812 registered",
    )
    assert out["audit_severity"] == "high"
    assert any("id_card" in str(f).lower() or "likely pi" in str(f).lower() for f in out["findings"])


def test_audit_detects_cross_border_flow():
    out = _call(
        "audit_content_pipeline",
        tenant_id="t1",
        data_flow_csv="users_cn→us-db, audit_logs→cn-logging",
    )
    assert out["audit_severity"] == "high"
    cross_border_finding = [f for f in out["findings"] if "cross-border" in f.get("issue", "").lower()]
    assert len(cross_border_finding) == 1
    assert "us-db" in cross_border_finding[0]["issue"]


def test_audit_flags_weak_consent_receipt():
    out = _call(
        "audit_content_pipeline",
        tenant_id="t1",
        consent_receipt_sample="We collect your data for our service.",
    )
    # Weak receipt → medium severity
    assert out["audit_severity"] in ("medium", "high")
    consent_finding = [f for f in out["findings"] if "consent" in f.get("issue", "").lower() and "missing" in f.get("issue", "").lower()]
    assert len(consent_finding) == 1
    issue = consent_finding[0]["issue"].lower()
    assert "withdraw" in issue or "purpose" in issue or "retention" in issue


def test_audit_passes_strong_consent_receipt():
    out = _call(
        "audit_content_pipeline",
        tenant_id="t1",
        consent_receipt_sample=(
            "目的: 账户安全分析。保存期限: 90天。联系方式: dpo@example.com。"
            "您可以随时撤回同意 (withdraw consent at any time)。"
        ),
    )
    info_findings = [f for f in out["findings"] if f.get("severity") == "info"]
    assert any("Art 17" in f.get("issue", "") for f in info_findings)


# ---------- 4. sign_attestation (graceful fallback) -----------------------

def test_sign_attestation_without_api_key_returns_friendly_error(monkeypatch):
    monkeypatch.delenv("MEOK_API_KEY", raising=False)
    out = _call(
        "sign_pipl_attestation",
        entity_name="Demo Co",
        audited_articles_csv="art_13_consent,art_38_cross-border-transfer",
        compliance_score=0.85,
    )
    assert "MEOK_API_KEY" in out.get("error", "")


# ---------- 5. crosswalk_pipl_to_gdpr --------------------------------------

def test_crosswalk_returns_10_rows():
    out = _call("crosswalk_pipl_to_gdpr")
    assert out["law_left"] == "PIPL"
    assert out["law_right"] == "GDPR"
    assert len(out["rows"]) == 10
    # Sensitive data row
    sensitive = [r for r in out["rows"] if r["topic"] == "Sensitive data"][0]
    assert "Art 28" in sensitive["pipl"]
    assert "Art 9" in sensitive["gdpr"]
    # Children row
    children = [r for r in out["rows"] if r["topic"] == "Children"][0]
    assert "14" in children["pipl"]
    assert "16" in children["gdpr"] or "under-16" in children["gdpr"].lower()
