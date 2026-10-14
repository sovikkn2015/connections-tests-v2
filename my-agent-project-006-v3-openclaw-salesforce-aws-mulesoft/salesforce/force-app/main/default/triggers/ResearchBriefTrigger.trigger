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
