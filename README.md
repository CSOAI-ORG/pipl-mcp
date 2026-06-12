# meok-pipl-mcp

> PIPL (China Personal Information Protection Law, 中华人民共和国个人信息保护法) compliance MCP server by [MEOK AI Labs](https://meok.ai).

[![MEOK AI Labs](https://img.shields.io/badge/MEOK-AI%20Labs-667eea)](https://meok.ai)
[![EU AI Act](https://img.shields.io/badge/EU%20AI%20Act-Compliant-22c55e)](https://councilof.ai)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![PyPI](https://img.shields.io/pypi/v/meok-pipl-mcp)](https://pypi.org/project/meok-pipl-mcp/)

The MCP for **PIPL** (effective 1 November 2021). Covers 4 articles — the practical obligations for AI systems handling Chinese personal information:

| Article | What | Why it bites for AI |
|---|---|---|
| **Art 13** | Consent (告知·同意) | AI products handling Chinese user PI need affirmative, specific, informed consent — no implied consent, no "legitimate interest" equivalent |
| **Art 38** | Cross-border data transfer (跨境提供) | 4 mechanisms (CAC assessment / SCC / Certification / necessity test). Default to in-China processing for sensitive PI |
| **Art 44-50** | Data subject rights (个人权利) | Access, correction, deletion, portability, withdraw consent (one click), explanation of automated decisions, right to refuse ADM with material impact |
| **Art 51** | Security obligations (安全保障义务) | Encryption, de-identification, access control, audit log, incident response. Annual security assessment mandatory for >1M individuals' PI |

Crosswalks to **GDPR + TC260 + EU AI Act + APPI** so a multi-jurisdiction AI system can demonstrate compliance with one assessment.

## Install

```bash
pip install meok-pipl-mcp
meok-pipl-mcp
```

## Tools (4)

### `pipi_overview()`

High-level PIPL summary: who it applies to, when it bites, what the 4 cross-border mechanisms are, and how it crosswalks to GDPR / TC260 / EU AI Act.

### `classify_pipl_obligations(handles_chinese_pi, is_critical_information_infrastructure_operator, pi_volume_above_1m_individuals, cross_border_transfers_pi, processes_sensitive_pi, uses_automated_decision_making, handles_minor_data_under_14, suffered_data_breach_past_year)`

Map your system characteristics to the specific PIPL articles that apply. Returns the triggered obligations, the CAC security assessment requirement, the separate consent requirement, the minor guardian consent requirement, the annual security assessment requirement, the DPO requirement, and the breach notification clock.

### `audit_content_pipeline(tenant_id, sample_text, data_flow_csv, consent_receipt_sample)`

Audit an existing content/data pipeline for PIPL gaps. Scans sample text for likely PI fields (ID card, phone, email, bank card, address, minor signals), checks data flow CSV for cross-border transfers, and checks consent receipt for the 4 mandatory Art 17 disclosures (withdraw path, purposes, retention, contact).

### `sign_pipl_attestation(entity_name, audited_articles_csv, compliance_score, findings_csv, contact_email)`

Generate a hash-chained PIPL compliance attestation via the canonical meok-attestation-api `/sign` endpoint. Returns `cert_id`, `signature`, `verify_url`, `audit_url`, `issued_at`, `expires_at`, `kid`. The result is publicly verifiable at `/v/{id}`. Requires `MEOK_API_KEY` env var (free tier: 1 cert/day; Pro tier £199/mo: unlimited).

### `crosswalk_pipl_to_gdpr()`

Side-by-side PIPL ↔ GDPR crosswalk: 10 rows (lawful basis, cross-border, DSR, DPIA, breach, DPO, max fine, sensitive data, children, ADM). Practical note: PIPL is generally more prescriptive (less wiggle room on legitimate interest, stricter cross-border, lower child-consent age of 14 vs 16). GDPR has stronger individual remedies (Art 82). One assessment, one cert, both regimes.

## Honest limits

- **No CAC security assessment submission**: that requires a CAC portal account + accredited body — not in this MCP
- **No SCC filing**: same — the CAC portal is the filing authority
- **No automated decision-making test**: the MCP tells you the rule, your team / auditor runs the test
- **No cross-border mechanism issuance**: the MCP advises on which mechanism to use; the actual mechanism (SCC text, certification request) is up to you
- **No Chinese-language UI**: the MCP returns English (with key Chinese terms in pinyin + characters). Build your own UI in Chinese for the user-facing surface
- **No real-time CAC list of certified bodies**: the list is published by CAC; we link to it but don't fetch live

## Tests

```bash
cd pipl-mcp
pip install mcp httpx pytest
pytest tests/test_pipl_mcp.py -v
```

13 tests across all 4 tools, no live API required.

## Honest comparison to TC260 MCP

PIPL is the law; **TC260 WG8 standards are the technical implementation of PIPL Art 51 security.** Our `meok-tc260-compliance` MCP server covers the implementation standards; this one covers the law. Together: one assessment, both regimes.

## See also

- `meok-tc260-compliance` — China TC260 WG8 technical standards
- `meok-eu-ai-act-mcp` — EU AI Act (Art 50 watermarking is the cliff — 50 days from 2026-06-12)
- `meok-compliance-gateway` — 13-framework crosswalk
- `meok-attestation-api` — canonical SIGIL signer (Ed25519, kid d4cb0eaa)

## License

MIT — MEOK AI Labs, UK Companies House 16939677.
