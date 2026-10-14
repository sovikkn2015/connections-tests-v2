/** Schwab Zod schemas — 3 READ-ONLY tools. Spec T-SC1..T-SC3. */

import { z } from "zod";

export const AccountNumber = z.string().regex(/^\d{8}$/, { message: "account_digits" });
export const SymbolRegex = z.string().regex(/^[A-Z0-9.\-]+$/).max(20);
export const MasterAccountId = z.string().regex(/^[A-Z0-9\-]{1,32}$/);

export const FetchPositionsInput = z
  .object({
    accountNumber: AccountNumber,
    fields: z.array(z.string().max(32)).max(8).optional(),
  })
  .strict();

export const FetchTaxlotsInput = z
  .object({
    accountNumber: AccountNumber,
    symbol: SymbolRegex.optional(),
  })
  .strict();

export const FetchMasterAccountInput = z
  .object({
    masterAccountId: MasterAccountId,
    includeLinkedAccounts: z.boolean().optional(),
  })
  .strict();

export type FetchPositionsArgs = z.infer<typeof FetchPositionsInput>;
export type FetchTaxlotsArgs = z.infer<typeof FetchTaxlotsInput>;
export type FetchMasterAccountArgs = z.infer<typeof FetchMasterAccountInput>;
