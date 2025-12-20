import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { formatPercent } from '@/lib/utils';
import type { AccuracyStats, ScrapeStats } from '@/types/prediction';

interface AccuracyStatsCardProps {
  stats: AccuracyStats;
}

export function AccuracyStatsCard({ stats }: AccuracyStatsCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>予測精度</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <StatItem label="予測数" value={stats.total_predictions.toString()} />
          <StatItem label="1着的中率" value={formatPercent(stats.win_accuracy)} />
          <StatItem label="複勝的中率" value={formatPercent(stats.show_accuracy)} />
          <StatItem label="Top3平均" value={stats.avg_top3_hit.toFixed(2)} />
        </div>
      </CardContent>
    </Card>
  );
}

interface ScrapeStatsCardProps {
  stats: ScrapeStats;
}

export function ScrapeStatsCard({ stats }: ScrapeStatsCardProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>データ状況</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          <StatItem label="レース数" value={stats.total_races.toLocaleString()} />
          <StatItem label="出走数" value={stats.total_entries.toLocaleString()} />
          <StatItem label="馬数" value={stats.total_horses.toLocaleString()} />
          <StatItem label="騎手数" value={stats.total_jockeys.toLocaleString()} />
          <StatItem label="予測数" value={stats.total_predictions.toLocaleString()} />
          {stats.latest_race_date && (
            <StatItem label="最新レース" value={stats.latest_race_date} />
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function StatItem({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-lg font-semibold text-gray-900">{value}</p>
    </div>
  );
}
