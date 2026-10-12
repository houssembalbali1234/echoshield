// Types des données renvoyées par l'API EchoShield.
// Ils reprennent les schémas Pydantic du backend (backend/app/schemas).

export type User = {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
};

export type CircleKind = "family" | "enterprise";
export type CircleRole = "owner" | "admin" | "member";

export type Circle = {
  id: string;
  name: string;
  kind: CircleKind;
  created_at: string;
  my_role: CircleRole;
};

export type Member = {
  user_id: string;
  full_name: string;
  email: string;
  role: CircleRole;
  trusted_from: string;
  is_trusted: boolean;
};

export type CircleDetail = Circle & { members: Member[] };

export type Invitation = { token: string; expires_at: string };

export type Device = {
  id: string;
  name: string;
  status: "active" | "revoked";
  activates_at: string;
  created_at: string;
  revoked_at: string | null;
  can_confirm: boolean;
};

export type RiskLevel = "low" | "medium" | "high";

export type RiskSignal = {
  code: string;
  label: string;
  weight: number;
  matches: string[];
};

export type RiskReport = {
  level: RiskLevel;
  score: number;
  signals: RiskSignal[];
  recommendation: string;
};

export type VerificationStatus = "pending" | "confirmed" | "denied" | "expired";

export type Verification = {
  id: string;
  circle_id: string;
  requester_id: string;
  claimed_user_id: string;
  note: string | null;
  status: VerificationStatus;
  created_at: string;
  expires_at: string;
  responded_at: string | null;
  risk: RiskReport;
};

export type IncomingChallenge = {
  id: string;
  requester_name: string;
  note: string | null;
  expires_at: string;
  message_to_sign_confirm: string;
  message_to_sign_deny: string;
};

export type SecretCodeStatus = {
  has_code: boolean;
  pending_change: boolean;
  pending_active_from: string | null;
};

export type SecretCodeCheckResult = { valid: boolean; attempts_left: number };