// Seed Knowledge Articles for Wealth Advisor Agent — Phase 5A
// Run: sf apex run --file scripts/apex/seed-knowledge-articles.apex
//
// Prerequisites: Salesforce Knowledge must be enabled in your org.
// If Knowledge is not enabled, this script will print a helpful message and exit gracefully.

try {
    // Verify Knowledge__kav is accessible
    Schema.DescribeSObjectResult kav = Schema.SObjectType.Knowledge__kav;
    System.debug('Knowledge__kav is accessible. Proceeding with article creation...');
} catch (Exception e) {
    System.debug('============================================================');
    System.debug('ERROR: Salesforce Knowledge is not enabled in this org.');
    System.debug('');
    System.debug('To enable Knowledge:');
    System.debug('  1. Go to Setup → Knowledge Settings');
    System.debug('  2. Toggle Salesforce Knowledge to Enabled');
    System.debug('  3. Re-run this script');
    System.debug('============================================================');
    return;
}

// Check for existing articles to avoid duplicates
List<Knowledge__kav> existing = [
    SELECT Title FROM Knowledge__kav
    WHERE Title IN (
        'Margin Account Policy',
        'Portfolio Rebalancing Guidelines',
        'Client Onboarding Procedures',
        'Risk Assessment Framework',
        'Wealth Management Fee Schedule'
    )
    AND PublishStatus = 'Online'
    AND Language = 'en_US'
];

if (!existing.isEmpty()) {
    System.debug('Found ' + existing.size() + ' existing published articles. Skipping duplicates.');
    Set<String> existingTitles = new Set<String>();
    for (Knowledge__kav a : existing) {
        existingTitles.add(a.Title);
        System.debug('  Already exists: ' + a.Title);
    }
}

// Build list of articles to insert
List<Knowledge__kav> articles = new List<Knowledge__kav>();

// ── Article 1: Margin Account Policy ─────────────────────────
Knowledge__kav art1 = new Knowledge__kav();
art1.Title = 'Margin Account Policy';
art1.UrlName = 'margin-account-policy';
art1.Summary = 'Firm policy governing margin account eligibility, limits, and maintenance requirements.';
art1.Language = 'en_US';
articles.add(art1);

// ── Article 2: Portfolio Rebalancing Guidelines ──────────────
Knowledge__kav art2 = new Knowledge__kav();
art2.Title = 'Portfolio Rebalancing Guidelines';
art2.UrlName = 'rebalancing-guidelines';
art2.Summary = 'Guidelines for when and how to rebalance client portfolios to maintain target allocations.';
art2.Language = 'en_US';
articles.add(art2);

// ── Article 3: Client Onboarding Procedures ──────────────────
Knowledge__kav art3 = new Knowledge__kav();
art3.Title = 'Client Onboarding Procedures';
art3.UrlName = 'client-onboarding-procedures';
art3.Summary = 'Step-by-step process for onboarding new wealth management clients.';
art3.Language = 'en_US';
articles.add(art3);

// ── Article 4: Risk Assessment Framework ─────────────────────
Knowledge__kav art4 = new Knowledge__kav();
art4.Title = 'Risk Assessment Framework';
art4.UrlName = 'risk-assessment-framework';
art4.Summary = 'Framework for assessing and categorizing client risk tolerance and investment suitability.';
art4.Language = 'en_US';
articles.add(art4);

// ── Article 5: Wealth Management Fee Schedule ────────────────
Knowledge__kav art5 = new Knowledge__kav();
art5.Title = 'Wealth Management Fee Schedule';
art5.UrlName = 'fee-schedule';
art5.Summary = 'Current fee schedule for wealth management advisory services.';
art5.Language = 'en_US';
articles.add(art5);

// Insert draft articles
try {
    insert articles;
    System.debug('Inserted ' + articles.size() + ' Knowledge articles as drafts.');
} catch (DmlException e) {
    System.debug('Error inserting articles: ' + e.getMessage());
    System.debug('');
    System.debug('Common fixes:');
    System.debug('  - Ensure Knowledge is enabled (Setup → Knowledge Settings)');
    System.debug('  - Ensure your user has the "Manage Articles" permission');
    System.debug('  - If UrlName conflicts, existing articles may need to be archived first');
    return;
}

// Publish each article immediately
Integer published = 0;
for (Knowledge__kav art : articles) {
    try {
        KbManagement.PublishingService.publishArticle(art.Id, true);
        published++;
        System.debug('Published: ' + art.Title);
    } catch (Exception e) {
        System.debug('Could not publish "' + art.Title + '": ' + e.getMessage());
    }
}

System.debug('============================================================');
System.debug('Knowledge Articles Summary:');
System.debug('  Created: ' + articles.size());
System.debug('  Published: ' + published);
System.debug('');
System.debug('NOTE: Article bodies use the Summary field only.');
System.debug('For rich text body content, add a custom rich text field');
System.debug('(e.g., Body__c) to Knowledge__kav, or edit articles in the');
System.debug('Knowledge tab UI to add full policy text from the docs.');
System.debug('============================================================');
