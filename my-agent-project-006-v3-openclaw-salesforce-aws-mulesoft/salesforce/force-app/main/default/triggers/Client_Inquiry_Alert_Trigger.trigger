// After-insert trigger on Client_Inquiry__c.
// When Type__c = 'alert' AND Auto_Send_Eligible__c = true, publishes a
// Client_Alert_Auto_Send__e platform event carrying the Inquiry Id, Contact
// Id, and preferred channel. Consumed by the client-liaison subscriber.
//
// Bulkified: handles the full 200-record trigger chunk in one EventBus.publish
// call. Non-eligible inquiries (type != alert or eligible = false) are skipped
// entirely — no PE is emitted, no DML side-effects.
trigger Client_Inquiry_Alert_Trigger on Client_Inquiry__c (after insert) {
    List<Client_Alert_Auto_Send__e> events = new List<Client_Alert_Auto_Send__e>();
    for (Client_Inquiry__c row : Trigger.new) {
        if (row.Type__c != 'alert') { continue; }
        if (row.Auto_Send_Eligible__c != true) { continue; }
        events.add(new Client_Alert_Auto_Send__e(
            Inquiry_Id__c = row.Id,
            Contact_Id__c = row.Client_Contact_Id__c,
            Preferred_Channel__c = row.Channel__c,
            Correlation_Id__c = String.valueOf(System.currentTimeMillis()) + '-' + row.Id
        ));
    }
    if (!events.isEmpty()) {
        EventBus.publish(events);
    }
}
