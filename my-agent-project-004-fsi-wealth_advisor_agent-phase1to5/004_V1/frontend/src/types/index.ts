export interface Message {
  id: string;
  role: 'user' | 'agent';
  text: string;
  timestamp: Date;
  isStreaming?: boolean;
}

export interface HouseholdData {
  name: string;
  totalAum: string;
  riskProfile: string;
  advisor: string;
  members: { name: string; role: string; email: string }[];
}

export interface AccountData {
  name: string;
  client: string;
  type: string;
  balance: string;
  allocation: string;
  ytdReturn: string;
}

export interface GoalData {
  name: string;
  client: string;
  targetAmount: string;
  currentAmount: string;
  targetDate: string;
  progressPct: number;
}

export interface MeetingData {
  client: string;
  dateTime: string;
  location: string;
  notes: string;
  actionItems: string;
}

export interface TransactionData {
  date: string;
  type: string;
  symbol: string;
  amount: string;
  description: string;
}

export type AdvisorTab = 'clients' | 'portfolio' | 'goals' | 'activity';

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
