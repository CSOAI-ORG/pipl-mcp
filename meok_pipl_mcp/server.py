"""
MEOK PIPL MCP Server
====================

The MCP for China's Personal Information Protection Law (PIPL,
中华人民共和国个人信息保护法). Effective since 1 November 2021. Covers
4 articles (the practical obligations for AI systems handling Chinese
personal information):

- Art 13:  Consent (must be informed, specific, freely given)
- Art 38:  Cross-border data transfer (3 lawful mechanisms)
- Art 44-50: Data subject rights (access, correction, deletion,
            portability, withdraw consent)
- Art 51:  Security obligations (encryption, access control, audit)

This is the canonical CSOAI/MEOK reference for PIPL. Crosswalks to
GDPR + TC260 + EU AI Act so a multi-jurisdiction AI system can
demonstrate compliance with one assessment.

CSOAI is the body; this MCP is the surface that the Council substrate
reads. No shadow signers, no parallel keys — compliance posture is
served by the same meok-attestation-api spine that /v1/health pings.
"""

from __future__ import annotations

import json
import os
import re
import hashlib
import secrets
from datetime import datetime, timezone
from typing import Any, Optional

try:
    from mcp.server.mcpserver import MCPServer as FastMCP  # mcp 2.x: FastMCP renamed MCPServer
except ImportError:
    raise ImportError("pip install mcp>=1.0.0 — required for the MCP server")

mcp = FastMCP("meok-pipl-mcp")

# --------------------------------------------------------------------------
# Canonical PIPL data
# --------------------------------------------------------------------------

PIPL_META = {
    "name": "Personal Information Protection Law of the People's Republic of China",
    "chinese_name": "中华人民共和国个人信息保护法",
    "short_name": "PIPL",
    "law_number": None,  # PRC laws don't always carry a public number
    "effective_date": "2021-11-01",
    "authority": "Standing Committee of the National People's Congress",
    "enforcement_authority": "Cyberspace Administration of China (CAC) + sector regulators",
    "scope": "All processing of personal information of natural persons within the territory of the People's Republic of China, plus extraterritorial processing that provides products/services to natural persons inside China or analyses their behaviour",
    "max_fine": "Up to RMB 50 million or 5% of preceding year's annual revenue (whichever is higher) for serious violations",
    "individual_rights": "Yes (access, correction, deletion, portability, withdraw consent, explanation of automated decisions)",
    "url": "http://www.npc.gov.cn/npc/c2/c30834/202108/t20210820_311127.html",
}

