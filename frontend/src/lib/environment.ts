/**
 * 環境検出ユーティリティ
 * ローカル環境とクラウド環境（Vercel）を判別
 */

export type Environment = 'local' | 'cloud';

export function getEnvironment(): Environment {
  // Vercel環境変数をチェック
  if (process.env.NEXT_PUBLIC_VERCEL_ENV) {
    return 'cloud';
  }
  if (process.env.VERCEL) {
    return 'cloud';
  }
  // Vercel URLがある場合もクラウド
  if (process.env.NEXT_PUBLIC_VERCEL_URL) {
    return 'cloud';
  }
  return 'local';
}

export function isLocalEnvironment(): boolean {
  return getEnvironment() === 'local';
}

export function isCloudEnvironment(): boolean {
  return getEnvironment() === 'cloud';
}

export function getEnvironmentLabel(): string {
  return getEnvironment() === 'local' ? 'ローカル環境' : 'クラウド環境';
}

export function getEnvironmentColor(): string {
  return getEnvironment() === 'local' ? 'green' : 'blue';
}
