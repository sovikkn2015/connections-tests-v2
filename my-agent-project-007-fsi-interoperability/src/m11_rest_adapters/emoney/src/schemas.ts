/**
 * eMoney strict output Zod — aligned to M7 EMoneyPlanSummary.
 * Spec AC8.5 (v0.2.0). 7 required + 14 optional (per NEW-2 patch).
 *
 * ANY top-level key NOT on this list causes AC8.6 rejection with
 * emoney_raw_plan_forbidden (HTTP 502, non-retryable).
 */

import { z } from "zod";

export const FetchPlanSummaryInput = z
  .object({
    planId: z.string().uuid(),
    includeGoals: z.boolean().optional(),
  })
  .strict();

export type FetchPlanSummaryArgs = z.infer<typeof FetchPlanSummaryInput>;

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;
const ISO_DATETIME = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$/;

export const RetirementGoalStrict = z
  .object({
    amount: z.number().nonnegative().optional(),
    targetDate: z.string().regex(ISO_DATE).optional(),
    incomeGap: z.number().optional(),
  })
  .strict();

export const MonteCarloStrict = z
  .object({
    successPct: z.number().min(0).max(100).optional(),
    iterations: z.number().int().nonnegative().optional(),
  })
  .strict();

export const AssumptionsStrict = z
  .object({
    inflation: z.number().optional(),
    returnAssumption: z.number().optional(),
    lifeExpectancy: z.number().int().nonnegative().optional(),
    retirementAge: z.number().int().optional(),
    taxRate: z.number().optional(),
  })
  .strict();

export const RecommendationStrict = z
  .object({
    category: z.string().min(1),
    description: z.string().min(1),
    priority: z.string().min(1),
  })
  .strict();

export const PlanTypeEnum = z.enum([
  "Comprehensive",
  "Retirement",
  "Education",
  "Estate",
  "Tax",
  "Insurance",
]);

export const EMoneyPlanSummaryOutput = z
  .object({
    planId: z.string().min(1),
    clientId: z.string().min(1),
    planName: z.string().min(1),
    probabilityOfSuccess: z.number().min(0).max(100),
    asOfDate: z.string().regex(ISO_DATE),
    createdAt: z.string().regex(ISO_DATETIME),
    updatedAt: z.string().regex(ISO_DATETIME),
    scenarioId: z.string().optional(),
    householdId: z.string().optional(),
    planType: PlanTypeEnum.optional(),
    totalAssets: z.number().nonnegative().optional(),
    totalLiabilities: z.number().nonnegative().optional(),
    retirementGoal: RetirementGoalStrict.optional(),
    monteCarlo: MonteCarloStrict.optional(),
    annualSavingsRate: z.number().nonnegative().optional(),
    annualSpending: z.number().nonnegative().optional(),
    socialSecurityEstimate: z.number().nonnegative().optional(),
    pensionIncome: z.number().nonnegative().optional(),
    goalIds: z.array(z.string()).optional(),
    assumptions: AssumptionsStrict.optional(),
    recommendations: z.array(RecommendationStrict).optional(),
  })
  .strict();

export const EMONEY_ALLOWLIST_FIELDS = Object.freeze([
  "planId",
  "clientId",
  "planName",
  "probabilityOfSuccess",
  "asOfDate",
  "createdAt",
  "updatedAt",
  "scenarioId",
  "householdId",
  "planType",
  "totalAssets",
  "totalLiabilities",
  "retirementGoal",
  "monteCarlo",
  "annualSavingsRate",
  "annualSpending",
  "socialSecurityEstimate",
  "pensionIncome",
  "goalIds",
  "assumptions",
  "recommendations",
] as const);