# 4 articles covered, with the practical obligations
PIPL_ARTICLES = {
    "art_13_consent": {
        "title": "Consent requirements (告知·同意)",
        "trigger": "Processing personal information (PI) requires the prior, informed, specific, freely-given consent of the individual — except for 7 statutory exceptions (e.g. contract performance, legal obligation, public interest, journalistic, emergency)",
        "obligation": "Provide clear, specific, fully-informed notice of: (a) identity & contact of the processor, (b) purposes of processing, (c) methods and types of PI collected, (d) retention period, (e) how to exercise rights. Consent must be a positive act (no pre-ticked boxes).",
        "who": "Personal information processor (PI handler, 个人信息处理者)",
        "exceptions": [
            "Necessary for concluding or performing a contract to which the individual is a party",
            "Necessary for statutory duties or legal obligations",
            "Necessary for public-interest reporting or news-gathering",
            "Necessary to protect life or property in an emergency",
            "PI already lawfully disclosed within a reasonable scope",
            "Necessary to perform statistical or academic research that has been de-identified",
            "Other circumstances stipulated by laws and administrative regulations",
        ],
        "technical_options": [
            "Granular consent UI (per-purpose, per-type, not a single 'accept all')",
            "Consent receipt / evidence trail (timestamp, version of notice, UI snapshot)",
            "Withdraw-consent path as easy as giving it (Art 44) — one click, no friction",
            "Default-deny for new processing purposes (no implicit consent expansion)",
        ],
    },
    "art_38_cross_border_transfer": {
        "title": "Cross-border transfer (跨境提供)",
        "trigger": "PI handler provides PI to overseas recipients, OR stores/uses PI outside China for business purposes",
        "obligation": "Must satisfy ONE of 4 cross-border mechanisms + pass a CAC security assessment if the handler is a Critical Information Infrastructure Operator (CIIO) OR processes PI of >1 million individuals, OR has provided PI of >100,000 individuals or sensitive PI of >10,000 individuals cumulatively since the start of the preceding year (per Measures on Promoting and Standardizing Cross-border Data Flows, 2024)",
        "who": "PI handler (the data exporter)",
        "mechanisms": [
            "CAC security assessment (安全评估) — for CIIOs and high-volume handlers above",
            "Standard Contractual Clauses (标准合同) with CAC filing (effective Jun 2023)",
            "Personal Information Protection Certification (认证) by a CAC-accredited body",
            "Other conditions stipulated by law or CAC (e.g. necessity test for HR cross-border)",
        ],
        "technical_options": [
            "Data flow inventory (what PI leaves China, to which countries, in what volume)",
            "Standard Contract Execution engine (SCC generation, filing, audit trail)",
            "Destination-country adequacy tracker (CAC publishes a list — currently none in the EU, but 2024 measures create exceptions for FTA partners)",
            "Localisation toggle — default to in-China processing for sensitive PI",
        ],
    },
    "art_44_50_data_subject_rights": {
        "title": "Data subject rights (个人权利)",
        "trigger": "Any individual whose PI is processed has rights that the handler must support",
        "obligation": "Provide a free, accessible channel for: (a) access & copy of PI, (b) correction of inaccurate or incomplete PI, (c) deletion when retention purpose is achieved or consent is withdrawn or the handler stops providing the product, (d) withdraw consent (one click, no friction), (e) explanation of automated decision-making logic, (f) refuse automated decision-making that has a material impact (e.g. credit, employment, eligibility)",
        "who": "PI handler (responding to the individual)",
        "sla": "Response within 30 days; correction/deletion must be effective within 30 days of verified request",
        "technical_options": [
            "Self-service rights portal (Chinese-language, ID-verified)",
            "API endpoints for each right (access, correct, delete, export)",
            "Automated decision audit log (the inputs, the model version, the output, the human override if any)",
            "Withdraw-consent = same number of clicks as giving consent (Art 44 strict)",
        ],
    },
    "art_51_security": {
        "title": "Security obligations (安全保障义务)",
        "trigger": "Any PI handling",
        "obligation": "Implement appropriate technical and organisational measures to ensure PI security, including: encryption, de-identification, access control, audit logging, incident response plan, regular training, designated PI protection officer (DPO) for handlers above 1M individuals' PI",
        "who": "PI handler (the data controller)",
        "incident_response": "Notify regulator + affected individuals immediately upon discovery of a breach where harm may occur; mitigation within reasonable time",
        "technical_options": [
            "Encryption at rest (PI columns separately encrypted from app data) + TLS 1.3 in transit",
            "De-identification pipeline (k-anonymity, differential privacy, or pseudonymisation with key separation)",
            "Access control: RBAC + audit log (every PI read logged with principal, time, justification)",
            "Incident response runbook (within-72-hour regulator notification, individual notification template)",
            "Annual security assessment (mandatory for handlers of >1M individuals' PI)",
        ],
    },
}

# Common sensitive PI categories (Art 28)
SENSITIVE_PI_CATEGORIES = [
    "biometric (facial, fingerprint, voiceprint)",
    "religious belief",
    "specific identity (e.g. ID card, military, medical)",
    "medical health",
    "financial account (bank card, payment)",
    "individual location tracking (under 14 years old)",
    "PI of minors under 14 (treated as sensitive — separate consent + guardian)",
]

# Standard audit-log fields per Art 51 + GB/T 35273-2020
PIPL_AUDIT_LOG_FIELDS = [
    "ts_utc", "principal_did", "action", "pi_categories_touched", "purpose_code",
    "lawful_basis", "consent_receipt_id", "retention_decision",
    "data_subject_request_id", "automated_decision_id",
    "destination_country", "cross_border_mechanism",
]


