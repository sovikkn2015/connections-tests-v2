// Publish all draft Knowledge articles
// Run: sf apex run --file scripts/apex/publish-knowledge-articles.apex

List<Knowledge__kav> drafts = [
    SELECT Id, KnowledgeArticleId, Title
    FROM Knowledge__kav
    WHERE PublishStatus = 'Draft'
    AND Language = 'en_US'
];

Integer published = 0;
for (Knowledge__kav art : drafts) {
    try {
        KbManagement.PublishingService.publishArticle(art.KnowledgeArticleId, true);
        published++;
        System.debug('Published: ' + art.Title);
    } catch (Exception e) {
        System.debug('Failed to publish "' + art.Title + '": ' + e.getMessage());
    }
}

System.debug('Published ' + published + ' of ' + drafts.size() + ' draft articles.');
