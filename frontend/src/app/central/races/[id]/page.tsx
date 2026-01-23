import Link from 'next/link';
import { notFound } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { EntryTable } from '@/components/features/race/EntryTable';
import { PredictionPanel } from '@/components/features/prediction/PredictionPanel';
import { getRaceDetail, getPrediction } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { cn } from '@/lib/utils';
import { COURSE_COLORS, GRADE_COLORS, TRACK_TYPE_LABELS } from '@/lib/constants';
import { ArrowLeft } from 'lucide-react';

interface PageProps {
  params: Promise<{ id: string }>;
}

export const dynamic = 'force-dynamic';

export default async function RaceDetailPage({ params }: PageProps) {
  const { id } = await params;

  let race;
  let prediction;

  try {
    [race, prediction] = await Promise.all([
      getRaceDetail(id),
      getPrediction(id),
    ]);
  } catch {
    notFound();
  }

  if (!race) {
    notFound();
  }

  const courseColor = COURSE_COLORS[race.course] || 'bg-gray-100 text-gray-800';
  const gradeColor = race.grade ? GRADE_COLORS[race.grade] : null;
  const hasResult = race.entries?.some((e) => e.result !== null && e.result !== undefined);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Back Link */}
      <Link
        href="/central/races"
        className="inline-flex items-center text-sm text-gray-600 hover:text-gray-900 mb-6"
      >
        <ArrowLeft className="w-4 h-4 mr-1" />
        レース一覧に戻る
      </Link>

      {/* Race Header */}
      <div className="mb-8">
        <div className="flex flex-wrap items-center gap-2 mb-2">
          <span className={cn('px-3 py-1 text-sm rounded-full', courseColor)}>
            {race.course}
          </span>
          <span className="text-gray-500">{race.race_number}R</span>
          {race.grade && gradeColor && (
            <span className={cn('px-3 py-1 text-sm rounded-full', gradeColor)}>
              {race.grade}
            </span>
          )}
        </div>
        <h1 className="text-2xl font-bold text-gray-900 mb-2">
          {race.race_name || `${race.course}${race.race_number}R`}
        </h1>
        <div className="flex flex-wrap items-center gap-4 text-gray-600">
          <span>{formatDate(race.date)}</span>
          <span>
            {TRACK_TYPE_LABELS[race.track_type] || race.track_type}
            {race.distance}m
          </span>
          {race.condition && <span>馬場: {race.condition}</span>}
          {race.weather && <span>天気: {race.weather}</span>}
          {race.entries && (
            <Badge variant="info">{race.entries.length}頭出走</Badge>
          )}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-3">
        {/* Entry Table */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>出馬表</CardTitle>
            </CardHeader>
            <CardContent className="p-0">
              {race.entries && race.entries.length > 0 ? (
                <EntryTable entries={race.entries} showResult={hasResult} />
              ) : (
                <div className="text-center py-8 text-gray-500">
                  出走馬情報がありません
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Prediction Panel */}
        <div>
          <PredictionPanel raceId={id} initialPrediction={prediction} />
        </div>
      </div>
    </div>
  );
}