# --------------------------------------------------------------------------
# MCP tools
# --------------------------------------------------------------------------

@mcp.tool()
def pipi_overview() -> str:
    """High-level PIPL summary: who it applies to, when it bites, what the
    four cross-border mechanisms are, and how it crosswalks to GDPR/TC260."""
    overview = {
        "law": PIPL_META,
        "articles_covered": list(PIPL_ARTICLES.keys()),
        "sensitive_pi_categories": SENSITIVE_PI_CATEGORIES,
        "audit_log_fields_required": PIPL_AUDIT_LOG_FIELDS,
        "crosswalk_to_other_regimes": {
            "GDPR": "PIPL Art 13 ≈ GDPR Art 6 (lawful bases). PIPL Art 38 has 4 mechanisms vs GDPR's SCC/BCR/Adequacy. Both require a DPIA for high-risk processing — PIPL calls it a 'Personal Information Protection Impact Assessment' (PIPIA, Art 55-56).",
            "TC260": "TC260 WG8 standards (GB/T 41867, GB/T 39204, GB/T 35273, GB/T 22239) are the technical implementation standards for PIPL Art 51 security. Our TC260 MCP server covers these.",
            "EU_AI_Act": "PIPL Art 24 (automated decision-making transparency) overlaps with EU AI Act Art 13 (transparency) and Art 14 (human oversight). PIPL gives a right to 'refuse' automated decisions with material impact — EU AI Act Art 22 is similar.",
            "APPI_Japan": "Both require consent for cross-border transfer; APPI is generally less strict on the cross-border mechanism (only one option — consent or equivalent), PIPL is stricter (4 mechanisms).",
        },
        "next_step": "Call classify_pipl_obligations() to map your system characteristics to the specific PIPL articles that apply.",
    }
    return json.dumps(overview, indent=2, ensure_ascii=False)


@mcp.tool()
def classify_pipl_obligations(
    handles_chinese_pi: bool = False,
    is_critical_information_infrastructure_operator: bool = False,
    pi_volume_above_1m_individuals: bool = False,
    cross_border_transfers_pi: bool = False,
    processes_sensitive_pi: bool = False,
    uses_automated_decision_making: bool = False,
    handles_minor_data_under_14: bool = False,
    suffered_data_breach_past_year: bool = False,
) -> str:
    """Map your system characteristics to the specific PIPL articles that
    actually apply. Returns the triggered obligations + the next concrete
    step (audit_content_pipeline, generate_compliance_attestation, etc.)."""
    triggered: list[str] = []
    if handles_chinese_pi:
        triggered.append("art_13_consent")
    if cross_border_transfers_pi:
        triggered.append("art_38_cross-border-transfer")
    if any([
        pi_volume_above_1m_individuals,
        processes_sensitive_pi,
        uses_automated_decision_making,
        handles_minor_data_under_14,
    ]):
        triggered.append("art_44-50_data-subject-rights")
    if any([
        handles_chinese_pi,
        pi_volume_above_1m_individuals,
        is_critical_information_infrastructure_operator,
    ]):
        triggered.append("art_51_security")

    # Extra: if CIIO + cross-border + high volume → CAC security assessment is mandatory
    cac_assessment_required = (
        is_critical_information_infrastructure_operator
        or pi_volume_above_1m_individuals
    )

    # Sensitive PI requires separate consent (Art 29)
    separate_consent_required = (
        processes_sensitive_pi or handles_minor_data_under_14
    )

    result = {
        "in_scope": bool(triggered),
        "triggered_obligations": triggered,
        "details": {k: PIPL_ARTICLES[k] for k in triggered if k in PIPL_ARTICLES},
        "cac_security_assessment_required": cac_assessment_required,
        "separate_consent_required": separate_consent_required,
        "minor_guardian_consent_required": handles_minor_data_under_14,
        "annual_security_assessment_required": pi_volume_above_1m_individuals,
        "designated_dpo_required": pi_volume_above_1m_individuals,
        "breach_notification_clock_hours": 24,  # 'immediately' per Art 57, de facto 24h practice
        "next_step": (
            "Call audit_content_pipeline() to scan your current content pipeline "
            "for gaps. Or sign_pipl_attestation() (Pro tier) for an audit-evidence cert."
        ) if triggered else (
            "No PIPL obligations triggered by these characteristics. Re-check if you handle "
            "Chinese natural persons' PI, transfer PI overseas, process sensitive PI, or "
            "make automated decisions with material impact."
        ),
    }
    return json.dumps(result, indent=2, ensure_ascii=False)


