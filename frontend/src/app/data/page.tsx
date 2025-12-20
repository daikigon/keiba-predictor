import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { ScrapeStatsCard } from '@/components/features/prediction/StatsCard';
import { ScrapeForm } from '@/components/features/data/ScrapeForm';
import { getScrapeStats } from '@/lib/api';
import { Database, Calendar, Users } from 'lucide-react';

export const dynamic = 'force-dynamic';

async function getStats() {
  try {
    return await getScrapeStats();
  } catch {
    return null;
  }
}

export default async function DataPage() {
  const stats = await getStats();

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">データ管理</h1>
        <p className="text-gray-500 mt-1">レースデータのスクレイピングと状況確認</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        {/* Scrape Form */}
        <ScrapeForm />

        {/* Stats Overview */}
        {stats ? (
          <Card>
            <CardHeader>
              <CardTitle>データベース統計</CardTitle>
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
            <CardContent className="py-12 text-center">
              <p className="text-gray-500">データを取得できませんでした</p>
              <p className="text-sm text-gray-400 mt-1">
                バックエンドサーバーが起動しているか確認してください
              </p>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Instructions */}
      <Card>
        <CardHeader>
          <CardTitle>コマンドラインからのデータ取得</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-6">
            <div>
              <h4 className="font-medium text-gray-900 mb-2">
                一括データ投入
              </h4>
              <div className="bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <p># デモデータを作成</p>
                <p className="text-green-400">python scripts/init_data.py --demo</p>
                <p className="mt-2"># 過去7日分のデータをスクレイピング</p>
                <p className="text-green-400">python scripts/init_data.py --days 7</p>
                <p className="mt-2"># 期間指定でスクレイピング</p>
                <p className="text-green-400">python scripts/init_data.py --from 2024-12-01 --to 2024-12-22</p>
              </div>
            </div>

            <div>
              <h4 className="font-medium text-gray-900 mb-2">
                モデル学習
              </h4>
              <div className="bg-gray-900 text-gray-100 p-4 rounded-lg font-mono text-sm overflow-x-auto">
                <p># モデルを学習</p>
                <p className="text-green-400">python ml/train.py</p>
                <p className="mt-2"># モデルを評価</p>
                <p className="text-green-400">python ml/evaluate.py --detail</p>
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
