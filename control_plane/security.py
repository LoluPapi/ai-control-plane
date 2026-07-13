"""Inbound security: prompt injection and privilege escalation attempts."""

from __future__ import annotations

import re
from dataclasses import dataclass

INJECTION_RE = re.compile(
    r"(?i)(ignore (?:all )?previous|disregard (?:all )?(?:prior|previous)|"
    r"system prompt|you are now|forget (?:all )?your|new instructions|"
    r"role[:\s]*system|<\|system\|>|jailbreak|developer mode|"
    r"every tenant|all tenants|without validation|approve this request)",
)

PRIVILEGE_RE = re.compile(
    r"(?i)(price list|customer data|other tenant|bypass validation|"
    r"skip validation|override policy|admin access)",
)


@dataclass(frozen=True)
class SecurityDecision:
    blocked: bool
    reason: str | None = None
    workflow_action: str = "continue"


def wrap_untrusted(raw: str) -> str:
    """Mirror StratiSell's <untrusted_user_message> envelope."""
    cleaned = raw.replace("</untrusted_user_message>", "").replace(
        "<untrusted_user_message>", ""
    )
    return f"<untrusted_user_message>\n{cleaned}\n</untrusted_user_message>"


def assess_inbound(text: str) -> SecurityDecision:
    """Block high-confidence injection / privilege escalation before model call."""
    if INJECTION_RE.search(text):
        return SecurityDecision(
            blocked=True,
            reason="Prompt injection attempt",
            workflow_action="human_review",
        )
    if PRIVILEGE_RE.search(text) and INJECTION_RE.search(text):
        return SecurityDecision(
            blocked=True,
            reason="Privilege escalation attempt",
            workflow_action="human_review",
        )
    if "ignore all previous" in text.lower() and "without validation" in text.lower():
        return SecurityDecision(
            blocked=True,
            reason="Prompt injection attempt",
            workflow_action="human_review",
        )
    return SecurityDecision(blocked=False)
