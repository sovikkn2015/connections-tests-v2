# Phase 5C: Role-Based Access Control — Implementation Guide

## Overview

This guide covers implementing sharing rules, permission sets, and advisor-to-client assignment models so the WA_P1to5_Advisor agent respects data boundaries. Each advisor should only see their own clients' data when interacting with the agent.

**Key Principle:** The agent runs as the Einstein Agent User, but sharing rules and FLS (Field-Level Security) are enforced based on the requesting user's profile. All Apex classes use `with sharing` to respect these boundaries.

---

## Architecture: How Agent Respects Sharing

```
┌──────────────────────────────────────────────────────────────────┐
│  Advisor: Sarah Thompson                                         │
│  Profile: Wealth Advisor                                         │
│  Assigned Clients: Johnson, Chen households                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Agent Query: "Tell me about the Patel household"         │   │
│  │                                                           │   │
│  │  WA_P1to5_Advisor                                         │   │
│  │    → DC_ClientLookupAction (with sharing)                 │   │
│  │    → Queries Data Cloud as Sarah Thompson                 │   │
│  │    → Sharing rules: Sarah can't see Patel data            │   │
│  │    → Result: "No client found matching Patel"             │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  Agent Query: "Tell me about the Johnson household"       │   │
│  │                                                           │   │
│  │  WA_P1to5_Advisor                                         │   │
│  │    → DC_ClientLookupAction (with sharing)                 │   │
│  │    → Queries Data Cloud as Sarah Thompson                 │   │
│  │    → Sharing rules: Sarah owns Johnson data ✓             │   │
│  │    → Result: "Johnson Family | AUM: $2.8M | ..."          │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────┘
```

## Step 1: Advisor-to-Client Assignment Model

The `WA_Household__c.Advisor__c` field stores the assigned advisor name. For proper sharing, this should be converted to a lookup to the User object:

### Option A: OWD + Sharing Rules (Recommended)

1. **Set Organization-Wide Defaults (OWD):**
   - **Setup → Sharing Settings**
   - Set these objects to **Private**:
     - `WA_Household__c` → Private
     - `WA_Client__c` → Controlled by Parent (parent = WA_Household__c)
     - `WA_Financial_Account__c` → Controlled by Parent
     - `WA_Financial_Goal__c` → Controlled by Parent
     - `WA_Meeting__c` → Controlled by Parent

2. **Add Owner field to WA_Household__c:**
   - The standard `OwnerId` field on WA_Household__c should be set to the advisor's Salesforce User Id
   - When seeding data, set `OwnerId` to the advisor user:
     ```apex
     WA_Household__c hh = new WA_Household__c();
     hh.Name = 'Johnson Family';
     hh.OwnerId = sarahThompsonUserId;  // Advisor who owns this household
     ```

3. **Create Sharing Rules for team access:**
   - **Setup → Sharing Settings → WA_Household__c → New Rule**
   - Rule: Share households owned by "Wealth Advisor Team" role with "Compliance Team" role (Read Only)
   - This lets compliance officers view all client data without owning it

### Option B: Criteria-Based Sharing Rules

If you can't use record ownership (e.g., the Einstein Agent User needs to own records):

1. Add a custom field: `Advisor_User__c` (Lookup to User) on `WA_Household__c`
2. Create criteria-based sharing rules:
   - **Rule Name:** Advisor Sees Own Households
   - **Criteria:** `Advisor_User__c` equals `$CurrentUser.Id`
   - **Share With:** Record owner
   - **Access Level:** Read/Write

## Step 2: Create Permission Sets

### Permission Set: WA_Advisor

```
Name: WA_Advisor
Label: Wealth Advisor Agent Access
Description: Grants advisors access to wealth management objects and agent actions
```

**Object Permissions:**

| Object | Read | Create | Edit | Delete |
|--------|------|--------|------|--------|
| WA_Household__c | ✅ | ❌ | ❌ | ❌ |
| WA_Client__c | ✅ | ❌ | ❌ | ❌ |
| WA_Financial_Account__c | ✅ | ❌ | ❌ | ❌ |
| WA_Financial_Goal__c | ✅ | ❌ | ❌ | ❌ |
| WA_Meeting__c | ✅ | ✅ | ✅ | ❌ |
| WA_Audit_Log__c | ✅ | ✅ | ❌ | ❌ |

**Field-Level Security:** All fields on above objects → Visible (Read)

**Apex Class Access:**
- DC_ClientLookupAction
- DC_PortfolioReviewAction
- DC_GoalPlanningAction
- DC_MeetingPrepAction
- DC_AuditLogAction

### Permission Set: WA_Compliance_Officer

```
Name: WA_Compliance_Officer
Label: Wealth Advisor Compliance Access
Description: Grants compliance officers read access to all client data and audit logs
```

**Object Permissions:**

| Object | Read | Create | Edit | Delete |
|--------|------|--------|------|--------|
| WA_Household__c | ✅ | ❌ | ❌ | ❌ |
| WA_Client__c | ✅ | ❌ | ❌ | ❌ |
| WA_Financial_Account__c | ✅ | ❌ | ❌ | ❌ |
| WA_Financial_Goal__c | ✅ | ❌ | ❌ | ❌ |
| WA_Meeting__c | ✅ | ❌ | ❌ | ❌ |
| WA_Audit_Log__c | ✅ | ❌ | ❌ | ❌ |

### Permission Set: WA_Admin

