import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { RaceList } from '@/components/features/race/RaceList';
import { ScrapeStatsCard } from '@/components/features/prediction/StatsCard';
import { getRaces, getScrapeStats, getHistory } from '@/lib/api';
import { formatDate, formatPercent } from '@/lib/utils';
import { Calendar, TrendingUp, Target, DollarSign } from 'lucide-react';

export const dynamic = 'force-dynamic';

async function getTodayRaces() {
  try {
    const today = new Date().toISOString().split('T')[0];
    return await getRaces(today);
  } catch {
    return { total: 0, races: [] };
  }
}

async function getStats() {
  try {
    return await getScrapeStats();
  } catch {
    return null;
  }
}

async function getRecentHistory() {
  try {
    return await getHistory({ limit: 5 });
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const [racesData, stats, historyData] = await Promise.all([
    getTodayRaces(),
    getStats(),
    getRecentHistory(),
  ]);

  const today = formatDate(new Date().toISOString());

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">ダッシュボード</h1>
        <p className="text-gray-500 mt-1">{today}</p>
      </div>

      {/* Stats Overview */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
        <StatCard
          icon={<Calendar className="w-5 h-5 text-blue-600" />}
          label="本日のレース"
          value={`${racesData.total}件`}
        />
        <StatCard
          icon={<Target className="w-5 h-5 text-green-600" />}
          label="総予測数"
          value={stats ? `${stats.total_predictions.toLocaleString()}件` : '-'}
        />
        <StatCard
          icon={<TrendingUp className="w-5 h-5 text-purple-600" />}
          label="的中率"
          value={historyData?.summary ? formatPercent(historyData.summary.hit_rate) : '-'}
        />
        <StatCard
          icon={<DollarSign className="w-5 h-5 text-orange-600" />}
          label="回収率"
          value={historyData?.summary ? formatPercent(historyData.summary.roi + 100) : '-'}
        />
      </div>

      <div className="grid gap-8 lg:grid-cols-3">
        {/* Today's Races */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>本日のレース</CardTitle>
                <Link
                  href="/races"
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  すべて見る
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {racesData.races.length > 0 ? (
                <RaceList races={racesData.races.slice(0, 6)} />
              ) : (
                <div className="text-center py-8 text-gray-500">
                  本日のレースはありません
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Data Stats */}
          {stats && <ScrapeStatsCard stats={stats} />}

          {/* Recent History */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>最近の予想</CardTitle>
                <Link
                  href="/history"
                  className="text-sm text-blue-600 hover:text-blue-800"
                >
                  すべて見る
                </Link>
              </div>
            </CardHeader>
            <CardContent>
              {historyData && historyData.items.length > 0 ? (
                <div className="space-y-3">
                  {historyData.items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between py-2 border-b last:border-0"
                    >
                      <div>
                        <p className="text-sm font-medium">{item.bet_type}</p>
                        <p className="text-xs text-gray-500">{item.bet_detail}</p>
                      </div>
                      {item.is_hit !== null && (
                        <Badge variant={item.is_hit ? 'success' : 'danger'}>
                          {item.is_hit ? '的中' : 'ハズレ'}
                        </Badge>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-center py-4 text-gray-500 text-sm">
                  履歴がありません
                </p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gray-100 rounded-lg">{icon}</div>
          <div>
            <p className="text-sm text-gray-500">{label}</p>
            <p className="text-xl font-semibold text-gray-900">{value}</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
