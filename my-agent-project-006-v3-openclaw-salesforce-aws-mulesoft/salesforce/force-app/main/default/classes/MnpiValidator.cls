public with sharing class MnpiValidator {
    private static final Pattern SHARE_COUNT = Pattern.compile('(?i)\\b(?:holds?|owns?|position\\s*of)\\s+\\d{2,}\\s+shares?\\b');
    private static final Pattern WIRE_ACCT = Pattern.compile('(?i)wire\\s+\\$?[\\d,]+(?:\\.\\d+)?\\s+to\\s+(?:account\\s+)?[A-Z0-9]{6,}');
    private static final Pattern TRADE_INTENT = Pattern.compile('(?i)\\b(?:buy|sell)\\s+\\d+\\s+(?:shares?|contracts?)\\s+(?:of\\s+)?[A-Z]{1,5}\\b');

    public static String findViolation(String text) {
        if (String.isBlank(text)) { return null; }
        if (SHARE_COUNT.matcher(text).find()) { return 'Contains raw share count'; }
        if (WIRE_ACCT.matcher(text).find()) { return 'Contains wire instructions'; }
        if (TRADE_INTENT.matcher(text).find()) { return 'Contains trade intent'; }
        return null;
    }

    public static Boolean isClean(String text) { return findViolation(text) == null; }
}
