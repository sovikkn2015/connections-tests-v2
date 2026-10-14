public with sharing class DC_TransactionHistoryAction {

    public class TxnInput {
        @InvocableVariable(label='Client Name' description='Name of the client to get transaction history for' required=true)
        public String clientName;
    }

    public class TxnOutput {
        @InvocableVariable(label='Transaction History' description='Recent transactions with summary totals from Data Cloud')
        public String transactionHistory;
    }

    @InvocableMethod(
        label='Get Transaction History (Data Cloud)'
        description='Returns recent transactions for a client from Data Cloud including buys, sells, dividends, and fees'
    )
    public static List<TxnOutput> getTransactionHistory(List<TxnInput> inputs) {
        List<TxnOutput> outputs = new List<TxnOutput>();

        for (TxnInput input : inputs) {
            TxnOutput output = new TxnOutput();
            try {
                String cleanName = cleanClientName(input.clientName);

                // Find client
                ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
                cq.sql = 'SELECT Id__c, Name__c FROM WA_Client_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);

                if ((cr.data == null || cr.data.isEmpty()) && cleanName.contains(' ')) {
                    for (String part : cleanName.split('\\s+')) {
                        if (part.length() < 2) continue;
                        cq.sql = 'SELECT Id__c, Name__c FROM WA_Client_c_Home__dlm ' +
                            'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(part) + '%\' LIMIT 1';
                        cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);
                        if (cr.data != null && !cr.data.isEmpty()) break;
                    }
                }

                if (cr.data == null || cr.data.isEmpty()) {
                    output.transactionHistory = 'No client found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                String clientId = safeStr(cr.data[0].rowData[0]);
                String clientName2 = safeStr(cr.data[0].rowData[1]);

                // Get transactions ordered by date desc, limit 10
                ConnectApi.CdpQueryInput tq = new ConnectApi.CdpQueryInput();
                tq.sql = 'SELECT Name__c, Type_c__c, Amount_c__c, Date_c__c, Symbol_c__c, Description_c__c ' +
                    'FROM WA_Transaction_c_Home__dlm ' +
                    'WHERE Client_c__c = \'' + String.escapeSingleQuotes(clientId) + '\' ' +
                    'ORDER BY Date_c__c DESC LIMIT 10';
                ConnectApi.CdpQueryOutputV2 tr = ConnectApi.CdpQuery.queryAnsiSqlV2(tq);

                if (tr.data == null || tr.data.isEmpty()) {
                    output.transactionHistory = 'No transactions found for "' + clientName2 + '".';
                    outputs.add(output);
                    continue;
                }

                String history = 'Transaction History: ' + clientName2
                    + '\nShowing last ' + tr.data.size() + ' transactions:';

                Decimal totalBuys = 0, totalSells = 0, totalDividends = 0, totalFees = 0;

                for (ConnectApi.CdpQueryV2Row row : tr.data) {
                    String txnType = safeStr(row.rowData[1]);
                    Decimal amount = row.rowData[2] != null ? Decimal.valueOf(String.valueOf(row.rowData[2])) : 0;
                    String txnDate = safeStr(row.rowData[3]);
                    String symbol = safeStr(row.rowData[4]);
                    String txnDesc = safeStr(row.rowData[5]);

                    history += '\n\n  ' + txnDate + ' | ' + txnType + ' | $' + formatCurrency(amount);
                    if (symbol != null && symbol != 'N/A') history += ' | ' + symbol;
                    if (txnDesc != null && txnDesc != 'N/A') history += '\n    ' + txnDesc;

                    if (txnType == 'Buy') totalBuys += amount;
                    else if (txnType == 'Sell') totalSells += amount;
                    else if (txnType == 'Dividend') totalDividends += amount;
                    else if (txnType == 'Fee') totalFees += amount;
                }

                history += '\n\n=== SUMMARY ==='
                    + '\nTotal Buys: $' + formatCurrency(totalBuys)
                    + '\nTotal Sells: $' + formatCurrency(totalSells)
                    + '\nTotal Dividends: $' + formatCurrency(totalDividends)
                    + '\nTotal Fees: $' + formatCurrency(totalFees)
                    + '\nNet Activity: $' + formatCurrency(totalSells + totalDividends - totalBuys - totalFees);

                output.transactionHistory = history;
            } catch (Exception e) {
                output.transactionHistory = 'I was unable to retrieve transaction history. Please try again or check the client name.';
            }

            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                DC_AuditLogAction.logInteraction(
                    'WA_P1to5_Advisor',
                    'transaction_history',
                    'get_transactions',
                    inputs[i].clientName,
                    outputs[i].transactionHistory,
                    inputs[i].clientName
                );
            } catch (Exception auditEx) {
                // Don't fail the action if audit logging fails
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        return outputs;
    }

    private static String cleanClientName(String raw) {
        String rawName = raw != null ? raw.trim() : '';
        String cleanName = rawName
            .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|rebalancing|transactions?|compliance|referral|history|check|alert|recent|meeting|prep)\\s*', ' ')
            .replaceAll('(?i)s$', '')
            .trim();
        if (String.isBlank(cleanName)) cleanName = rawName;
        return cleanName;
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }

    private static String formatCurrency(Object value) {
        if (value == null) return '0';
        try {
            Decimal d = Decimal.valueOf(String.valueOf(value));
            if (d >= 1000000) return String.valueOf((d / 1000000).setScale(1)) + 'M';
            if (d >= 1000) return String.valueOf((d / 1000).setScale(0)) + 'K';
            return String.valueOf(d.setScale(2));
        } catch (Exception e) {
            return '0';
        }
    }
}