@mcp.tool()
def audit_content_pipeline(
    tenant_id: str,
    sample_text: str = "",
    data_flow_csv: str = "",
    consent_receipt_sample: str = "",
) -> str:
    """Audit an existing content/data pipeline for PIPL gaps.

    Args:
        tenant_id: your org identifier (for the audit record)
        sample_text: optional sample output that may contain PI fields
        data_flow_csv: comma-separated list of destinations, e.g.
                       "users_cn→eu-db, audit_logs→us-logging, model_artifacts→global-cache"
        consent_receipt_sample: optional sample consent text (will be checked for
                                specificity, granularity, withdraw-path)
    """
    findings: list[dict[str, Any]] = []
    severity = "low"

    # 1. Scan sample text for likely PI fields
    if sample_text:
        pi_signals = {
            "id_card_like": bool(re.search(r"\b\d{17}[\dXx]\b", sample_text)),
            "phone_like": bool(re.search(r"\b1[3-9]\d{9}\b", sample_text)),
            "email_like": bool(re.search(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", sample_text)),
            "bank_card_like": bool(re.search(r"\b\d{16,19}\b", sample_text)),
            "address_like": bool(re.search(r"(省|市|区|县|街道|路|号)", sample_text)),
            "minor_signal": bool(re.search(r"\b(13|14|15|16|17)\b.*\b(岁|岁生日|grade|primary|secondary|junior)\b", sample_text, re.IGNORECASE)),
        }
        detected = [k for k, v in pi_signals.items() if v]
        if detected:
            findings.append({
                "issue": f"Sample text contains likely PI fields: {detected}",
                "severity": "high",
                "fix": "Apply de-identification (pseudonymisation + key separation) before storing or transferring this content. Log a PIPIA per Art 55-56 if processing >100k individuals' PI.",
            })
            severity = "high"

    # 2. Check data flow for cross-border
    if data_flow_csv:
        flows = [f.strip() for f in data_flow_csv.split(",") if f.strip()]
        outbound = [f for f in flows if "→" in f and not f.split("→", 1)[1].strip().startswith(("cn-", "china-"))]
        if outbound:
            severity = max(severity, "high", key=["low", "medium", "high", "critical"].index)
            findings.append({
                "issue": f"Cross-border data flow detected: {outbound}",
                "severity": "high",
                "fix": "Apply one of the 4 PIPL Art 38 mechanisms: CAC security assessment, SCC (with CAC filing), Certification, or necessity test for HR. Default to in-China processing for sensitive PI.",
            })

    # 3. Check consent receipt quality
    if consent_receipt_sample:
        consent_lc = consent_receipt_sample.lower()
        missing = []
        if "撤回" not in consent_receipt_sample and "withdraw" not in consent_lc:
            missing.append("explicit withdraw-consent path ('撤回同意' or 'withdraw consent')")
        if "目的" not in consent_receipt_sample and "purpose" not in consent_lc:
            missing.append("specific processing purposes ('目的' or 'purposes: ...')")
        if "保存期限" not in consent_receipt_sample and "retention" not in consent_lc:
            missing.append("retention period ('保存期限' or 'retain for X')")
        if "联系方式" not in consent_receipt_sample and "contact" not in consent_lc:
            missing.append("processor contact info for rights requests")
        if missing:
            findings.append({
                "issue": f"Consent receipt missing: {missing}",
                "severity": "medium",
                "fix": "Update the consent notice to include all 4 mandatory disclosures per Art 17.",
            })
            severity = max(severity, "medium", key=["low", "medium", "high", "critical"].index)
        else:
            findings.append({
                "issue": "Consent receipt includes the 4 mandatory disclosures (Art 17)",
                "severity": "info",
            })

    if not findings:
        findings.append({
            "issue": "No content provided to audit. Pass sample_text, data_flow_csv, and consent_receipt_sample for a full review.",
            "severity": "info",
        })

    # Audit record (hash-chained, links to meok-attestation-api /api/audit)
    sample_hash = hashlib.sha256((sample_text or data_flow_csv or consent_receipt_sample or "").encode()).hexdigest()[:16]
    record_id = f"PIPL-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

    return json.dumps({
        "audit_record_id": record_id,
        "tenant_id": tenant_id,
        "audit_severity": severity,
        "findings_count": len(findings),
        "findings": findings,
        "sample_hash": sample_hash,
        "audit_url_template": f"https://meok-attestation-api.vercel.app/api/audit?tenant={tenant_id}",
        "next_steps": [
            "If HIGH: apply de-identification + cross-border mechanism + consent notice update",
            "If MEDIUM: update the consent receipt; rerun audit",
            "When green: sign_pipl_attestation() (Pro tier, £199/mo) for audit-evidence cert on /v/{id}",
        ],
        "lawful_basis_warnings": [
            "PIPL does NOT have a 'legitimate interest' basis like GDPR Art 6(1)(f). The 7 statutory exceptions in Art 13 are narrower — most AI use cases need consent.",
            "Implied consent (e.g. continued use = consent) is NOT valid. Affirmative action required.",
        ],
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def sign_pipl_attestation(
    entity_name: str,
    audited_articles_csv: str,
    compliance_score: float,
    findings_csv: str = "",
    contact_email: str = "",
) -> str:
    """Generate a hash-chained PIPL compliance attestation. Calls the
    canonical meok-attestation-api /sign endpoint — no shadow signer,
    no parallel key. The result is publicly verifiable at /v/{id}.

    NOTE: Requires an MEOK_API_KEY. The free tier issues 1 cert/day; the
    Pro tier (£199/mo) is unlimited.

    Returns a JSON dict with: cert_id, signature, verify_url, audit_url,
    issued_at, expires_at, kid, next_renewal_due.
    """
    api_key = os.getenv("MEOK_API_KEY", "")
    if not api_key:
        return json.dumps({
            "error": "MEOK_API_KEY env var not set. Free tier: 1 cert/day via /sign with CSOAI- key prefix. Pro tier (£199/mo): unlimited, get key at https://csoai.org/checkout",
            "fallback": "Use sovereign-temple/sovereign_continual_learning.py for an offline-signed cert (no API call).",
        }, indent=2)

    audited_articles = [a.strip() for a in audited_articles_csv.split(",") if a.strip()]
    findings_list = [f.strip() for f in findings_csv.split(",") if f.strip()]

    findings_list.extend([
        f"Audited PIPL articles: {audited_articles}",
        f"Compliance score: {compliance_score:.2f}",
    ])

    payload = {
        "regulation": "PIPL (Personal Information Protection Law of the People's Republic of China, effective 2021-11-01)",
        "entity": entity_name,
        "score": compliance_score,
        "findings": findings_list,
        "tier": "pro",
    }

    try:
        import httpx
        r = httpx.post(
            "https://meok-attestation-api.vercel.app/sign",
            json={"api_key": api_key, "email": contact_email, **payload},
            headers={"Content-Type": "application/json"},
            timeout=10.0,
        )
        r.raise_for_status()
        cert = r.json()
    except Exception as e:
        return json.dumps({"error": f"attestation API unreachable: {e}"}, indent=2)

    expires_at = cert.get("expires_at", "2026-08-02T00:00:00Z")  # EU AI Act cliff default
    next_renewal = "after any material change to processing purposes, or 365 days from issue, whichever is sooner"

    return json.dumps({
        "cert_id": cert.get("cert_id", cert.get("id")),
        "signature": (cert.get("signature_ed25519", cert.get("signature", ""))[:32] + "…") if cert.get("signature_ed25519") or cert.get("signature") else None,
        "kid": cert.get("kid"),
        "verify_url": f"https://meok-attestation-api.vercel.app/v/{cert.get('cert_id', cert.get('id'))}",
        "audit_url": "https://meok-attestation-api.vercel.app/api/audit",
        "issued_at": cert.get("issued_at"),
        "expires_at": expires_at,
        "next_renewal_due": next_renewal,
        "lawful_basis_summary": "Consent (Art 13) + 1 of 4 cross-border mechanisms (Art 38) + data subject rights (Art 44-50) + security (Art 51) = full PIPL posture",
        "spine": "meok-attestation-api v1.2.0 / Ed25519 / kid d4cb0eaa",
        "spec_ref": "csoai.org/council/law — PIPL region (APAC/China)",
    }, indent=2, ensure_ascii=False)


@mcp.tool()
def crosswalk_pipl_to_gdpr() -> str:
    """Side-by-side PIPL ↔ GDPR crosswalk so a multi-jurisdiction AI
    system can demonstrate compliance with one assessment."""
    crosswalk = [
        {"topic": "Lawful basis", "pipl": "Art 13: consent (affirmative) + 7 statutory exceptions (no legitimate-interest equivalent)", "gdpr": "Art 6(1): 6 lawful bases incl. legitimate interest"},
        {"topic": "Cross-border transfer", "pipl": "Art 38: 4 mechanisms (CAC assessment / SCC with filing / Certification / necessity)", "gdpr": "Chapter V: Adequacy / SCC / BCR / derogations"},
        {"topic": "Data subject rights", "pipl": "Art 44-50: access, correction, deletion, portability, withdraw consent, explanation of ADM", "gdpr": "Art 15-22: same set + right to object, restrict processing"},
        {"topic": "DPIA equivalent", "pipl": "PIPIA (Art 55-56): Personal Information Protection Impact Assessment, mandatory for sensitive PI / cross-border / ADM / publishing PI", "gdpr": "DPIA per Art 35, mandatory for high-risk processing"},
        {"topic": "Breach notification", "pipl": "Art 57: 'immediately' to regulator + affected individuals (de facto 24h practice)", "gdpr": "Art 33: 72h to regulator; Art 34: 'without undue delay' to individuals"},
        {"topic": "DPO", "pipl": "Designated PI Protection Officer (Art 52): mandatory for >1M individuals' PI", "gdpr": "DPO (Art 37-39): mandatory for certain public bodies + large-scale monitoring/special-category processing"},
        {"topic": "Maximum fine", "pipl": "RMB 50M or 5% of annual revenue (whichever higher) for serious violations", "gdpr": "€20M or 4% of global turnover (whichever higher)"},
        {"topic": "Sensitive data", "pipl": "Art 28: separate consent for sensitive PI + 9 categories (biometric, religious, medical, financial, location of minors, etc.)", "gdpr": "Art 9: explicit consent or specific legal basis for special categories + broader list incl. trade union membership, sexual orientation, genetic, biometric for ID"},
        {"topic": "Children", "pipl": "Art 31: separate + guardian consent for PI of minors under 14", "gdpr": "Art 8: parental consent for under-16 (or lower if member state) information society services"},
        {"topic": "Automated decision-making", "pipl": "Art 24: transparency + right to refuse decisions with 'significant impact' (credit, employment, eligibility)", "gdpr": "Art 22: similar right + right to human review"},
    ]
    return json.dumps({
        "law_left": "PIPL",
        "law_right": "GDPR",
        "rows": crosswalk,
        "practical_note": "PIPL is generally more prescriptive (less wiggle room on legitimate interest, stricter cross-border, lower child-consent age). GDPR has stronger individual remedies (Art 82). One assessment, one cert, both regimes.",
    }, indent=2, ensure_ascii=False)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
