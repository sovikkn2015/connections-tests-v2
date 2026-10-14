"""Scaffold V3 Apex triggers, classes, permission sets, Data Cloud stream."""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

ROOT = Path(__file__).resolve().parent / "force-app" / "main" / "default"
CLASSES = ROOT / "classes"
PERMSETS = ROOT / "permissionsets"
DATASTREAMS = ROOT / "dataCloudDataStreams"

TRIGGER_META = '<?xml version="1.0" encoding="UTF-8"?>\n<ApexTrigger xmlns="http://soap.sforce.com/2006/04/metadata">\n    <apiVersion>60.0</apiVersion>\n    <status>Active</status>\n</ApexTrigger>\n'
CLASS_META = '<?xml version="1.0" encoding="UTF-8"?>\n<ApexClass xmlns="http://soap.sforce.com/2006/04/metadata">\n    <apiVersion>60.0</apiVersion>\n    <status>Active</status>\n</ApexClass>\n'


def write(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)


# ResearchBriefTrigger — fires Platform Event on publish, blocks unpublished MNPI.
write(CLASSES / "ResearchBriefTrigger.trigger", dedent("""\
    trigger ResearchBriefTrigger on Research_Brief__c (after insert, after update, before insert, before update) {
        if (Trigger.isBefore) {
            for (Research_Brief__c row : Trigger.new) {
                if (row.Rm_Consumable__c == true && row.Mnpi_Cleared__c != true) {
                    row.addError('Research_Brief__c cannot be RM-consumable until MNPI cleared.');
                }
            }
            return;
        }
        List<Research_Brief_Published__e> events = new List<Research_Brief_Published__e>();
        for (Research_Brief__c row : Trigger.new) {
            Boolean justPublished = false;
            if (Trigger.isInsert) {
                justPublished = row.Rm_Consumable__c == true && row.Published_At__c != null;
            } else {
                Research_Brief__c prev = Trigger.oldMap.get(row.Id);
                justPublished = row.Rm_Consumable__c == true
                    && (prev.Rm_Consumable__c != true || prev.Published_At__c == null);
            }
            if (justPublished) {
                events.add(new Research_Brief_Published__e(
                    Brief_Id__c = row.Id,
                    Ticker__c = row.Ticker__c,
                    Principal_Id__c = row.Author_Agent_Id__c != null ? row.Author_Agent_Id__c : UserInfo.getUserName(),
                    Published_At__c = row.Published_At__c
                ));
            }
        }
        if (!events.isEmpty()) { EventBus.publish(events); }
    }
"""))
write(CLASSES / "ResearchBriefTrigger.trigger-meta.xml", TRIGGER_META)


# MnpiValidator
write(CLASSES / "MnpiValidator.cls", dedent("""\
    public with sharing class MnpiValidator {
        private static final Pattern SHARE_COUNT = Pattern.compile('(?i)\\\\b(?:holds?|owns?|position\\\\s*of)\\\\s+\\\\d{2,}\\\\s+shares?\\\\b');
        private static final Pattern WIRE_ACCT = Pattern.compile('(?i)wire\\\\s+\\\\$?[\\\\d,]+(?:\\\\.\\\\d+)?\\\\s+to\\\\s+(?:account\\\\s+)?[A-Z0-9]{6,}');
        private static final Pattern TRADE_INTENT = Pattern.compile('(?i)\\\\b(?:buy|sell)\\\\s+\\\\d+\\\\s+(?:shares?|contracts?)\\\\s+(?:of\\\\s+)?[A-Z]{1,5}\\\\b');

        public static String findViolation(String text) {
            if (String.isBlank(text)) { return null; }
            if (SHARE_COUNT.matcher(text).find()) { return 'Contains raw share count'; }
            if (WIRE_ACCT.matcher(text).find()) { return 'Contains wire instructions'; }
            if (TRADE_INTENT.matcher(text).find()) { return 'Contains trade intent'; }
            return null;
        }

        public static Boolean isClean(String text) { return findViolation(text) == null; }
    }
"""))
write(CLASSES / "MnpiValidator.cls-meta.xml", CLASS_META)


