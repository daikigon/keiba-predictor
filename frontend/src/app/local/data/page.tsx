import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { ScrapeForm } from '@/components/features/data/ScrapeForm';
import { SyncToSupabaseButton } from '@/components/features/data/SyncToSupabaseButton';
import { getScrapeStats } from '@/lib/api';
import { Database, Calendar, Users, AlertTriangle, Server, CheckCircle } from 'lucide-react';
import { API_BASE_URL } from '@/lib/constants';

export const dynamic = 'force-dynamic';

async function getStats() {
  try {
    return await getScrapeStats('local');
  } catch {
    return null;
  }
}

async function checkBackendHealth(): Promise<boolean> {
  if (!API_BASE_URL) return false;
  try {
    const res = await fetch(`${API_BASE_URL}/api/v1/stats/scrape`, {
      cache: 'no-store',
      signal: AbortSignal.timeout(3000),
    });
    return res.ok;
  } catch {
    return false;
  }
}

export default async function DataPage() {
  const [stats, isBackendAvailable] = await Promise.all([
    getStats(),
    checkBackendHealth(),
  ]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">地方競馬 データ管理</h1>
        <p className="text-gray-500 mt-1">地方競馬のレースデータスクレイピングと状況確認</p>
      </div>

      {/* バックエンド状態表示 */}
      {isBackendAvailable ? (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start gap-3">
            <CheckCircle className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-green-800">ローカルバックエンド接続中</h3>
              <p className="text-sm text-green-700 mt-1">
                FastAPIバックエンドに接続しています。スクレイピング機能が利用可能です。
              </p>
              <div className="mt-2 text-xs text-green-600 bg-green-100 px-2 py-1 rounded inline-flex items-center gap-1">
                <Server className="w-3 h-3" />
                FastAPIバックエンド: 稼働中
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-amber-800">ローカル環境専用機能</h3>
              <p className="text-sm text-amber-700 mt-1">
                この機能はローカルのFastAPIバックエンドが必要です。
                現在はSupabase直接接続モードのため、スクレイピング機能は
                <a href="/operations" className="underline font-medium mx-1">運用管理ページ</a>
                またはコマンドラインをご利用ください。
              </p>
              <div className="mt-2 text-xs text-amber-600 bg-amber-100 px-2 py-1 rounded inline-flex items-center gap-1">
                <Server className="w-3 h-3" />
                FastAPIバックエンド: 停止中
              </div>
            </div>
          </div>
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        {/* Scrape Form */}
        <div className={isBackendAvailable ? '' : 'opacity-60 pointer-events-none'}>
          <ScrapeForm raceType="local" />
        </div>

        {/* Sync to Supabase */}
        <SyncToSupabaseButton isBackendAvailable={isBackendAvailable} />

        {/* Stats Overview */}
        {stats ? (
          <Card>
            <CardHeader>
              <CardTitle>地方競馬統計（{isBackendAvailable ? 'ローカルDB' : 'Supabase'}）</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <StatRow
                  icon={<Calendar className="w-5 h-5 text-blue-600" />}
                  label="総レース数"
                  value={stats.total_races.toLocaleString()}
                />
                <StatRow
                  icon={<Users className="w-5 h-5 text-green-600" />}
                  label="総出走数"
                  value={stats.total_entries.toLocaleString()}
                />
                <StatRow
                  icon={<Database className="w-5 h-5 text-purple-600" />}
                  label="登録馬数"
                  value={stats.total_horses.toLocaleString()}
                />
                <StatRow
                  icon={<Users className="w-5 h-5 text-orange-600" />}
                  label="登録騎手数"
                  value={stats.total_jockeys.toLocaleString()}
                />
                {stats.latest_race_date && (
                  <div className="pt-2 border-t">
                    <p className="text-sm text-gray-500">
                      最新データ: {stats.latest_race_date}
                    </p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card>
            <CardHeader>
              <CardTitle>地方競馬統計（{isBackendAvailable ? 'ローカルDB' : 'Supabase'}）</CardTitle>
            </CardHeader>
            <CardContent className="py-8 text-center">
              <p className="text-gray-500">統計データを取得できませんでした</p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>コマンドラインからのデータ取得（推奨）</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">
                Supabase直接スクレイピング
              </h4>
              <div className="bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <p># 特定の日付を取得</p>
                <p className="text-green-400">python3 scripts/scrape_local.py --date 2024-12-22</p>
                <p className="mt-2"># 期間指定でスクレイピング</p>
                <p className="text-green-400">python3 scripts/scrape_local.py --start 2024-12-01 --end 2024-12-22</p>
                <p className="mt-2"># データ件数確認</p>
                <p className="text-green-400">python3 scripts/scrape_local.py --stats</p>
              </div>
            </div>

            <div className="p-4 bg-gray-50 rounded-lg">
              <h4 className="font-medium text-gray-900 mb-2">
                ローカルFastAPIバックエンドを使う場合
              </h4>
              <p className="text-sm text-gray-600 mb-3">
                大量データの高速処理が必要な場合は、ローカルPostgreSQLとFastAPIバックエンドを起動してください。
              </p>
              <div className="bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <p># PostgreSQL起動（Homebrew）</p>
                <p className="text-green-400">brew services start postgresql</p>
                <p className="mt-2"># FastAPIバックエンド起動</p>
                <p className="text-green-400">cd backend && source venv/bin/activate && uvicorn app.main:app --reload</p>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function StatRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between py-2 border-b last:border-0">
      <div className="flex items-center gap-3">
        {icon}
        <span className="text-gray-600">{label}</span>
      </div>
      <span className="font-semibold text-gray-900">{value}</span>
    </div>
  );
}
