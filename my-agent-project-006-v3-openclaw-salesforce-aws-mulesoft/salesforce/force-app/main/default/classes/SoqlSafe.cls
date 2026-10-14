public with sharing class SoqlSafe {
    public class SoqlSafeException extends Exception {}

    private static final Pattern IDENTIFIER = Pattern.compile('^[A-Za-z][A-Za-z0-9_]{0,78}[A-Za-z0-9]$|^[A-Za-z]$');

    public static String validateIdentifier(String name) {
        if (name == null || !IDENTIFIER.matcher(name).matches()) {
            throw new SoqlSafeException('Invalid identifier: ' + name);
        }
        return name;
    }

    public static String escapeLiteral(Object value) {
        if (value == null) { return 'null'; }
        if (value instanceof Boolean) { return ((Boolean) value) ? 'true' : 'false'; }
        if (value instanceof Integer || value instanceof Decimal || value instanceof Double || value instanceof Long) {
            return String.valueOf(value);
        }
        String s = String.valueOf(value);
        s = s.replace('\\', '\\\\').replace('\'', '\\\'');
        return '\'' + s + '\'';
    }

    public static void ensureReadOnly(String soql) {
        if (String.isBlank(soql)) { throw new SoqlSafeException('SOQL must not be blank'); }
        String upper = soql.toUpperCase();
        for (String kw : new List<String>{'UPDATE ', 'DELETE ', 'INSERT ', 'UPSERT ', 'MERGE ', 'TRUNCATE', '--', ';'}) {
            if (upper.contains(kw)) { throw new SoqlSafeException('SOQL contains forbidden keyword: ' + kw); }
        }
    }
}