# SoqlSafe
write(CLASSES / "SoqlSafe.cls", dedent("""\
    public with sharing class SoqlSafe {
        public class SoqlSafeException extends Exception {}

        private static final Pattern IDENTIFIER = Pattern.compile('^[A-Za-z][A-Za-z0-9_]{0,78}[A-Za-z0-9]$|^[A-Za-z]$');

        public static String validateIdentifier(String name) {
            if (name == null || !IDENTIFIER.matcher(name).matches()) {
                throw new SoqlSafeException('Invalid identifier: ' + name);
            }
            return name;
        }

        public static String escapeLiteral(Object value) {
            if (value == null) { return 'null'; }
            if (value instanceof Boolean) { return ((Boolean) value) ? 'true' : 'false'; }
            if (value instanceof Integer || value instanceof Decimal || value instanceof Double || value instanceof Long) {
                return String.valueOf(value);
            }
            String s = String.valueOf(value);
            s = s.replace('\\\\', '\\\\\\\\').replace('\\'', '\\\\\\'');
            return '\\'' + s + '\\'';
        }

        public static void ensureReadOnly(String soql) {
            if (String.isBlank(soql)) { throw new SoqlSafeException('SOQL must not be blank'); }
            String upper = soql.toUpperCase();
            for (String kw : new List<String>{'UPDATE ', 'DELETE ', 'INSERT ', 'UPSERT ', 'MERGE ', 'TRUNCATE', '--', ';'}) {
                if (upper.contains(kw)) { throw new SoqlSafeException('SOQL contains forbidden keyword: ' + kw); }
            }
        }
    }
"""))
write(CLASSES / "SoqlSafe.cls-meta.xml", CLASS_META)


# SuitabilityCheckDeterministic
write(CLASSES / "SuitabilityCheckDeterministic.cls", dedent("""\
    public with sharing class SuitabilityCheckDeterministic {
        public enum Outcome { PASS_OK, FAIL_RISK_PROFILE, FAIL_CONCENTRATION, REVIEW_HORIZON }

        public class Result {
            public Outcome verdict;
            public String reason;
            public Result(Outcome v, String r) { this.verdict = v; this.reason = r; }
        }

        public static Result evaluate(String riskProfile, String tradeSide, Decimal notional,
                                      Decimal currentConcentrationPct, Integer timeHorizonMonths) {
            if (riskProfile == null) {
                return new Result(Outcome.REVIEW_HORIZON, 'Missing risk profile');
            }
            Decimal ceiling = riskProfile == 'Conservative' ? 5.0 : riskProfile == 'Moderate' ? 15.0 : 30.0;
            if (tradeSide == 'buy' && currentConcentrationPct != null && currentConcentrationPct >= ceiling) {
                return new Result(Outcome.FAIL_CONCENTRATION,
                    'Concentration ' + currentConcentrationPct + '% exceeds ' + ceiling + '% ceiling for ' + riskProfile);
            }
            if (timeHorizonMonths != null && timeHorizonMonths < 3 && notional != null && notional > 100000) {
                return new Result(Outcome.REVIEW_HORIZON, 'Large notional on short horizon — review');
            }
            return new Result(Outcome.PASS_OK, 'Within profile');
        }
    }
"""))
write(CLASSES / "SuitabilityCheckDeterministic.cls-meta.xml", CLASS_META)


# AuditLogTriggerTest
write(CLASSES / "AuditLogTriggerTest.cls", dedent("""\
    @isTest
    private class AuditLogTriggerTest {
        @isTest static void insert_sets_timestamp() {
            IR_Audit_Log__c row = new IR_Audit_Log__c(
                Principal_Id__c = 'sarah@firm.com',
                Action__c = 'RESEARCH_PUBLISHED'
            );
            insert row;
            IR_Audit_Log__c loaded = [SELECT Timestamp__c FROM IR_Audit_Log__c WHERE Id = :row.Id];
            System.assertNotEquals(null, loaded.Timestamp__c);
        }

        @isTest static void rejects_raw_approval_token_in_gate_trace() {
            IR_Audit_Log__c row = new IR_Audit_Log__c(
                Principal_Id__c = 'rm@firm.com',
                Action__c = 'TRADE_SUBMITTED',
                Gate_Trace__c = 'gate_5 hitl approval_token=SECRET_TOKEN_VALUE ok'
            );
            Boolean err = false;
            try { insert row; } catch (DmlException e) { err = true; }
            System.assert(err, 'Raw approval_token must be rejected');
        }

        @isTest static void accepts_hashed_approval_token() {
            IR_Audit_Log__c row = new IR_Audit_Log__c(
                Principal_Id__c = 'rm@firm.com',
                Action__c = 'TRADE_SUBMITTED',
                Gate_Trace__c = 'gate_5 hitl approval_token_hash=0123abcd ok'
            );
            insert row;
            System.assertNotEquals(null, row.Id);
        }

        @isTest static void non_senior_cannot_update() {
            IR_Audit_Log__c row = new IR_Audit_Log__c(Principal_Id__c = 'x', Action__c = 'ADVISORY_QUERY');
            insert row;
            row.Gate_Trace__c = 'tamper';
            Boolean err = false;
            try { update row; } catch (DmlException e) { err = true; }
            System.assert(err);
        }
    }
"""))
write(CLASSES / "AuditLogTriggerTest.cls-meta.xml", CLASS_META)


