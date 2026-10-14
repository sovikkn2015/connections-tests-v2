"""
Salesforce Bidirectional Client — OAuth2 Client Credentials Flow

Provides methods to call back into Salesforce for CRM data via the
SF MCP Server endpoint (IR_McpServerEndpoint). Uses Connected App
credentials from environment variables.

Token caching: reuses access token until expiry (with 60s buffer).
Graceful fallback: returns empty/default data if SF is unreachable.

Usage:
    from salesforce_client import SalesforceClient

    sf = SalesforceClient()
    coverage = sf.get_analyst_coverage("NVDA")
    company = sf.get_company_info("AAPL")
    meetings = sf.get_meeting_history("MSFT")
"""

import json
import logging
import os
import time
from urllib import request as urllib_request
from urllib.parse import urlencode
from urllib.error import URLError

logger = logging.getLogger(__name__)

SF_CLIENT_ID = os.environ.get("SF_CLIENT_ID", "")
SF_CLIENT_SECRET = os.environ.get("SF_CLIENT_SECRET", "")
SF_TOKEN_URL = os.environ.get(
    "SF_TOKEN_URL", "https://login.salesforce.com/services/oauth2/token"
)
SF_INSTANCE_URL = os.environ.get("SF_INSTANCE_URL", "")
SF_MCP_ENDPOINT = os.environ.get("SF_MCP_ENDPOINT", "/services/apexrest/ir-mcp")

# Token cache (module-level for Lambda warm starts)
_token_cache = {
    "access_token": None,
    "expires_at": 0,
}

TOKEN_EXPIRY_BUFFER_SECONDS = 60
REQUEST_TIMEOUT_SECONDS = 15


class SalesforceClient:
    """Client for bidirectional communication with Salesforce CRM.

    Uses OAuth2 client_credentials flow to authenticate, then calls the
    Salesforce MCP Server REST endpoint for CRM data retrieval.
    """

    def __init__(self):
        """Initialize the Salesforce client with environment configuration."""
        self.client_id = SF_CLIENT_ID
        self.client_secret = SF_CLIENT_SECRET
        self.token_url = SF_TOKEN_URL
        self.instance_url = SF_INSTANCE_URL.rstrip("/")
        self.mcp_endpoint = SF_MCP_ENDPOINT

    def is_configured(self):
        """Check whether Salesforce credentials are present.

        Returns:
            bool: True if all required credentials are set.
        """
        return bool(
            self.client_id
            and self.client_secret
            and self.instance_url
            and self.client_id != "CONFIGURE_AFTER_DEPLOY"
        )

    def _get_access_token(self):
        """Obtain or reuse a cached OAuth2 access token.

        Uses client_credentials grant type. Caches the token and reuses
        it until 60 seconds before expiry.

        Returns:
            str: Access token, or empty string on failure.
        """
        global _token_cache

        now = time.time()
        if (
            _token_cache["access_token"]
            and _token_cache["expires_at"] > now + TOKEN_EXPIRY_BUFFER_SECONDS
        ):
            return _token_cache["access_token"]

        if not self.is_configured():
            logger.debug("Salesforce not configured — skipping token fetch")
            return ""

        try:
            form_data = urlencode({
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            }).encode("utf-8")

            req = urllib_request.Request(
                self.token_url,
                data=form_data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                method="POST",
            )

            with urllib_request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                access_token = data.get("access_token", "")
                # Salesforce tokens typically last 2 hours (7200s)
                issued_at_ms = int(data.get("issued_at", str(int(now * 1000))))
                expires_in = 7200  # default 2 hours
                _token_cache["access_token"] = access_token
                _token_cache["expires_at"] = (issued_at_ms / 1000) + expires_in
                logger.info("Salesforce access token obtained successfully")
                return access_token

        except URLError as exc:
            logger.warning("Salesforce token request failed: %s", exc)
            return ""
        except Exception as exc:
            logger.warning("Salesforce token unexpected error: %s", exc)
            return ""

    def _call_mcp(self, tool_name, arguments):
        """Call the Salesforce MCP Server endpoint.

        Args:
            tool_name: The MCP tool name to invoke (e.g. 'get_analyst_coverage').
            arguments: Dict of arguments to pass to the tool.

        Returns:
            dict: The parsed response data, or empty dict on failure.
        """
        token = self._get_access_token()
        if not token:
            logger.debug("No SF token — returning empty result for %s", tool_name)
            return {}

        url = f"{self.instance_url}{self.mcp_endpoint}"
        payload = json.dumps({
            "tool": tool_name,
            "arguments": arguments,
        }).encode("utf-8")

        try:
            req = urllib_request.Request(
                url,
                data=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {token}",
                },
                method="POST",
            )

            with urllib_request.urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data

        except URLError as exc:
            logger.warning("SF MCP call failed for %s: %s", tool_name, exc)
            return {}
        except Exception as exc:
            logger.warning("SF MCP unexpected error for %s: %s", tool_name, exc)
            return {}

    def get_analyst_coverage(self, ticker):
        """Get analyst coverage data for a ticker from Salesforce CRM.

        Args:
            ticker: Stock ticker symbol (e.g. 'NVDA').

        Returns:
            dict: Analyst coverage data including analysts, ratings, and
                  coverage history. Returns fallback data if SF unavailable.
        """
        result = self._call_mcp("get_analyst_coverage", {"ticker": ticker})
        if result:
            return result

        # Graceful fallback
        return {
            "source": "fallback",
            "ticker": ticker,
            "message": "Salesforce CRM data unavailable — using fallback.",
            "analysts": [],
            "coverage_count": 0,
        }

    def get_company_info(self, ticker):
        """Get company information from Salesforce CRM.

        Args:
            ticker: Stock ticker symbol (e.g. 'AAPL').

        Returns:
            dict: Company info including account details, relationship
                  history, and CRM metadata. Returns fallback if unavailable.
        """
        result = self._call_mcp("get_company_info", {"ticker": ticker})
        if result:
            return result

        # Graceful fallback
        return {
            "source": "fallback",
            "ticker": ticker,
            "message": "Salesforce CRM data unavailable — using fallback.",
            "company_name": "",
            "account_id": "",
        }

    def get_meeting_history(self, ticker):
        """Get meeting history for a ticker from Salesforce CRM.

        Args:
            ticker: Stock ticker symbol (e.g. 'MSFT').

        Returns:
            dict: Meeting history including dates, attendees, and notes.
                  Returns fallback data if SF unavailable.
        """
        result = self._call_mcp("get_meeting_history", {"ticker": ticker})
        if result:
            return result

        # Graceful fallback
        return {
            "source": "fallback",
            "ticker": ticker,
            "message": "Salesforce CRM data unavailable — using fallback.",
            "meetings": [],
            "meeting_count": 0,
        }
