public with sharing class SuitabilityCheckDeterministic {
    public enum Outcome { PASS_OK, FAIL_RISK_PROFILE, FAIL_CONCENTRATION, REVIEW_HORIZON }

    public class Result {
        public Outcome verdict;
        public String reason;
        public Result(Outcome v, String r) { this.verdict = v; this.reason = r; }
    }

    public static Result evaluate(String riskProfile, String tradeSide, Decimal notional,
                                  Decimal currentConcentrationPct, Integer timeHorizonMonths) {
        if (riskProfile == null) {
            return new Result(Outcome.REVIEW_HORIZON, 'Missing risk profile');
        }
        Decimal ceiling = riskProfile == 'Conservative' ? 5.0 : riskProfile == 'Moderate' ? 15.0 : 30.0;
        if (tradeSide == 'buy' && currentConcentrationPct != null && currentConcentrationPct >= ceiling) {
            return new Result(Outcome.FAIL_CONCENTRATION,
                'Concentration ' + currentConcentrationPct + '% exceeds ' + ceiling + '% ceiling for ' + riskProfile);
        }
        if (timeHorizonMonths != null && timeHorizonMonths < 3 && notional != null && notional > 100000) {
            return new Result(Outcome.REVIEW_HORIZON, 'Large notional on short horizon — review');
        }
        return new Result(Outcome.PASS_OK, 'Within profile');
    }
}