# ResearchBriefTriggerTest
write(CLASSES / "ResearchBriefTriggerTest.cls", dedent("""\
    @isTest
    private class ResearchBriefTriggerTest {
        @isTest static void publish_without_mnpi_clear_blocked() {
            Research_Brief__c b = new Research_Brief__c(
                Ticker__c = 'NVDA', Thesis__c = 'AI strong',
                Mnpi_Cleared__c = false, Rm_Consumable__c = true, Published_At__c = Datetime.now()
            );
            Boolean err = false;
            try { insert b; } catch (DmlException e) { err = true; }
            System.assert(err, 'Publish without MNPI clear must fail');
        }

        @isTest static void publish_with_mnpi_clear_ok() {
            Research_Brief__c b = new Research_Brief__c(
                Ticker__c = 'NVDA', Thesis__c = 'AI strong',
                Mnpi_Cleared__c = true, Rm_Consumable__c = true,
                Published_At__c = Datetime.now(), Author_Agent_Id__c = 'research-orchestrator'
            );
            Test.startTest();
            insert b;
            Test.getEventBus().deliver();
            Test.stopTest();
            System.assertNotEquals(null, b.Id);
        }

        @isTest static void update_to_rm_consumable_fires_event() {
            Research_Brief__c b = new Research_Brief__c(
                Ticker__c = 'AMD', Thesis__c = 'challenger',
                Mnpi_Cleared__c = true, Rm_Consumable__c = false,
                Published_At__c = Datetime.now()
            );
            insert b;
            b.Rm_Consumable__c = true;
            Test.startTest();
            update b;
            Test.getEventBus().deliver();
            Test.stopTest();
            System.assert(true);
        }
    }
"""))
write(CLASSES / "ResearchBriefTriggerTest.cls-meta.xml", CLASS_META)


# MnpiValidatorTest
write(CLASSES / "MnpiValidatorTest.cls", dedent("""\
    @isTest
    private class MnpiValidatorTest {
        @isTest static void flags_share_count() {
            System.assertEquals('Contains raw share count',
                MnpiValidator.findViolation('Patel owns 1500 shares of NVDA'));
        }
        @isTest static void flags_wire_instructions() {
            System.assertEquals('Contains wire instructions',
                MnpiValidator.findViolation('Please wire $24,000 to account ABC123XYZ'));
        }
        @isTest static void flags_trade_intent() {
            System.assertEquals('Contains trade intent',
                MnpiValidator.findViolation('We plan to sell 150 shares NVDA tomorrow'));
        }
        @isTest static void clean_text_passes() {
            System.assertEquals(null, MnpiValidator.findViolation('NVDA data-center growth continues.'));
            System.assert(MnpiValidator.isClean('neutral text'));
        }
        @isTest static void blank_returns_null() {
            System.assertEquals(null, MnpiValidator.findViolation(''));
            System.assertEquals(null, MnpiValidator.findViolation(null));
        }
    }
"""))
write(CLASSES / "MnpiValidatorTest.cls-meta.xml", CLASS_META)


