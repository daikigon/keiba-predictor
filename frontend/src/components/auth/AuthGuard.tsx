'use client';

import { useEffect } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';

const PUBLIC_PATHS = ['/login', '/login/mfa'];

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();
  const pathname = usePathname();

  useEffect(() => {
    if (!loading) {
      const isPublicPath = PUBLIC_PATHS.includes(pathname);

      if (!user && !isPublicPath) {
        // 未ログインで保護されたページにアクセス → ログインページへ
        router.push('/login');
      }
      // ログインページからのリダイレクトはログインページ自身が管理
      // （MFAフローを正しく処理するため）
    }
  }, [user, loading, pathname, router]);

  // ローディング中
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  // 未ログインで保護されたページの場合は何も表示しない（リダイレクト中）
  const isPublicPath = PUBLIC_PATHS.includes(pathname);
  if (!user && !isPublicPath) {
    return null;
  }

  return <>{children}</>;
}
