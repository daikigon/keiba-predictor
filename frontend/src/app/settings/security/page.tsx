'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { ArrowLeft, Shield, ShieldCheck, Loader2, QrCode, Trash2 } from 'lucide-react';
import {
  getMFAFactors,
  enrollMFA,
  verifyMFAEnrollment,
  unenrollMFA,
  MFAFactor,
} from '@/lib/auth';

export default function SecuritySettingsPage() {
  const [factors, setFactors] = useState<MFAFactor[]>([]);
  const [loading, setLoading] = useState(true);
  const [enrolling, setEnrolling] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [removing, setRemoving] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // 登録中の状態
  const [enrollmentData, setEnrollmentData] = useState<{
    id: string;
    qrCode: string;
    secret: string;
  } | null>(null);
  const [verificationCode, setVerificationCode] = useState('');

  useEffect(() => {
    loadFactors();
  }, []);

  const loadFactors = async () => {
    try {
      setLoading(true);
      const data = await getMFAFactors();
      setFactors(data);
    } catch (err) {
      setError('MFA情報の取得に失敗しました');
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleEnroll = async () => {
    try {
      setEnrolling(true);
      setError('');
      const data = await enrollMFA();
      setEnrollmentData({
        id: data.id,
        qrCode: data.totp.qr_code,
        secret: data.totp.secret,
      });
    } catch (err) {
      setError('MFA登録の開始に失敗しました');
      console.error(err);
    } finally {
      setEnrolling(false);
    }
  };

  const handleVerifyEnrollment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!enrollmentData) return;

    try {
      setVerifying(true);
      setError('');
      await verifyMFAEnrollment(enrollmentData.id, verificationCode);
      setSuccess('二要素認証が有効になりました');
      setEnrollmentData(null);
      setVerificationCode('');
      await loadFactors();
    } catch (err) {
      setError('認証コードが正しくありません');
      console.error(err);
    } finally {
      setVerifying(false);
    }
  };

  const handleCancelEnrollment = () => {
    setEnrollmentData(null);
    setVerificationCode('');
    setError('');
  };

  const handleRemoveFactor = async (factorId: string) => {
    if (!confirm('二要素認証を無効にしますか？')) return;

    try {
      setRemoving(factorId);
      setError('');
      await unenrollMFA(factorId);
      setSuccess('二要素認証が無効になりました');
      await loadFactors();
    } catch (err) {
      setError('MFAの削除に失敗しました');
      console.error(err);
    } finally {
      setRemoving(null);
    }
  };

  const verifiedFactors = factors.filter((f) => f.status === 'verified');
  const hasMFA = verifiedFactors.length > 0;

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-6">
        <Link
          href="/"
          className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          ダッシュボードに戻る
        </Link>
      </div>

      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center mb-6">
          {hasMFA ? (
            <ShieldCheck className="w-8 h-8 text-green-600 mr-3" />
          ) : (
            <Shield className="w-8 h-8 text-gray-400 mr-3" />
          )}
          <div>
            <h1 className="text-2xl font-bold text-gray-900">セキュリティ設定</h1>
            <p className="text-sm text-gray-600">二要素認証（2FA）の管理</p>
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-700 text-sm">
            {error}
          </div>
        )}

        {success && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-700 text-sm">
            {success}
          </div>
        )}

        {/* 登録済みのMFA */}
        {verifiedFactors.length > 0 && (
          <div className="mb-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-3">
              登録済みの認証方法
            </h2>
            <div className="space-y-3">
              {verifiedFactors.map((factor) => (
                <div
                  key={factor.id}
                  className="flex items-center justify-between p-4 bg-gray-50 rounded-lg"
                >
                  <div className="flex items-center">
                    <QrCode className="w-5 h-5 text-gray-600 mr-3" />
                    <div>
                      <p className="font-medium text-gray-900">
                        {factor.friendly_name || '認証アプリ'}
                      </p>
                      <p className="text-sm text-gray-500">TOTP認証</p>
                    </div>
                  </div>
                  <button
                    onClick={() => handleRemoveFactor(factor.id)}
                    disabled={removing === factor.id}
                    className="p-2 text-red-600 hover:bg-red-50 rounded-md disabled:opacity-50"
                  >
                    {removing === factor.id ? (
                      <Loader2 className="w-5 h-5 animate-spin" />
                    ) : (
                      <Trash2 className="w-5 h-5" />
                    )}
                  </button>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MFA登録フロー */}
        {!hasMFA && !enrollmentData && (
          <div className="text-center py-8">
            <Shield className="w-16 h-16 text-gray-300 mx-auto mb-4" />
            <h2 className="text-lg font-semibold text-gray-900 mb-2">
              二要素認証を有効にする
            </h2>
            <p className="text-gray-600 mb-6">
              Google Authenticatorなどの認証アプリを使用して、
              <br />
              アカウントのセキュリティを強化できます。
            </p>
            <button
              onClick={handleEnroll}
              disabled={enrolling}
              className="inline-flex items-center px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {enrolling ? (
                <>
                  <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                  準備中...
                </>
              ) : (
                <>
                  <Shield className="w-5 h-5 mr-2" />
                  二要素認証を設定する
                </>
              )}
            </button>
          </div>
        )}

        {/* QRコード表示 & 検証 */}
        {enrollmentData && (
          <div className="py-4">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">
              認証アプリで登録
            </h2>

            <div className="mb-6">
              <p className="text-gray-600 mb-4">
                1. Google AuthenticatorまたはAuthyなどの認証アプリを開きます
              </p>
              <p className="text-gray-600 mb-4">
                2. 以下のQRコードをスキャンするか、シークレットキーを手動で入力します
              </p>
            </div>

            <div className="flex flex-col items-center mb-6">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={enrollmentData.qrCode}
                alt="QR Code"
                className="w-48 h-48 border rounded-lg mb-4"
              />
              <div className="text-center">
                <p className="text-sm text-gray-500 mb-1">シークレットキー:</p>
                <code className="text-sm bg-gray-100 px-3 py-1 rounded font-mono">
                  {enrollmentData.secret}
                </code>
              </div>
            </div>

            <form onSubmit={handleVerifyEnrollment} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  3. 認証アプリに表示された6桁のコードを入力
                </label>
                <input
                  type="text"
                  inputMode="numeric"
                  pattern="[0-9]*"
                  maxLength={6}
                  value={verificationCode}
                  onChange={(e) => setVerificationCode(e.target.value.replace(/\D/g, ''))}
                  placeholder="000000"
                  className="w-full px-4 py-3 text-center text-2xl tracking-widest border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  autoComplete="one-time-code"
                />
              </div>

              <div className="flex space-x-3">
                <button
                  type="button"
                  onClick={handleCancelEnrollment}
                  className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50"
                >
                  キャンセル
                </button>
                <button
                  type="submit"
                  disabled={verificationCode.length !== 6 || verifying}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {verifying ? (
                    <span className="flex items-center justify-center">
                      <Loader2 className="w-5 h-5 mr-2 animate-spin" />
                      確認中...
                    </span>
                  ) : (
                    '確認して有効化'
                  )}
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
}
