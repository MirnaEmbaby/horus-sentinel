<div align="center">

# 🦅 HORUS SENTINEL — System Test Report

### Results vs. `USER_MANUAL.md` claimed expectations

</div>

---

> **What this is.** A record of an end-to-end test of HORUS Sentinel executed against every
> verifiable claim in [`USER_MANUAL.md`](USER_MANUAL.md) — install checks, the test suite, lint,
> and every documented API endpoint driven on a live server (real fine-tuned model via Ollama and
> live passive OSINT over the network). **Overall verdict: PASS.**

**Test run**

| | |
|---|---|
| **Date** | 2026-07-18 |
| **OS** | Windows 11 Pro (10.0.22621) |
| **Python** | 3.12.10 (venv at outer `horus-sentinel/.venv`) |
| **App dir** | inner `horus-sentinel/horus-sentinel/` |
| **Brain** | `BRAIN_BACKEND=hybrid`; Ollama reachable, `horus-osint:latest` (4.9 GB) served; HF token valid (`digilians1`) |
| **Report language** | `ar` (default) |
| **Server** | `uvicorn api.main:app` on `:8000`, `WORKER_ENABLED=true` |

---

## 1. Summary — results vs. manual

| # | Manual § | Check | Expected | Actual | Verdict |
|---|---|---|---|---|---|
| 1 | §3.3 | Dependency import (`fastapi, uvicorn, fpdf, arabic_reshaper, bidi, networkx, sqlalchemy`) | `deps OK` | `deps OK` | ✅ |
| 2 | §10.1 | `pytest -q` | `104 passed` | **104 passed** (38.8 s, 85 % coverage) | ✅ |
| 3 | §10.2 | `ruff check .` | `All checks passed!` | `All checks passed!` | ✅ |
| 3b | §10.2 | `ruff format --check .` | `96 files already formatted` | **95 formatted, 1 would reformat** (`reporting/chat_report.py`) | ⚠️ minor |
| 4 | §5.1 | `uvicorn` startup log | worker + "Application startup complete" | Verbatim match (`worker_started backend=memory`) | ✅ |
| 5 | §5.3 | `GET /health` | `{"status":"ok", …}` | Exact shape | ✅ |
| 6 | §9 | `GET /`, `/setup/status`, `/ui/`, `/docs`, `/openapi.json` | 200 | All 200; `ollama_ready:true`, `hf_token_valid:true` | ✅ |
| 7 | §10.3 | `POST /demo` + demo PDF | `status:completed, entity_count:4`; `%PDF-` | Exact match; PDF `%PDF-1.3`, 46 KB | ✅ |
| 8 | §10.3 | Authorization gate (out-of-scope `web_infra`) | HTTP 403 | 403 + exact documented detail message | ✅ |
| 9 | §9.3 | `POST /chat` (English) | model answer | `generated_by: horus-selfhosted`, real 474-char answer | ✅ |
| 10 | §9.4 | `POST /chat/report` (pdf / html) | `%PDF-` / HTML | EN PDF + HTML ✅; **AR PDF ✅** (via UTF-8) | ✅ |
| 11 | §11 | Full E2E on `example.com` (create→run→report→validate→download) | 10 entities, 6 findings, Low, PDF | **Exact match**; `generated_by: horus-osint`; validate → `completed / is_final:true`; pdf+html+json all valid | ✅ |
| 12 | §9 | `enqueue`+worker, `GET /jobs`, `GET /jobs/{id}`, `flag`/`edit`, 404 | processed / 202 / 404 | All correct (worker done in ~27 s) | ✅ |

---

## 2. Full end-to-end workflow on `example.com` (§11)

Reproduced the manual's **"Verified real-world results"** table exactly, over live DNS/RDAP:

| Metric | Manual claim | Observed | |
|---|---|---|---|
| Entities | 10 | 10 | ✅ |
| IPs | 4 | 4 (2× IPv4 + 2× IPv6, Cloudflare) | ✅ |
| Findings | 6 | 6 | ✅ |
| Top band | Low | Low | ✅ |
| PDF | ✅ | `%PDF-`, 45 KB | ✅ |

- **Pipeline:** `osint → web_infra → threat_intel` → `awaiting_validation` (run took 107 s incl. live network).
- **ATT&CK mapping:** findings mapped to `T1592` (Gather Victim Host Information) and `T1584` (Compromise Infrastructure).
- **Graph:** 10 nodes / 13 edges; edge types `EXPOSES`, `LIKELY_EMAIL_PATTERN`, `RESOLVES_TO`, `RUNS`, `SERVES`, `USES_NAMESERVER`.
- **Validation:** `validate` → `new_status: completed`, `is_final: true`.
- **Downloads:** PDF (`%PDF-`, 45 222 B), HTML (`<!doctype`, 20 872 B), JSON (19 946 B) — all valid.
- **Narrative:** `generated_by: horus-osint` — genuinely authored by the fine-tuned model.
- **Graceful degradation (non-fatal, as designed):** `crtsh` network error; `ABUSEIPDB_API_KEY not set` reputation skips; OSV "no known vulnerabilities for Cloudflare".

---

## 3. Items worth attention (neither is a functional bug)

### 3.1 Cold-start model timeout → offline fallback on the first assessment
The **guided demo** (Sinai, Arabic) returned `generated_by: offline-synthesis`. The server log shows the
Ollama call timed out at exactly **+120 s** (`ollama_unreachable … error=`, the `ollama_timeout_s`
default) because the **Arabic** narrative ran on a **cold** model. Once the model was **warm** (after the
first chat call), the `example.com` report was model-authored (`horus-osint`) and the queued worker job
finished in ~27 s.

- **Consistent with** §12 ("Arabic … may hit the 120 s timeout … then fall back") — not a defect.
- **Impact:** the *first* assessment a fresh evaluator runs may show `offline-synthesis`.
- **Optional mitigation:** pre-warm Ollama at startup, or raise `OLLAMA_TIMEOUT_S` in `.env`.

### 3.2 Format drift — one file
`reporting/chat_report.py` is not ruff-formatted, so §10.2's "96 files already formatted" is actually
**95/96**. `ruff format .` fixes it. (`ruff check` itself is clean.)

---

## 4. Non-issues ruled out

- **Arabic `/chat/report` "400 error parsing the body"** — this was **Windows-terminal UTF-8 corruption of the
  `curl` command line**, not the app. The identical request sent with proper UTF-8 (Python) returns a valid
  Arabic RTL PDF (`%PDF-`, 21.7 KB). Matches §12's cosmetic-console note.
- **Startup warnings** — `Pillow could not be imported` (fpdf2 image embedding only) and the pydantic
  `model_id` protected-namespace warning are harmless and do not affect any tested path.

---

## 5. Environment note

The virtual environment lives at the **outer** `horus-sentinel/.venv` (Python 3.12.10), one level above the
manual's per-folder instructions. All commands were run with that interpreter and the working directory set
to the inner `horus-sentinel/horus-sentinel/`. Everything functions correctly with this layout.

---

<div align="center">

**HORUS SENTINEL** · *The eye that never sleeps.*
System test: **PASS** — 12/12 areas green (1 minor format drift, 1 documented cold-start caveat).

</div>
