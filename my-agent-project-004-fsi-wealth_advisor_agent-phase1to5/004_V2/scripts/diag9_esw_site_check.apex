// Check the Site records to see which sites exist and their status
List<Site> sites = [SELECT Id, Name, MasterLabel, Status, SiteType, UrlPathPrefix, Subdomain FROM Site];
for (Site s : sites) {
    System.debug('Site: ' + s.MasterLabel + ' | Name: ' + s.Name + ' | Status: ' + s.Status + ' | Type: ' + s.SiteType + ' | Path: ' + s.UrlPathPrefix + ' | Subdomain: ' + s.Subdomain);
}
System.debug('Total Site records: ' + sites.size());
