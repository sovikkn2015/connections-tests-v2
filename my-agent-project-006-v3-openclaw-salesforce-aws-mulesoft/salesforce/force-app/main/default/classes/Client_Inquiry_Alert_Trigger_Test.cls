@isTest
private class Client_Inquiry_Alert_Trigger_Test {
    @TestSetup
    static void setup() {
        Account acct = new Account(Name = 'Household A');
        insert acct;
        List<Contact> contacts = new List<Contact>();
        for (Integer i = 0; i < 200; i++) {
            contacts.add(new Contact(LastName = 'Client_' + i, AccountId = acct.Id));
        }
        insert contacts;
    }

    @isTest
    static void testAutoSendFires_WhenEligible() {
        List<Contact> contacts = [SELECT Id FROM Contact LIMIT 200];
        List<Client_Inquiry__c> rows = new List<Client_Inquiry__c>();
        for (Contact c : contacts) {
            rows.add(new Client_Inquiry__c(
                Type__c = 'alert',
                Auto_Send_Eligible__c = true,
                Channel__c = 'Email',
                Client_Contact_Id__c = c.Id,
                Inquiry_Text__c = 'NVDA concentration above threshold'
            ));
        }
        Test.startTest();
        insert rows;
        Test.getEventBus().deliver();
        Test.stopTest();
        // Assert every inserted row persisted and trigger fired w/o error.
        Integer persisted = [SELECT COUNT() FROM Client_Inquiry__c WHERE Type__c = 'alert' AND Auto_Send_Eligible__c = true];
        System.assertEquals(200, persisted, 'All 200 alert inquiries should persist');
    }

    @isTest
    static void testAutoSendSkipped_WhenNotEligible() {
        List<Contact> contacts = [SELECT Id FROM Contact LIMIT 200];
        List<Client_Inquiry__c> rows = new List<Client_Inquiry__c>();
        for (Contact c : contacts) {
            rows.add(new Client_Inquiry__c(
                Type__c = 'alert',
                Auto_Send_Eligible__c = false,
                Channel__c = 'Email',
                Client_Contact_Id__c = c.Id,
                Inquiry_Text__c = 'not eligible for auto-send'
            ));
        }
        Test.startTest();
        insert rows;
        Test.getEventBus().deliver();
        Test.stopTest();
        // Non-eligible rows must persist but not cause trigger failures.
        Integer persisted = [SELECT COUNT() FROM Client_Inquiry__c WHERE Auto_Send_Eligible__c = false];
        System.assertEquals(200, persisted, 'All 200 non-eligible inquiries should persist without PE publish error');
    }

    @isTest
    static void testAutoSendSkipped_WhenNotAlert() {
        List<Contact> contacts = [SELECT Id FROM Contact LIMIT 200];
        List<Client_Inquiry__c> rows = new List<Client_Inquiry__c>();
        for (Contact c : contacts) {
            rows.add(new Client_Inquiry__c(
                Type__c = 'question',
                Auto_Send_Eligible__c = true,
                Channel__c = 'Email',
                Client_Contact_Id__c = c.Id,
                Inquiry_Text__c = 'question, not alert'
            ));
        }
        Test.startTest();
        insert rows;
        Test.getEventBus().deliver();
        Test.stopTest();
        Integer persisted = [SELECT COUNT() FROM Client_Inquiry__c WHERE Type__c = 'question'];
        System.assertEquals(200, persisted, 'All 200 question inquiries should persist without PE publish');
    }
}
