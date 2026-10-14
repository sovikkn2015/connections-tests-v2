# Gap Analysis: 004 V1 → V2

## Summary

After thorough verification against the live org, the actual gaps are fewer but more specific than initially assessed. The agent script already has 12 topics, audit logging is wired into all actions, and market data works. The real gaps are organizational, documentation, and a few specific code issues.

## VERIFIED Gaps (Confirmed Against Live Org)

### GAP-1: WA_WorkbenchController Not in grant-permissions.apex
- **Status**: CONFIRMED
- **Impact**: VF Workbench page may fail for non-admin users
- **Fix**: Add `WA_WorkbenchController` to the grant-permissions script

### GAP-2: VF Workbench and React Frontend Not Documented in README
- **Status**: CONFIRMED
- **Impact**: New users don't know about `/apex/WA_Workbench` or the React frontend
- **Fix**: Add sections to README

### GAP-3: Experience Cloud Chat Widget Not Rendering
- **Status**: CONFIRMED
- **Workaround**: VF Workbench at `/apex/WA_Workbench` works as primary UI

### GAP-4: Knowledge Articles — Draft Status (UI-only fix)
### GAP-5: Data Cloud Streams Missing (UI-only fix)
### GAP-6: Stale esw-retrieve/ Directory
### GAP-7: No V1/V2 Folder Organization — FIXED
### GAP-8: RBAC Not Enforced — intentional for dev
### GAP-9: Performance Tests Not Executed
### GAP-10: LLM-as-Judge Not Executed

## CORRECTED (Initially Wrong)
- Agent script already has 12 topics including market_data and market_news ✅
- All 8 DC_* classes already call audit logging ✅
- 5 audit log records confirmed in org ✅

## V2 Actions: P0=code fixes, P1=doc updates, P2/P3=manual/future
