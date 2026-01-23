'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { Calendar, History, BarChart3, Database, Users, Award, Cpu, LogOut, Shield, Settings } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';

function getNavigation(baseUrl: string) {
  return [
    { name: 'ホーム', href: baseUrl, icon: BarChart3 },
    { name: 'レース', href: `${baseUrl}/races`, icon: Calendar },
    { name: '競走馬', href: `${baseUrl}/horses`, icon: Award },
    { name: '騎手', href: `${baseUrl}/jockeys`, icon: Users },
    { name: '履歴', href: `${baseUrl}/history`, icon: History },
    { name: 'データ', href: `${baseUrl}/data`, icon: Database },
    { name: 'モデル', href: `${baseUrl}/model`, icon: Cpu },
    { name: '運用', href: `${baseUrl}/operations`, icon: Settings },
  ];
}

const raceTypeLabels: Record<string, string> = {
  central: '中央競馬',
  local: '地方競馬',
  banei: 'ばんえい競馬',
};

const raceTypeColors: Record<string, { bg: string; text: string; activeBg: string; activeText: string }> = {
  central: { bg: 'bg-blue-50', text: 'text-blue-700', activeBg: 'bg-blue-50', activeText: 'text-blue-700' },
  local: { bg: 'bg-green-50', text: 'text-green-700', activeBg: 'bg-green-50', activeText: 'text-green-700' },
  banei: { bg: 'bg-purple-50', text: 'text-purple-700', activeBg: 'bg-purple-50', activeText: 'text-purple-700' },
};

export function Header() {
  const pathname = usePathname();
  const { user, signOut } = useAuth();

  // Determine the base URL from the current path
  const baseUrl = pathname.startsWith('/local') ? '/local'
    : pathname.startsWith('/banei') ? '/banei'
    : '/central';

  const raceType = baseUrl.replace('/', '');
  const navigation = getNavigation(baseUrl);
  const colors = raceTypeColors[raceType] || raceTypeColors.central;

  const handleSignOut = async () => {
    try {
      await signOut();
    } catch (error) {
      console.error('Sign out error:', error);
    }
  };

  return (
    <header className="bg-white border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between h-16">
          <div className="flex">
            <div className="flex-shrink-0 flex items-center gap-3">
              <Link href="/" className="text-xl font-bold text-gray-900">
                競馬予想AI
              </Link>
              <span className={cn(
                'px-2 py-0.5 text-xs font-medium rounded',
                colors.bg,
                colors.text
              )}>
                {raceTypeLabels[raceType]}
              </span>
            </div>
            <nav className="hidden sm:ml-6 sm:flex sm:space-x-1">
              {navigation.map((item) => {
                const isActive = pathname === item.href ||
                  (item.href !== '/' && pathname.startsWith(item.href));
                return (
                  <Link
                    key={item.name}
                    href={item.href}
                    className={cn(
                      'inline-flex items-center px-2 py-2 text-sm font-medium rounded-md whitespace-nowrap',
                      isActive
                        ? `${colors.activeBg} ${colors.activeText}`
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    )}
                    title={item.name}
                  >
                    <item.icon className="w-4 h-4 mr-1" />
                    {item.name}
                  </Link>
                );
              })}
            </nav>
          </div>

          {/* User menu */}
          {user && (
            <div className="flex items-center space-x-1 sm:space-x-2">
              <span className="hidden lg:block text-sm text-gray-600 truncate max-w-[150px]">
                {user.email}
              </span>
              <Link
                href={`${baseUrl}/settings/security`}
                className="inline-flex items-center p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-md"
                title="セキュリティ設定"
              >
                <Shield className="w-4 h-4" />
              </Link>
              <button
                onClick={handleSignOut}
                className="inline-flex items-center px-3 py-2 text-sm font-medium text-gray-600 hover:text-gray-900 hover:bg-gray-50 rounded-md"
              >
                <LogOut className="w-4 h-4 sm:mr-2" />
                <span className="hidden sm:inline">ログアウト</span>
              </button>
            </div>
          )}
        </div>
      </div>

      {/* Mobile navigation */}
      <nav className="sm:hidden border-t border-gray-200">
        <div className="flex justify-around py-2">
          {navigation.map((item) => {
            const isActive = pathname === item.href ||
              (item.href !== '/' && pathname.startsWith(item.href));
            return (
              <Link
                key={item.name}
                href={item.href}
                className={cn(
                  'flex flex-col items-center px-3 py-2 text-xs',
                  isActive ? colors.activeText : 'text-gray-600'
                )}
              >
                <item.icon className="w-5 h-5 mb-1" />
                {item.name}
              </Link>
            );
          })}
        </div>
      </nav>
    </header>
  );
}
