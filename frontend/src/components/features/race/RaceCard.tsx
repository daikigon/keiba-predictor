import Link from 'next/link';
import { cn } from '@/lib/utils';
import { Card, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { COURSE_COLORS, GRADE_COLORS, TRACK_TYPE_LABELS } from '@/lib/constants';
import type { Race } from '@/types/race';

interface RaceCardProps {
  race: Race;
}

export function RaceCard({ race }: RaceCardProps) {
  const courseColor = COURSE_COLORS[race.course] || 'bg-gray-100 text-gray-800';
  const gradeColor = race.grade ? GRADE_COLORS[race.grade] : null;

  return (
    <Link href={`/races/${race.race_id}`}>
      <Card className="hover:shadow-md transition-shadow cursor-pointer">
        <CardContent className="p-4">
          <div className="flex items-start justify-between">
            <div className="flex-1">
              <div className="flex items-center gap-2 mb-2">
                <span className={cn('px-2 py-0.5 text-xs rounded', courseColor)}>
                  {race.course}
                </span>
                <span className="text-sm text-gray-500">
                  {race.race_number}R
                </span>
                {race.grade && gradeColor && (
                  <span className={cn('px-2 py-0.5 text-xs rounded', gradeColor)}>
                    {race.grade}
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-gray-900 mb-1">
                {race.race_name || `${race.course}${race.race_number}R`}
              </h3>
              <div className="flex items-center gap-3 text-sm text-gray-600">
                <span>
                  {TRACK_TYPE_LABELS[race.track_type] || race.track_type}
                  {race.distance}m
                </span>
                {race.condition && (
                  <span>馬場: {race.condition}</span>
                )}
                {race.weather && (
                  <span>天気: {race.weather}</span>
                )}
              </div>
            </div>
            <div className="text-right">
              {race.entries && race.entries.length > 0 && (
                <Badge variant="info">{race.entries.length}頭</Badge>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </Link>
  );
}
