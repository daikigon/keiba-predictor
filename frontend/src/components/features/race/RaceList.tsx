import { RaceCard } from './RaceCard';
import type { Race } from '@/types/race';

interface RaceListProps {
  races: Race[];
  baseUrl?: string;
}

export function RaceList({ races, baseUrl = '/central' }: RaceListProps) {
  if (races.length === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-gray-500">レースが見つかりません</p>
      </div>
    );
  }

  // Group by course
  const racesByCourse = races.reduce((acc, race) => {
    if (!acc[race.course]) {
      acc[race.course] = [];
    }
    acc[race.course].push(race);
    return acc;
  }, {} as Record<string, Race[]>);

  return (
    <div className="space-y-8">
      {Object.entries(racesByCourse).map(([course, courseRaces]) => (
        <div key={course}>
          <h2 className="text-lg font-semibold text-gray-900 mb-4">{course}</h2>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {courseRaces
              .sort((a, b) => a.race_number - b.race_number)
              .map((race) => (
                <RaceCard key={race.race_id} race={race} baseUrl={baseUrl} />
              ))}
          </div>
        </div>
      ))}
    </div>
  );
}
