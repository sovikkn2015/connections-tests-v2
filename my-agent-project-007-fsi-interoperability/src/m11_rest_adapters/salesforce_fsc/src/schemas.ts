/**
 * SFDC Zod input schemas — spec §Design + AC8.1, AC8.3, AC8.4, AC8.9.
 *
 * SF Id regex: base62, 15 or 18 chars.
 */

import { z } from "zod";

export const SFDC_ID_REGEX = /^[a-zA-Z0-9]{15,18}$/;

export const FetchClientInput = z
  .object({
    clientId: z.string().regex(SFDC_ID_REGEX, { message: "sfdc_id_regex" }),
  })
  .strict();

export const FetchHouseholdInput = z
  .object({
    householdId: z.string().regex(SFDC_ID_REGEX, { message: "sfdc_id_regex" }),
  })
  .strict();

export const FetchGoalInput = z
  .object({
    goalId: z.string().regex(SFDC_ID_REGEX, { message: "sfdc_id_regex" }),
  })
  .strict();

/**
 * Writable allow-list per Appendix E row 17.
 * PII fields (name, email, phone, SSN, DOB, tax ID) are NOT writable via
 * the service account — they stay in SFDC UI for native audit.
 */
export const WritableFields = z
  .object({
    FinServ__Status__c: z.string().max(64).optional(),
    FinServ__ClientArchetype__c: z.string().max(128).optional(),
    FinServ__RiskToleranceUpdatedDate__c: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, { message: "iso_date" })
      .optional(),
    Description: z.string().max(4000).optional(),
  })
  .strict();

export const UpdateClientInput = z
  .object({
    clientId: z.string().regex(SFDC_ID_REGEX, { message: "sfdc_id_regex" }),
    ifMatch: z.string().min(1).max(256),
    fields: WritableFields,
  })
  .strict();

export const InteractionTypeEnum = z.enum([
  "meeting",
  "call",
  "email",
  "note",
  "task",
]);

export const CreateInteractionSummaryInput = z
  .object({
    clientId: z.string().regex(SFDC_ID_REGEX, { message: "sfdc_id_regex" }),
    ifMatch: z.string().min(1).max(256),
    summaryText: z.string().min(1).max(32_000),
    interactionDate: z
      .string()
      .regex(/^\d{4}-\d{2}-\d{2}$/, { message: "iso_date" }),
    interactionType: InteractionTypeEnum.optional(),
  })
  .strict();

export type FetchClientArgs = z.infer<typeof FetchClientInput>;
export type FetchHouseholdArgs = z.infer<typeof FetchHouseholdInput>;
export type FetchGoalArgs = z.infer<typeof FetchGoalInput>;
export type UpdateClientArgs = z.infer<typeof UpdateClientInput>;
export type CreateInteractionSummaryArgs = z.infer<
  typeof CreateInteractionSummaryInput
>;
