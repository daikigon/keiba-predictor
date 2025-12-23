import { supabase } from './supabase';

export type AuthUser = {
  id: string;
  email: string;
  hasMFA?: boolean;
};

export type MFAFactor = {
  id: string;
  type: 'totp';
  friendly_name?: string;
  status: 'verified' | 'unverified';
};

// メールとパスワードでサインアップ
export async function signUp(email: string, password: string) {
  if (!supabase) throw new Error('Supabase is not configured');

  const { data, error } = await supabase.auth.signUp({
    email,
    password,
  });

  if (error) throw error;
  return data;
}

// メールとパスワードでログイン
export async function signIn(email: string, password: string) {
  if (!supabase) throw new Error('Supabase is not configured');

  const { data, error } = await supabase.auth.signInWithPassword({
    email,
    password,
  });

  if (error) throw error;
  return data;
}

// ログアウト
export async function signOut() {
  if (!supabase) throw new Error('Supabase is not configured');

  const { error } = await supabase.auth.signOut();
  if (error) throw error;
}

// 現在のユーザーを取得
export async function getCurrentUser(): Promise<AuthUser | null> {
  if (!supabase) return null;

  const { data: { user } } = await supabase.auth.getUser();

  if (!user) return null;

  return {
    id: user.id,
    email: user.email || '',
  };
}

// セッションを取得
export async function getSession() {
  if (!supabase) return null;

  const { data: { session } } = await supabase.auth.getSession();
  return session;
}

// 認証状態の変更を監視
export function onAuthStateChange(callback: (user: AuthUser | null) => void) {
  if (!supabase) return { data: { subscription: { unsubscribe: () => {} } } };

  return supabase.auth.onAuthStateChange((event, session) => {
    if (session?.user) {
      callback({
        id: session.user.id,
        email: session.user.email || '',
      });
    } else {
      callback(null);
    }
  });
}

// ===== MFA (二要素認証) 関連 =====

// MFAファクター一覧を取得
export async function getMFAFactors(): Promise<MFAFactor[]> {
  if (!supabase) return [];

  const { data, error } = await supabase.auth.mfa.listFactors();
  if (error) throw error;

  const factors = data?.totp || data?.all || [];
  return factors.map((f: { id: string; status: string; friendly_name?: string }) => ({
    id: f.id,
    type: 'totp' as const,
    friendly_name: f.friendly_name,
    status: f.status as 'verified' | 'unverified',
  }));
}

// MFAが有効かどうかを確認
export async function hasMFAEnabled(): Promise<boolean> {
  const factors = await getMFAFactors();
  return factors.some((f) => f.status === 'verified');
}

// MFA登録を開始（QRコード生成）
export async function enrollMFA(friendlyName?: string) {
  if (!supabase) throw new Error('Supabase is not configured');

  const { data, error } = await supabase.auth.mfa.enroll({
    factorType: 'totp',
    friendlyName: friendlyName || 'Authenticator App',
  });

  if (error) throw error;
  return data;
}

// MFA登録を確認（TOTPコードで検証）
export async function verifyMFAEnrollment(factorId: string, code: string) {
  if (!supabase) throw new Error('Supabase is not configured');

  const { data: challengeData, error: challengeError } =
    await supabase.auth.mfa.challenge({ factorId });

  if (challengeError) throw challengeError;

  const { data, error } = await supabase.auth.mfa.verify({
    factorId,
    challengeId: challengeData.id,
    code,
  });

  if (error) throw error;
  return data;
}

// MFAチャレンジを作成（ログイン時）
export async function createMFAChallenge(factorId: string) {
  if (!supabase) throw new Error('Supabase is not configured');

  const { data, error } = await supabase.auth.mfa.challenge({ factorId });
  if (error) throw error;
  return data;
}

// MFAチャレンジを検証（ログイン時）
export async function verifyMFAChallenge(factorId: string, challengeId: string, code: string) {
  if (!supabase) throw new Error('Supabase is not configured');

  const { data, error } = await supabase.auth.mfa.verify({
    factorId,
    challengeId,
    code,
  });

  if (error) throw error;
  return data;
}

// MFAを無効化
export async function unenrollMFA(factorId: string) {
  if (!supabase) throw new Error('Supabase is not configured');

  const { error } = await supabase.auth.mfa.unenroll({ factorId });
  if (error) throw error;
}

// 現在のAAL（認証保証レベル）を取得
export async function getAuthenticatorAssuranceLevel() {
  if (!supabase) return null;

  const { data, error } = await supabase.auth.mfa.getAuthenticatorAssuranceLevel();
  if (error) throw error;
  return data;
}