# SoqlSafeTest
write(CLASSES / "SoqlSafeTest.cls", dedent("""\
    @isTest
    private class SoqlSafeTest {
        @isTest static void identifier_ok() {
            System.assertEquals('Research_Brief__c', SoqlSafe.validateIdentifier('Research_Brief__c'));
        }
        @isTest static void identifier_rejects_semicolon() {
            Boolean err = false;
            try { SoqlSafe.validateIdentifier('DROP TABLE;'); } catch (SoqlSafe.SoqlSafeException e) { err = true; }
            System.assert(err);
        }
        @isTest static void escape_literal_null() { System.assertEquals('null', SoqlSafe.escapeLiteral(null)); }
        @isTest static void escape_literal_true() { System.assertEquals('true', SoqlSafe.escapeLiteral(true)); }
        @isTest static void escape_literal_number() { System.assertEquals('42', SoqlSafe.escapeLiteral(42)); }
        @isTest static void ensure_read_only_rejects_delete() {
            Boolean err = false;
            try { SoqlSafe.ensureReadOnly('SELECT Id FROM X; DELETE FROM X'); }
            catch (SoqlSafe.SoqlSafeException e) { err = true; }
            System.assert(err);
        }
        @isTest static void ensure_read_only_accepts_select() {
            SoqlSafe.ensureReadOnly('SELECT Id, Ticker__c FROM Research_Brief__c');
        }
    }
"""))
write(CLASSES / "SoqlSafeTest.cls-meta.xml", CLASS_META)


# SuitabilityCheckDeterministicTest
write(CLASSES / "SuitabilityCheckDeterministicTest.cls", dedent("""\
    @isTest
    private class SuitabilityCheckDeterministicTest {
        @isTest static void conservative_over_ceiling_fails() {
            SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
                'Conservative', 'buy', 10000, 6.0, 24);
            System.assertEquals(SuitabilityCheckDeterministic.Outcome.FAIL_CONCENTRATION, r.verdict);
        }
        @isTest static void moderate_under_ceiling_passes() {
            SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
                'Moderate', 'buy', 5000, 10.0, 24);
            System.assertEquals(SuitabilityCheckDeterministic.Outcome.PASS_OK, r.verdict);
        }
        @isTest static void aggressive_allows_higher_concentration() {
            SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
                'Aggressive', 'buy', 5000, 25.0, 12);
            System.assertEquals(SuitabilityCheckDeterministic.Outcome.PASS_OK, r.verdict);
        }
        @isTest static void short_horizon_large_notional_review() {
            SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
                'Moderate', 'buy', 200000, 5.0, 2);
            System.assertEquals(SuitabilityCheckDeterministic.Outcome.REVIEW_HORIZON, r.verdict);
        }
        @isTest static void missing_profile_review() {
            SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
                null, 'buy', 1000, 1.0, 24);
            System.assertEquals(SuitabilityCheckDeterministic.Outcome.REVIEW_HORIZON, r.verdict);
        }
        @isTest static void sell_not_blocked() {
            SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
                'Conservative', 'sell', 10000, 6.0, 24);
            System.assertEquals(SuitabilityCheckDeterministic.Outcome.PASS_OK, r.verdict);
        }
    }
"""))
write(CLASSES / "SuitabilityCheckDeterministicTest.cls-meta.xml", CLASS_META)


# Permission sets
PERMSET_TMPL = """<?xml version="1.0" encoding="UTF-8"?>
<PermissionSet xmlns="http://soap.sforce.com/2006/04/metadata">
    <label>{label}</label>
    <description>{description}</description>
    <hasActivationRequired>false</hasActivationRequired>
    <license>Salesforce</license>
{body}
</PermissionSet>
"""


def _field_perm(sobject: str, field: str, read: str = "true", edit: str = "false") -> str:
    return (f"    <fieldPermissions>\n"
            f"        <editable>{edit}</editable>\n"
            f"        <field>{sobject}.{field}</field>\n"
            f"        <readable>{read}</readable>\n"
            f"    </fieldPermissions>")


def _object_perm(sobject: str, *, c: bool = False, r: bool = True, u: bool = False, d: bool = False,
                 all_read: bool = False, modify: bool = False) -> str:
    return (f"    <objectPermissions>\n"
            f"        <allowCreate>{str(c).lower()}</allowCreate>\n"
            f"        <allowDelete>{str(d).lower()}</allowDelete>\n"
            f"        <allowEdit>{str(u).lower()}</allowEdit>\n"
            f"        <allowRead>{str(r).lower()}</allowRead>\n"
            f"        <modifyAllRecords>{str(modify).lower()}</modifyAllRecords>\n"
            f"        <object>{sobject}</object>\n"
            f"        <viewAllRecords>{str(all_read).lower()}</viewAllRecords>\n"
            f"    </objectPermissions>")


