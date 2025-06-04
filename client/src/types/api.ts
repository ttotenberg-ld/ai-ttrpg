export interface UserBase {
  username: string;
  email: string;
}

export interface User extends UserBase {
  id: number;
}

export interface UserCreate extends UserBase {
  password: string;
}

export interface PlayerCharacterBase {
  name: string;
  strength?: number;
  dexterity?: number;
  intelligence?: number;
  charisma?: number;
  personality_traits?: string | null;
  skills?: string | null; // Consider as JSON string or comma-separated
  inventory?: string | null; // Consider as JSON string or comma-separated
}

export interface PlayerCharacter extends PlayerCharacterBase {
  id: number;
  user_id: number;
}

export type PlayerCharacterCreate = PlayerCharacterBase;

export interface PlayerCharacterRead extends PlayerCharacterBase {
  id: number;
  user_id: number;
  is_template?: boolean;
  is_public?: boolean;
  version?: number;
  experience_points?: number;
  character_level?: number;
  created_at?: string;
  updated_at?: string;
}

export interface PlayerCharacterUpdate {
  name?: string;
  strength?: number;
  dexterity?: number;
  intelligence?: number;
  charisma?: number;
  personality_traits?: string | null;
  skills?: string | null;
  inventory?: string | null;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  refresh_token: string;
  expires_in: number;
}

export interface RefreshTokenRequest {
  refresh_token: string;
}

export interface LoginRequest {
  username: string;
  password: string;
}

export interface RegisterRequest extends UserCreate {
  confirm_password: string;
}

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  email_verified: boolean;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  updated_at: string;
}

export interface UserProfileUpdate {
  username?: string;
  email?: string;
}

export interface PasswordResetRequest {
  email: string;
}

export interface PasswordResetConfirm {
  token: string;
  new_password: string;
  confirm_password: string;
}

export interface AuthState {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: UserProfile | null;
  accessToken: string | null;
  refreshToken: string | null;
}

// Standard error response from FastAPI/HTTPException
export interface APIError {
  detail: string | { msg: string; type: string }[]; // FastAPI can return a string or a list of Pydantic errors
}

// --- Adventure and Game State Types ---

export interface AdventureEncounter {
  description: string;
  challenge_objective: string;
  potential_outcomes?: string | null;
}

export interface AdventureDefinition {
  title: string;
  overall_goal: string;
  encounters: AdventureEncounter[];
  conclusion: string;
}

export interface StartAdventureResponse {
  adventure_id: string;
  adventure_definition: AdventureDefinition;
}

// --- Player Action Types ---
export interface PlayerActionRequest {
  action_text: string;
  stat_to_check?: string | null; // "strength", "dexterity", etc.
  suggested_dc?: number | null;
}

export interface ActionOutcomeResponse {
  narration: string;
  skill_check_result_desc?: string | null;
  skill_check_success?: boolean | null;
}

// --- Reward System Types ---
export enum RewardType {
  EQUIPMENT = "equipment",
  NEW_SKILL = "new_skill",
  STAT_UPGRADE = "stat_upgrade",
}

export interface Reward {
  reward_type: RewardType;
  name: string;
  description: string;
  target_stat?: string | null;
  value?: string | null;
}

// --- Player Preferences for Adventure Generation ---
export interface PlayerPreferences {
  theme?: string | null;
  difficulty?: string | null;
  length?: string | null;
}

// --- Dice Roll and Skill Check Types ---
export interface SkillCheckResult {
  success: boolean;
  roll_value: number;
  modifier_applied: number;
  dc: number;
  description: string;
} 