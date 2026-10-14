"""
Einstein Trust Layer integration via Salesforce Models API.

Routes CRM-related LLM reasoning through Salesforce's trust layer
for prompt defense, data masking, toxicity detection, and audit.

This is the SECOND trust layer (alongside Bedrock Guardrails).
Bedrock Guardrails handle all LLM calls. Einstein Trust Layer
handles specifically CRM data reasoning.

Architecture: No credentials in code. SF instance URL and access
token passed as function parameters.
"""

import json
import logging
import requests
from typing import Any

logger = logging.getLogger("einstein-trust-layer")

SF_API_VERSION = "v66.0"

# Models API endpoint path (prompt-completions)
_MODELS_API_PATH = f"/services/data/{SF_API_VERSION}/einstein/llm/prompt-completions"


def _build_headers(sf_access_token: str) -> dict[str, str]:
    """Standard headers for SF Models API calls."""
    return {
        "Authorization": f"Bearer {sf_access_token}",
        "Content-Type": "application/json",
    }


def is_trust_layer_available(sf_instance_url: str, sf_access_token: str) -> bool:
    """
    Check if Einstein Trust Layer / Models API is available on the org.

    Sends a lightweight probe to the Models API endpoint. Returns True
    if the endpoint exists (even if the request body is invalid — we
    only care about 404 vs non-404).
    """
    url = f"{sf_instance_url}{_MODELS_API_PATH}"
    try:
        resp = requests.post(
            url,
            json={},  # empty body — we expect a 400, not a 404
            headers=_build_headers(sf_access_token),
            timeout=10,
        )
        # 404 = Models API not provisioned on this org
        if resp.status_code == 404:
            logger.info("Einstein Trust Layer not available on this org (404)")
            return False
        # Any other status (400, 401, 200) means the endpoint exists
        return True
    except requests.ConnectionError:
        logger.warning("Could not reach SF instance to check Trust Layer availability")
        return False
    except requests.Timeout:
        logger.warning("Timeout checking Trust Layer availability")
        return False
    except requests.RequestException as exc:
        logger.warning("Error checking Trust Layer availability: %s", exc)
        return False


def generate_with_trust_layer(
    prompt: str,
    sf_instance_url: str,
    sf_access_token: str,
    model_name: str = "sfdc_ai__DefaultGPT4Omni",
    max_tokens: int = 2000,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """
    Generate text via Salesforce Einstein Trust Layer (Models API).

    This routes the prompt through SF's trust layer which provides:
    - Prompt injection detection
    - PII/sensitive data masking
    - Toxicity filtering
    - Zero data retention
    - Audit trail in SF

    Parameters
    ----------
    prompt : str
        The prompt to send (CRM context should already be included).
    sf_instance_url : str
        Salesforce instance URL.
    sf_access_token : str
        Salesforce OAuth bearer token.
    model_name : str
        SF Models API model identifier.
    max_tokens : int
        Maximum tokens in response.
    temperature : float
        LLM temperature.

    Returns
    -------
    dict
        On success:
            {"text": "...", "trust_layer": {...}, "success": True}
        On block:
            {"success": False, "blocked_reason": "..."}
        On fallback (API unavailable):
            {"success": False, "fallback": True, "message": "..."}
    """
    url = f"{sf_instance_url}{_MODELS_API_PATH}"
    payload = {
        "promptTextorId": prompt,
        "provider": model_name,
        "additionalConfig": {
            "maxTokens": max_tokens,
            "temperature": temperature,
            "applicationName": "OpenClaw_FSI_Research",
        },
    }

    try:
        resp = requests.post(
            url,
            json=payload,
            headers=_build_headers(sf_access_token),
            timeout=30,
        )
    except requests.RequestException as exc:
        logger.error("Einstein Trust Layer request failed: %s", exc)
        return {
            "success": False,
            "fallback": True,
            "message": f"Trust Layer request error: {exc}",
        }

    # Models API not provisioned on this org
    if resp.status_code == 404:
        logger.warning("Einstein Trust Layer not available on this org (404)")
        return {
            "success": False,
            "fallback": True,
            "message": "Einstein Trust Layer not available on this org",
        }

    # Auth failure
    if resp.status_code in (401, 403):
        logger.error("Trust Layer auth failed (HTTP %d)", resp.status_code)
        return {
            "success": False,
            "fallback": True,
            "message": f"Trust Layer auth failed (HTTP {resp.status_code})",
        }

    # Other HTTP errors
    if not resp.ok:
        logger.error(
            "Trust Layer HTTP %d: %s", resp.status_code, resp.text[:500]
        )
        return {
            "success": False,
            "fallback": True,
            "message": f"Trust Layer HTTP {resp.status_code}",
        }

    # ── Parse successful response ───────────────────────────────
    return _parse_trust_layer_response(resp)


def _parse_trust_layer_response(resp: requests.Response) -> dict[str, Any]:
    """Parse the Models API JSON response into our standard format."""
    try:
        body = resp.json()
    except (json.JSONDecodeError, ValueError) as exc:
        logger.error("Trust Layer returned non-JSON response: %s", exc)
        return {
            "success": False,
            "fallback": True,
            "message": "Trust Layer returned non-JSON response",
        }

    # Extract generations
    generations = body.get("generations") or body.get("generation", {})
    if isinstance(generations, list):
        generation = generations[0] if generations else {}
    elif isinstance(generations, dict):
        generation = generations
    else:
        generation = {}

    generated_text = generation.get("text", "")

    # Extract content quality / trust signals
    content_quality = generation.get("contentQuality", {})
    toxicity = content_quality.get("scanToxicity", {})
    injection = content_quality.get("scanPromptInjection", {})

    toxicity_detected = toxicity.get("isDetected", False)
    injection_detected = injection.get("isDetected", False)
    pii_detected = content_quality.get("scanPiiEntities", {}).get("isDetected", False)

    # If the trust layer blocked the request
    if injection_detected:
        logger.warning("Trust Layer BLOCKED: prompt injection detected")
        return {
            "success": False,
            "blocked_reason": "prompt_injection_detected",
        }

    if toxicity_detected:
        logger.warning("Trust Layer BLOCKED: toxicity detected")
        return {
            "success": False,
            "blocked_reason": "toxicity_detected",
        }

    # Audit event ID (may be in top-level or generation-level)
    audit_event_id = (
        body.get("id")
        or generation.get("id")
        or "unknown"
    )
    logger.info("Trust Layer audit event: %s", audit_event_id)

    return {
        "text": generated_text,
        "trust_layer": {
            "prompt_injection_detected": injection_detected,
            "toxicity_detected": toxicity_detected,
            "pii_detected": pii_detected,
            "audit_event_id": audit_event_id,
        },
        "success": True,
    }
