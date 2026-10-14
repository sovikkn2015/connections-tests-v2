// Check Experience Cloud site (Network) configuration
List<Network> networks = [SELECT Id, Name, Status, UrlPathPrefix FROM Network];
for (Network n : networks) {
    System.debug('Network: ' + n.Name + ' | Status: ' + n.Status + ' | Path: ' + n.UrlPathPrefix);
}
System.debug('Total Network records: ' + networks.size());
