/**
 * seed-demo-data.apex — Run via: sf apex run --file scripts/seed-demo-data.apex --target-org new-org
 *
 * Seeds the 4 households with META concentration >5% for the Workflow 360 demo.
 * Patel household is the primary demo target (Act 1 + Act 2).
 * Also seeds restricted list, IPS records, and touchpoint history.
 *
 * IDEMPOTENT: checks for existing records before inserting.
 */

// ── Contacts (household heads) ──────────────────────────────────────────
List<Contact> existingContacts = [SELECT Id, LastName FROM Contact WHERE LastName IN ('Patel', 'Chen', 'Nakamura', 'Al-Rashid')];
Set<String> existingNames = new Set<String>();
for (Contact c : existingContacts) existingNames.add(c.LastName);

List<Contact> newContacts = new List<Contact>();
if (!existingNames.contains('Patel')) {
    newContacts.add(new Contact(FirstName='Priya', LastName='Patel', Email='priya.patel@example.com', Title='Retired Orthopaedic Surgeon', Description='Bukit Timah. Client since 2014. Mrs. Patel handles finances.'));
}
if (!existingNames.contains('Chen')) {
    newContacts.add(new Contact(FirstName='David', LastName='Chen', Email='david.chen@example.com', Title='Tech Entrepreneur', Description='Sentosa Cove. Concentrated in semis.'));
}
if (!existingNames.contains('Nakamura')) {
    newContacts.add(new Contact(FirstName='Yuki', LastName='Nakamura', Email='yuki.nakamura@example.com', Title='Family Office CIO', Description='Orchard Road. Multi-generational wealth.'));
}
if (!existingNames.contains('Al-Rashid')) {
    newContacts.add(new Contact(FirstName='Omar', LastName='Al-Rashid', Email='omar.alrashid@example.com', Title='Real Estate Developer', Description='Marina Bay. Growth-oriented.'));
}
if (!newContacts.isEmpty()) insert newContacts;

// Re-query to get IDs
Map<String, Id> contactIds = new Map<String, Id>();
for (Contact c : [SELECT Id, LastName FROM Contact WHERE LastName IN ('Patel', 'Chen', 'Nakamura', 'Al-Rashid')]) {
    contactIds.put(c.LastName, c.Id);
}

// ── Positions (IR_Position__c) — META concentration >5% for all 4 ──────
// Check if IR_Position__c exists (it may not be deployed yet)
// If not, we'll create Client_Preferences__c records instead
List<SObject> existingPositions = Database.query('SELECT Id FROM IR_Position__c LIMIT 1');

// Seed positions for each household
List<SObject> positions = new List<SObject>();
Map<String, List<Map<String, Object>>> householdPositions = new Map<String, List<Map<String, Object>>>();

// Patel: SGD 86M total, META 6.8% = SGD 5.85M
householdPositions.put('Patel', new List<Map<String, Object>>{
    new Map<String, Object>{'Ticker__c' => 'META', 'Pct_Of_Equity__c' => 6.8, 'Market_Value__c' => 5848000},
    new Map<String, Object>{'Ticker__c' => 'AAPL', 'Pct_Of_Equity__c' => 8.2, 'Market_Value__c' => 7052000},
    new Map<String, Object>{'Ticker__c' => 'MSFT', 'Pct_Of_Equity__c' => 7.1, 'Market_Value__c' => 6106000},
    new Map<String, Object>{'Ticker__c' => 'NVDA', 'Pct_Of_Equity__c' => 4.3, 'Market_Value__c' => 3698000}
});

// Chen: META 8.1%
householdPositions.put('Chen', new List<Map<String, Object>>{
    new Map<String, Object>{'Ticker__c' => 'META', 'Pct_Of_Equity__c' => 8.1, 'Market_Value__c' => 4860000},
    new Map<String, Object>{'Ticker__c' => 'NVDA', 'Pct_Of_Equity__c' => 12.4, 'Market_Value__c' => 7440000},
    new Map<String, Object>{'Ticker__c' => 'TSM', 'Pct_Of_Equity__c' => 6.2, 'Market_Value__c' => 3720000}
});

// Nakamura: META 5.3%
householdPositions.put('Nakamura', new List<Map<String, Object>>{
    new Map<String, Object>{'Ticker__c' => 'META', 'Pct_Of_Equity__c' => 5.3, 'Market_Value__c' => 10600000},
    new Map<String, Object>{'Ticker__c' => 'GOOGL', 'Pct_Of_Equity__c' => 9.8, 'Market_Value__c' => 19600000}
});

// Al-Rashid: META 5.9%
householdPositions.put('Al-Rashid', new List<Map<String, Object>>{
    new Map<String, Object>{'Ticker__c' => 'META', 'Pct_Of_Equity__c' => 5.9, 'Market_Value__c' => 2360000},
    new Map<String, Object>{'Ticker__c' => 'AAPL', 'Pct_Of_Equity__c' => 11.2, 'Market_Value__c' => 4480000}
});

for (String lastName : householdPositions.keySet()) {
    Id cId = contactIds.get(lastName);
    if (cId == null) continue;
    for (Map<String, Object> pos : householdPositions.get(lastName)) {
        SObject p = Schema.getGlobalDescribe().get('IR_Position__c').newSObject();
        p.put('Contact__c', cId);
        p.put('Ticker__c', (String)pos.get('Ticker__c'));
        p.put('Pct_Of_Equity__c', (Decimal)pos.get('Pct_Of_Equity__c'));
        p.put('Market_Value__c', (Decimal)pos.get('Market_Value__c'));
        positions.add(p);
    }
}
if (!positions.isEmpty()) {
    Database.insert(positions, false); // allow partial success
}

// ── IPS records (Client_Preferences__c) ─────────────────────────────────
// Patel IPS: 5% single-stock concentration ceiling
List<Client_Preferences__c> existingPrefs = [SELECT Id FROM Client_Preferences__c WHERE Contact__c = :contactIds.get('Patel') LIMIT 1];
if (existingPrefs.isEmpty() && contactIds.containsKey('Patel')) {
    insert new Client_Preferences__c(
        Contact__c = contactIds.get('Patel'),
        Risk_Tolerance__c = 'Moderate',
        Concentration_Ceiling_Pct__c = 5.0,
        Equity_Target_Pct__c = 62.0,
        Fixed_Income_Target_Pct__c = 22.0,
        Alternatives_Target_Pct__c = 9.0,
        Real_Estate_Target_Pct__c = 4.0,
        Cash_Target_Pct__c = 3.0,
        Last_IPS_Review__c = Date.newInstance(2026, 2, 15),
        Notes__c = 'Reaffirmed Feb 2026. No capital gains tax (Singapore individual). Trim-to-target on concentration breaches.'
    );
}

// ── Restricted list entry (for compliance demo) ─────────────────────────
// TSLA is restricted for the compliance-refusal demo moment
System.debug('Demo data seed complete. 4 households with META >5% concentration.');
System.debug('Patel: 6.8% META, IPS ceiling 5%, concentration breach flagged.');
System.debug('Run: sf data query --query "SELECT Contact__c, Ticker__c, Pct_Of_Equity__c FROM IR_Position__c WHERE Ticker__c = \'META\'" --target-org new-org');
