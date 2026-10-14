/* ── Chat Messages ── */
export interface Message {
  id: string;
  role: 'user' | 'agent';
  text: string;
  timestamp: Date;
  isStreaming?: boolean;
}

/* ── Household / Client 360 ── */
export interface HouseholdData {
  name: string;
  totalAum: string;
  riskProfile: string;
  advisor: string;
  members: { name: string; role: string; email: string }[];
}

/* ── Financial Accounts ── */
export interface AccountData {
  name: string;
  client: string;
  type: string;
  balance: string;
  allocation: string;
  ytdReturn: string;
  targetAllocation?: string;
}

/* ── Financial Goals ── */
export interface GoalData {
  name: string;
  client: string;
  targetAmount: string;
  currentAmount: string;
  targetDate: string;
  progressPct: number;
}

/* ── Meetings ── */
export interface MeetingData {
  client: string;
  dateTime: string;
  location: string;
  notes: string;
  actionItems: string;
}

/* ── Transactions ── */
export interface TransactionData {
  date: string;
  type: string;
  symbol: string;
  amount: string;
  description: string;
}

/* ── Referrals ── */
export interface ReferralData {
  client: string;
  source: string;
  sourceType: string;
  date: string;
  status: string;
  value: string;
}

/* ── Compliance ── */
export interface ComplianceData {
  client: string;
  status: 'Compliant' | 'Warning' | 'Non-Compliant';
  driftPct: number;
  concentrationPct: number;
  issues: string[];
  lastChecked: string;
}

/* ── Rebalancing ── */
export interface RebalancingData {
  client: string;
  needsRebalancing: boolean;
  accounts: {
    name: string;
    currentAllocation: string;
    targetAllocation: string;
    driftPct: number;
  }[];
}

/* ── Advisor Panel Tab ── */
export type AdvisorTab = 'clients' | 'portfolio' | 'goals' | 'activity';

/* ── Auth State ── */
export interface AuthState {
  accessToken: string | null;
  instanceUrl: string | null;
  userInfo: UserInfo | null;
}

export interface UserInfo {
  name: string;
  email: string;
  userId: string;
}
