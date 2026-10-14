"""rm_handoff skill — liaison-to-RM escalation.

The client-liaison persona captures an inquiry from a client channel
(web, WhatsApp, SMS in prod). When the liaison orchestrator decides
the inquiry needs RM attention (anything beyond bounded FAQ scope),
it calls this skill. We write two SObjects:

1. Client_Inquiry__c — the raw inquiry text, MNPI-scrubbed, queued
   to the RM's inbox.
2. Research_Request__c (optional) — if the inquiry is ticker-specific
   and research-oriented, flag a structured research ask so Sarah
   can decide whether to upgrade it into a published brief. Drives
   Narrative 2 (client question → RM handoff → research trigger →
   brief → RM follow-up).

Every call also writes an IR_Audit_Log__c row with
Action__c=CLIENT_INQUIRY. The MNPI filter runs on the inquiry text
BEFORE the row is built so no client-supplied leak reaches Salesforce.
"""

from .actions import RmHandoffInput, RmHandoffOutput, run

__all__ = ["RmHandoffInput", "RmHandoffOutput", "run"]