```
Name: WA_Admin
Label: Wealth Advisor Admin Access
Description: Full access to all WA objects, agent configuration, and audit logs
```

**Object Permissions:** Full CRUD on all WA_* objects

## Step 3: Grant Permission Sets via Script

Create a script to assign permission sets programmatically:

```apex
// scripts/apex/grant-rbac-permissions.apex

// Get permission set IDs
PermissionSet advisorPS = [SELECT Id FROM PermissionSet WHERE Name = 'WA_Advisor' LIMIT 1];
PermissionSet compliancePS = [SELECT Id FROM PermissionSet WHERE Name = 'WA_Compliance_Officer' LIMIT 1];

// Assign to advisor users
List<User> advisors = [SELECT Id FROM User WHERE Profile.Name = 'Wealth Advisor' AND IsActive = true];
List<PermissionSetAssignment> assignments = new List<PermissionSetAssignment>();
for (User u : advisors) {
    assignments.add(new PermissionSetAssignment(AssigneeId = u.Id, PermissionSetId = advisorPS.Id));
}

// Assign to compliance users
List<User> complianceUsers = [SELECT Id FROM User WHERE Profile.Name = 'Compliance Officer' AND IsActive = true];
for (User u : complianceUsers) {
    assignments.add(new PermissionSetAssignment(AssigneeId = u.Id, PermissionSetId = compliancePS.Id));
}

insert assignments;
System.debug('Assigned ' + assignments.size() + ' permission set assignments');
```

## Step 4: Verify Agent Respects Sharing

### Test Scenario

| Advisor | Assigned Households | Query | Expected Result |
|---------|-------------------|-------|-----------------|
| Sarah Thompson | Johnson, Chen | "Tell me about Johnson" | ✅ Returns Johnson data |
| Sarah Thompson | Johnson, Chen | "Tell me about Patel" | ❌ "No client found" |
| Mike Rodriguez | Martinez, Williams | "Tell me about Martinez" | ✅ Returns Martinez data |
| Mike Rodriguez | Martinez, Williams | "Tell me about Chen" | ❌ "No client found" |
| Compliance Officer | (all via sharing rule) | "Tell me about Patel" | ✅ Returns Patel data (read-only) |

### Verification Script

```apex
// Run as a specific advisor to verify sharing
System.runAs(sarahThompsonUser) {
    DC_ClientLookupAction.LookupInput input = new DC_ClientLookupAction.LookupInput();
    input.clientName = 'Patel';
    List<DC_ClientLookupAction.LookupOutput> results = DC_ClientLookupAction.getClient360(
        new List<DC_ClientLookupAction.LookupInput>{ input }
    );
    System.assert(results[0].clientSummary.contains('No client'), 
        'Sarah should NOT see Patel data');
}
```

## Step 5: Data Cloud Sharing Considerations

**Important:** Data Cloud (CdpQuery) does not natively enforce Salesforce sharing rules. The `ConnectApi.CdpQuery.queryAnsiSqlV2()` method runs with system-level access.

To enforce sharing in the Data Cloud path:

### Approach 1: Pre-filter in Apex (Recommended)

Before querying Data Cloud, verify the user has access to the household in CRM:

```apex
// In DC_ClientLookupAction, add this check before CdpQuery:
List<WA_Household__c> accessible = [
    SELECT Id, Name FROM WA_Household__c 
    WHERE Name LIKE :('%' + cleanName + '%')
    WITH SECURITY_ENFORCED
    LIMIT 1
];
if (accessible.isEmpty()) {
    output.clientSummary = 'No client or household found matching "' + input.clientName + '".';
    // User doesn't have access — don't query Data Cloud
    return;
}
// User has access — proceed with CdpQuery
```

### Approach 2: Row-Level Security in Data Cloud

1. **Data Cloud → Security → Row-Level Security Policies**
2. Create a policy on each WA_*__dlm object
3. Filter: `Advisor_c__c = $CurrentUser.Name` (or use a user ID mapping)
4. This enforces sharing at the Data Cloud query level

### Approach 3: Hybrid

Use Approach 1 for the initial access check, then query Data Cloud for the enriched data. This gives you CRM-level sharing enforcement with Data Cloud's richer query capabilities.

## Step 6: Audit Log Integration

All access attempts (successful and denied) should be logged:

```apex
// Log successful access
DC_AuditLogAction.logInteraction(
    'WA_P1to5_Advisor',
    'client_lookup',
    'DC_ClientLookupAction',
    input.clientName,
    output.clientSummary,
    householdName
);

// Log denied access
DC_AuditLogAction.logInteraction(
    'WA_P1to5_Advisor',
    'client_lookup',
    'DC_ClientLookupAction — ACCESS DENIED',
    input.clientName,
    'User does not have access to this household',
    input.clientName
);
```

---

## Summary: RBAC Configuration Checklist

- [ ] Set OWD to Private for WA_Household__c
- [ ] Set child objects to Controlled by Parent
- [ ] Set WA_Household__c.OwnerId to the assigned advisor
- [ ] Create sharing rule: Advisors → Compliance (Read Only)
- [ ] Create permission set: WA_Advisor
- [ ] Create permission set: WA_Compliance_Officer
- [ ] Create permission set: WA_Admin
- [ ] Assign permission sets to users
- [ ] Add CRM pre-filter to DC_* Apex classes (for Data Cloud sharing)
- [ ] Add audit logging for access attempts
- [ ] Test with multiple advisor profiles
- [ ] Verify denied access returns "No client found" (not an error)
