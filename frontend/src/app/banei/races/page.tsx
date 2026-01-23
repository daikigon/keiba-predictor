'use client';

import { useState, useEffect } from 'react';
import { RaceList } from '@/components/features/race/RaceList';
import { Card, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { getRaces } from '@/lib/api';
import { formatDate } from '@/lib/utils';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import type { Race } from '@/types/race';

export default function RacesPage() {
  const [date, setDate] = useState(() => new Date().toISOString().split('T')[0]);
  const [races, setRaces] = useState<Race[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchRaces() {
      setIsLoading(true);
      setError(null);
      try {
        const data = await getRaces(date, 'banei');
        setRaces(data.races);
      } catch {
        setError('レースの取得に失敗しました');
        setRaces([]);
      } finally {
        setIsLoading(false);
      }
    }
    fetchRaces();
  }, [date]);

  const changeDate = (days: number) => {
    const current = new Date(date);
    current.setDate(current.getDate() + days);
    setDate(current.toISOString().split('T')[0]);
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">ばんえい競馬 レース一覧</h1>
      </div>

      {/* Date Selector */}
      <Card className="mb-6">
        <CardContent className="p-4">
          <div className="flex items-center justify-center gap-4">
            <Button
              variant="outline"
              size="sm"
              onClick={() => changeDate(-1)}
            >
              <ChevronLeft className="w-4 h-4" />
              前日
            </Button>
            <div className="text-center">
              <input
                type="date"
                value={date}
                onChange={(e) => setDate(e.target.value)}
                className="px-4 py-2 border rounded-lg text-center font-medium"
              />
              <p className="text-sm text-gray-500 mt-1">
                {formatDate(date)}
              </p>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => changeDate(1)}
            >
              翌日
              <ChevronRight className="w-4 h-4" />
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Race List */}
      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto"></div>
          <p className="text-gray-500 mt-4">読み込み中...</p>
        </div>
      ) : error ? (
        <div className="text-center py-12">
          <p className="text-red-500">{error}</p>
        </div>
      ) : (
        <RaceList races={races} baseUrl="/banei" />
      )}
    </div>
  );
}
