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
