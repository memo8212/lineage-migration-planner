"""Optional AI suggestions for gap questions.

Two layers:
  1. **Heuristic** (always available, offline) — rules over the question context.
  2. **LLM** (optional) — used only if configured via environment variables
     (OpenAI-compatible or Databricks Foundation Model API). The human still
     confirms every answer, so the assistant is human-in-the-loop.

Env:
  OPENAI_API_KEY, OPENAI_BASE_URL (default https://api.openai.com/v1),
  OPENAI_MODEL (default gpt-4o-mini)
  or DATABRICKS_HOST + DATABRICKS_TOKEN (+ DATABRICKS_MODEL)
"""
from __future__ import annotations

import json
import os
import urllib.request

_EXT_TECH = {
    "bteq": "teradata", "ctl": "oracle", "sql": "sql", "py": "python",
    "sh": "shell", "ksh": "shell", "bat": "batch", "cmd": "batch", "ps1": "powershell",
    "jcl": "jcl", "sas": "sas", "xml": "informatica", "json": "elasticsearch",
    "ipynb": "notebook", "yaml": "config", "yml": "config", "ini": "config",
    "properties": "config", "env": "config", "txt": "file", "csv": "file",
}


def tech_for_ext(ext: str) -> str:
    return _EXT_TECH.get((ext or "").lower(), "")


def provider() -> str:
    if os.environ.get("OPENAI_API_KEY"):
        return "openai"
    if os.environ.get("DATABRICKS_TOKEN") and os.environ.get("DATABRICKS_HOST"):
        return "databricks"
    return ""


def heuristic(question) -> tuple[str, str]:
    kind = question.kind
    name = (question.context.get("name") or "").upper()
    if kind == "placeholder":
        if name.startswith("WF_") or "WORKFLOW" in name or name.startswith("BOX_"):
            return "workflow", "name looks like a workflow/box"
        if "SCRIPT" in name or "DDL" in name or name.endswith(".SQL"):
            return "program", "name looks like a script"
        if name.startswith(("PREPARE", "PUBLISH", "LOAD", "EXTRACT", "BUILD", "REFRESH", "RUN")) \
                or name.endswith(("_DIRS", "_REPORT", "_STEP")):
            return "program", "name looks like a program/step"
        return "external", "unresolved reference — treat as external"
    if kind == "orphan_source":
        if name.startswith("RAW_") or name.startswith("STG_") or name.endswith("_LANDING"):
            return "external", "name looks like a raw/landing source"
        return "external", "no producer found — likely an external source"
    if kind == "orphan_sink":
        return "terminal", "no consumer — likely a final output/report"
    if kind == "unknown_file":
        ext = question.context.get("ext", "")
        if ext in ("ipynb",):
            return "program", "Jupyter notebook"
        if ext in ("ctl", "bteq"):
            return "program", "database load script"
        if ext in ("yaml", "yml", "ini", "properties", "env"):
            return "config", "configuration file"
        return "file", f"unrecognized .{ext} — treat as a data file"
    if kind == "ambiguous_column":
        return (question.options[0] if question.options else ""), "first candidate table"
    return (question.default or ""), "default"


def _llm_answer(question, estate_hint: str = "") -> str | None:
    prov = provider()
    if not prov:
        return None
    prompt = (
        "You are a data-migration analyst. Answer ONE question about a legacy "
        "estate's lineage with exactly one of the allowed options.\n\n"
        f"Question: {question.prompt}\n"
        f"Allowed options: {', '.join(question.options)}\n"
        f"Context: {json.dumps(question.context)}\n"
        f"{('Estate: ' + estate_hint) if estate_hint else ''}\n"
        "Reply with ONLY the option value."
    )
    if prov == "openai":
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        url = base.rstrip("/") + "/chat/completions"
        headers = {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}",
                   "Content-Type": "application/json"}
        model = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    else:
        host = os.environ["DATABRICKS_HOST"].rstrip("/")
        model = os.environ.get("DATABRICKS_MODEL", "databricks-meta-llama-3-1-70b-instruct")
        url = f"{host}/serving-endpoints/{model}/invocations"
        headers = {"Authorization": f"Bearer {os.environ['DATABRICKS_TOKEN']}",
                   "Content-Type": "application/json"}
    body = json.dumps({"model": model, "temperature": 0, "max_tokens": 8,
                       "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        data = json.loads(resp.read().decode())
    text = data["choices"][0]["message"]["content"].strip().strip(".\"' ")
    for opt in question.options:
        if opt.lower() == text.lower():
            return opt
    return text or None


def suggest(question, estate_hint: str = "") -> dict:
    """Return {answer, reason, source} for one question."""
    ans, reason = heuristic(question)
    prov = provider()
    if prov:
        try:
            llm = _llm_answer(question, estate_hint)
            if llm:
                return {"answer": llm, "reason": f"{prov} suggestion", "source": prov}
        except Exception:  # noqa: BLE001 - never fail the interview on LLM errors
            pass
    return {"answer": ans, "reason": reason, "source": "heuristic"}