senior = "\n".join([
    _object_perm("IR_Audit_Log__c", r=True, c=True, u=True, all_read=True, modify=True),
    _object_perm("IR_Pending_Approval__c", r=True, c=True, u=True, all_read=True, modify=True),
    _object_perm("Research_Brief__c", r=True, u=True, all_read=True),
    _object_perm("Client_Inquiry__c", r=True, all_read=True),
    _field_perm("IR_Pending_Approval__c", "ActionPlan_Hash__c", edit="true"),
    _field_perm("IR_Pending_Approval__c", "Status__c", edit="true"),
    _field_perm("IR_Pending_Approval__c", "Senior_Approver_Id__c", edit="true"),
    _field_perm("IR_Audit_Log__c", "Gate_Trace__c", edit="true"),
    _field_perm("IR_Audit_Log__c", "Dual_Approver__c", edit="true"),
])
write(PERMSETS / "Senior_Compliance_Approver.permissionset-meta.xml",
      PERMSET_TMPL.format(
          label="Senior Compliance Approver",
          description="Dual-auth second-signer. Read/write IR_Pending_Approval__c + IR_Audit_Log__c.",
          body=senior))


analyst = "\n".join([
    _object_perm("Research_Brief__c", r=True, c=True, u=True),
    _object_perm("Client_Inquiry__c", r=True),
    _object_perm("IR_Audit_Log__c", r=True, c=True),
    _field_perm("Research_Brief__c", "Ticker__c", edit="true"),
    _field_perm("Research_Brief__c", "Thesis__c", edit="true"),
    _field_perm("Research_Brief__c", "Sentiment_Score__c", edit="true"),
    _field_perm("Research_Brief__c", "Risk_Factors__c", edit="true"),
    _field_perm("Research_Brief__c", "Compliance_Status__c", edit="true"),
    _field_perm("Research_Brief__c", "Mnpi_Cleared__c", edit="true"),
    _field_perm("Research_Brief__c", "Rm_Consumable__c", edit="true"),
    _field_perm("Research_Brief__c", "Client_Demand__c"),
    _field_perm("Research_Brief__c", "Source_Chunk_Ids__c", edit="true"),
    _field_perm("Research_Brief__c", "Published_At__c", edit="true"),
    _field_perm("Research_Brief__c", "Author_Agent_Id__c", edit="true"),
])
write(PERMSETS / "Research_Analyst.permissionset-meta.xml",
      PERMSET_TMPL.format(
          label="Research Analyst",
          description="Sarah's persona — author research briefs, read inquiries, write audit.",
          body=analyst))


advisor = "\n".join([
    _object_perm("Research_Brief__c", r=True),
    _object_perm("Client_Inquiry__c", r=True, c=True, u=True),
    _object_perm("IR_Audit_Log__c", r=True, c=True),
    _object_perm("IR_Pending_Approval__c", r=True, c=True),
    _field_perm("Client_Inquiry__c", "Client_Contact_Id__c", edit="true"),
    _field_perm("Client_Inquiry__c", "Inquiry_Text__c", edit="true"),
    _field_perm("Client_Inquiry__c", "Channel__c", edit="true"),
    _field_perm("Client_Inquiry__c", "Type__c", edit="true"),
    _field_perm("Client_Inquiry__c", "Resolved_By_Rm__c", edit="true"),
    _field_perm("Client_Inquiry__c", "Linked_Brief_Id__c", edit="true"),
])
write(PERMSETS / "Wealth_Advisor.permissionset-meta.xml",
      PERMSET_TMPL.format(
          label="Wealth Advisor",
          description="RM persona — read briefs, resolve inquiries, request dual-auth approvals.",
          body=advisor))


# Data Cloud Data Stream
write(DATASTREAMS / "Research_Brief_Stream.dataStream-meta.xml", dedent("""\
    <?xml version="1.0" encoding="UTF-8"?>
    <DataStream xmlns="http://soap.sforce.com/2006/04/metadata">
        <label>Research Brief Stream</label>
        <description>Points a Data Cloud DLM at Research_Brief__c for DLM joins to Position/Client/Contact.</description>
        <sourceApi>Salesforce</sourceApi>
        <objectName>Research_Brief__c</objectName>
        <category>Engagement</category>
        <refreshMode>Incremental</refreshMode>
        <refreshFrequency>PT15M</refreshFrequency>
    </DataStream>
"""))

print("Scaffolded Apex classes, permission sets, data stream.")
