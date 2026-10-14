"""One-shot scaffolder for V3 Salesforce SObject fields.

Run once during build to emit the -meta.xml files under
force-app/main/default/objects/<SObject>/fields/. This script is
committed so reviewers can read the schema as data, not regex hunt.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent / "force-app" / "main" / "default" / "objects"


def field_xml(props: dict) -> str:
    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<CustomField xmlns="http://soap.sforce.com/2006/04/metadata">']
    lines.append(f"    <fullName>{props['fullName']}</fullName>")
    for k, v in props.items():
        if k == "fullName":
            continue
        if k == "valueSet":
            lines.append("    <valueSet>")
            lines.append("        <valueSetDefinition>")
            lines.append(f"            <sorted>{str(v.get('sorted', False)).lower()}</sorted>")
            for value in v["values"]:
                lines.append("            <value>")
                lines.append(f"                <fullName>{value}</fullName>")
                lines.append(f"                <default>false</default>")
                lines.append(f"                <label>{value}</label>")
                lines.append("            </value>")
            lines.append("        </valueSetDefinition>")
            lines.append("    </valueSet>")
        elif isinstance(v, bool):
            lines.append(f"    <{k}>{str(v).lower()}</{k}>")
        else:
            lines.append(f"    <{k}>{v}</{k}>")
    lines.append("</CustomField>")
    return "\n".join(lines) + "\n"


def write(sobject: str, field_name: str, props: dict) -> None:
    out = ROOT / sobject / "fields" / f"{field_name}.field-meta.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(field_xml({"fullName": field_name, **props}))


# Research_Brief__c
write("Research_Brief__c", "Ticker__c", {"label": "Ticker", "type": "Text", "length": 16, "required": True})
write("Research_Brief__c", "Thesis__c", {"label": "Thesis", "type": "LongTextArea", "length": 32768, "visibleLines": 10})
write("Research_Brief__c", "Sentiment_Score__c", {"label": "Sentiment Score", "type": "Number", "precision": 5, "scale": 4})
write("Research_Brief__c", "Risk_Factors__c", {"label": "Risk Factors", "type": "LongTextArea", "length": 32768, "visibleLines": 10})
write("Research_Brief__c", "Compliance_Status__c", {"label": "Compliance Status", "type": "Picklist", "valueSet": {"values": ["CLEAR", "REVIEW", "BLOCKED"]}})
write("Research_Brief__c", "Mnpi_Cleared__c", {"label": "MNPI Cleared", "type": "Checkbox", "defaultValue": "false"})
write("Research_Brief__c", "Rm_Consumable__c", {"label": "RM Consumable", "type": "Checkbox", "defaultValue": "false"})
write("Research_Brief__c", "Client_Demand__c", {"label": "Client Demand", "type": "Picklist", "valueSet": {"values": ["low", "medium", "high"]}})
write("Research_Brief__c", "Source_Chunk_Ids__c", {"label": "Source Chunk IDs", "type": "LongTextArea", "length": 32768, "visibleLines": 6})
write("Research_Brief__c", "Published_At__c", {"label": "Published At", "type": "DateTime"})
write("Research_Brief__c", "Author_Agent_Id__c", {"label": "Author Agent Id", "type": "Text", "length": 80})

# Client_Inquiry__c
write("Client_Inquiry__c", "Client_Contact_Id__c", {
    "label": "Client Contact", "type": "Lookup",
    "referenceTo": "Contact", "relationshipName": "Client_Inquiries",
    "relationshipLabel": "Client Inquiries", "deleteConstraint": "SetNull",
})
write("Client_Inquiry__c", "Inquiry_Text__c", {"label": "Inquiry Text", "type": "LongTextArea", "length": 10000, "visibleLines": 6})
write("Client_Inquiry__c", "Channel__c", {"label": "Channel", "type": "Picklist", "valueSet": {"values": ["Web", "Slack", "WhatsApp", "WeChat", "SMS", "Email"]}})
write("Client_Inquiry__c", "Ticker_Mentions__c", {"label": "Ticker Mentions", "type": "Text", "length": 255})
write("Client_Inquiry__c", "Type__c", {"label": "Type", "type": "Picklist", "valueSet": {"values": ["question", "alert", "research-suggestion"]}})
write("Client_Inquiry__c", "Resolved_By_Rm__c", {"label": "Resolved by RM", "type": "Checkbox", "defaultValue": "false"})
write("Client_Inquiry__c", "Linked_Brief_Id__c", {
    "label": "Linked Brief", "type": "Lookup",
    "referenceTo": "Research_Brief__c", "relationshipName": "Client_Inquiries",
    "relationshipLabel": "Client Inquiries", "deleteConstraint": "SetNull",
})

# IR_Audit_Log__c (V3)
write("IR_Audit_Log__c", "Principal_Id__c", {"label": "Principal Id", "type": "Text", "length": 255, "required": True})
write("IR_Audit_Log__c", "Action__c", {"label": "Action", "type": "Picklist", "valueSet": {"values": [
    "RESEARCH_PUBLISHED", "ADVISORY_QUERY", "CLIENT_INQUIRY",
    "TRADE_SUBMITTED", "TRADE_REJECTED", "TRADE_TIMEOUT",
    "WIRE_INITIATED", "WIRE_BLOCKED",
    "COMPLIANCE_BLOCKED", "HITL_APPROVED", "HITL_REJECTED",
    "DUAL_AUTH_REQUESTED", "DUAL_AUTH_APPROVED",
    "KYC_SCREENING", "ACCOUNT_OPENED",
]}})
write("IR_Audit_Log__c", "Timestamp__c", {"label": "Timestamp", "type": "DateTime", "required": True})
write("IR_Audit_Log__c", "Gate_Trace__c", {"label": "Gate Trace", "type": "LongTextArea", "length": 32768, "visibleLines": 10})
write("IR_Audit_Log__c", "Approved_By__c", {"label": "Approved By", "type": "Text", "length": 255})
write("IR_Audit_Log__c", "Dual_Approver__c", {"label": "Dual Approver", "type": "Text", "length": 255})
write("IR_Audit_Log__c", "Mulesoft_Reference__c", {"label": "MuleSoft Reference", "type": "Text", "length": 120})
write("IR_Audit_Log__c", "Research_Brief_Id__c", {
    "label": "Research Brief", "type": "Lookup",
    "referenceTo": "Research_Brief__c", "relationshipName": "Audit_Logs",
    "relationshipLabel": "Audit Logs", "deleteConstraint": "SetNull",
})
write("IR_Audit_Log__c", "Client_Contact_Id__c", {
    "label": "Client Contact", "type": "Lookup",
    "referenceTo": "Contact", "relationshipName": "Audit_Logs",
    "relationshipLabel": "Audit Logs", "deleteConstraint": "SetNull",
})

# IR_Pending_Approval__c
write("IR_Pending_Approval__c", "ActionPlan_Hash__c", {"label": "ActionPlan Hash", "type": "Text", "length": 128, "required": True, "unique": True, "caseSensitive": True})
write("IR_Pending_Approval__c", "Requested_By__c", {
    "label": "Requested By", "type": "Lookup",
    "referenceTo": "User", "relationshipName": "Requested_Approvals",
    "relationshipLabel": "Requested Approvals", "deleteConstraint": "SetNull",
})
write("IR_Pending_Approval__c", "Status__c", {"label": "Status", "type": "Picklist", "valueSet": {"values": ["pending", "approved", "rejected", "expired"]}})
write("IR_Pending_Approval__c", "Senior_Approver_Id__c", {
    "label": "Senior Approver", "type": "Lookup",
    "referenceTo": "User", "relationshipName": "Approved_Approvals",
    "relationshipLabel": "Approved Approvals", "deleteConstraint": "SetNull",
})
write("IR_Pending_Approval__c", "Expires_At__c", {"label": "Expires At", "type": "DateTime"})

print("Scaffolded all fields.")

# Platform Event: Research_Brief_Published__e
write("Research_Brief_Published__e", "Brief_Id__c", {"label": "Brief Id", "type": "Text", "length": 18, "required": True})
write("Research_Brief_Published__e", "Ticker__c", {"label": "Ticker", "type": "Text", "length": 16, "required": True})
write("Research_Brief_Published__e", "Principal_Id__c", {"label": "Principal Id", "type": "Text", "length": 255, "required": True})
write("Research_Brief_Published__e", "Published_At__c", {"label": "Published At", "type": "DateTime", "required": True})
print("Scaffolded platform event fields.")
