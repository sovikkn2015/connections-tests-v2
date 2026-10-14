@isTest
private class SuitabilityCheckDeterministicTest {
    @isTest static void conservative_over_ceiling_fails() {
        SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
            'Conservative', 'buy', 10000, 6.0, 24);
        System.assertEquals(SuitabilityCheckDeterministic.Outcome.FAIL_CONCENTRATION, r.verdict);
    }
    @isTest static void moderate_under_ceiling_passes() {
        SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
            'Moderate', 'buy', 5000, 10.0, 24);
        System.assertEquals(SuitabilityCheckDeterministic.Outcome.PASS_OK, r.verdict);
    }
    @isTest static void aggressive_allows_higher_concentration() {
        SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
            'Aggressive', 'buy', 5000, 25.0, 12);
        System.assertEquals(SuitabilityCheckDeterministic.Outcome.PASS_OK, r.verdict);
    }
    @isTest static void short_horizon_large_notional_review() {
        SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
            'Moderate', 'buy', 200000, 5.0, 2);
        System.assertEquals(SuitabilityCheckDeterministic.Outcome.REVIEW_HORIZON, r.verdict);
    }
    @isTest static void missing_profile_review() {
        SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
            null, 'buy', 1000, 1.0, 24);
        System.assertEquals(SuitabilityCheckDeterministic.Outcome.REVIEW_HORIZON, r.verdict);
    }
    @isTest static void sell_not_blocked() {
        SuitabilityCheckDeterministic.Result r = SuitabilityCheckDeterministic.evaluate(
            'Conservative', 'sell', 10000, 6.0, 24);
        System.assertEquals(SuitabilityCheckDeterministic.Outcome.PASS_OK, r.verdict);
    }
}
