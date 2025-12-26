'use client';

import { useState, useEffect } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Shield, Loader2 } from 'lucide-react';
import { verifyMFAChallenge, createMFAChallenge } from '@/lib/auth';

export default function MFAPage() {
  const [mfaCode, setMfaCode] = useState('');
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [challengeId, setChallengeId] = useState<string | null>(null);

  const router = useRouter();
  const searchParams = useSearchParams();
  const factorId = searchParams.get('factorId');

  useEffect(() => {
    // factorIdがない場合はログインページへ
    if (!factorId) {
      router.push('/login');
      return;
    }

    // チャレンジを作成
    const initChallenge = async () => {
      try {
        const challenge = await createMFAChallenge(factorId);
        setChallengeId(challenge.id);
      } catch (err) {
        console.error('Failed to create MFA challenge:', err);
        setError('MFA認証の初期化に失敗しました');
      }
    };

    initChallenge();
  }, [factorId, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!factorId || !challengeId) return;

    setError('');
    setIsLoading(true);

    try {
      await verifyMFAChallenge(factorId, challengeId, mfaCode);
      router.push('/');
    } catch {
      setError('認証コードが正しくありません');
      setMfaCode('');
      // 新しいチャレンジを作成
      try {
        const challenge = await createMFAChallenge(factorId);
        setChallengeId(challenge.id);
      } catch {
        setError('MFA認証の再初期化に失敗しました');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleBack = () => {
    router.push('/login');
  };

  if (!challengeId) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <Shield className="mx-auto h-12 w-12 text-blue-600" />
          <h1 className="mt-4 text-2xl font-bold text-gray-900">
            二要素認証
          </h1>
          <p className="mt-2 text-gray-600">
            認証アプリに表示された6桁のコードを入力してください
          </p>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded">
              {error}
            </div>
          )}

          <div>
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={6}
              value={mfaCode}
              onChange={(e) => setMfaCode(e.target.value.replace(/\D/g, ''))}
              placeholder="000000"
              className="w-full px-4 py-4 text-center text-3xl tracking-[0.5em] border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              autoComplete="one-time-code"
              autoFocus
            />
          </div>

          <div className="space-y-3">
            <button
              type="submit"
              disabled={mfaCode.length !== 6 || isLoading}
              className="w-full flex justify-center items-center py-3 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  確認中...
                </>
              ) : (
                '確認'
              )}
            </button>

            <button
              type="button"
              onClick={handleBack}
              className="w-full py-2 text-sm text-gray-600 hover:text-gray-900"
            >
              ログイン画面に戻る
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
