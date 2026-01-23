'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';
import { getJockeyDetail } from '@/lib/api';
import type { JockeyDetail } from '@/lib/api';
import { ArrowLeft } from 'lucide-react';

export default function JockeyDetailPage() {
  const params = useParams();
  const jockeyId = params.id as string;
  const [jockey, setJockey] = useState<JockeyDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchJockey() {
      setIsLoading(true);
      try {
        const data = await getJockeyDetail(jockeyId);
        setJockey(data);
      } catch (err) {
        setError('騎手データの取得に失敗しました');
        console.error('Failed to fetch jockey:', err);
      } finally {
        setIsLoading(false);
      }
    }
    if (jockeyId) {
      fetchJockey();
    }
  }, [jockeyId]);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  if (error || !jockey) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 text-gray-500">
          {error || '騎手が見つかりません'}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <Link
          href="/central/jockeys"
          className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          騎手一覧に戻る
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">{jockey.name}</h1>
        <p className="text-gray-500 mt-1">騎手詳細情報</p>
      </div>

      {/* Stats Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5 mb-8">
        <StatCard
          label="総騎乗数"
          value={jockey.stats.total_entries.toLocaleString()}
        />
        <StatCard
          label="勝利数"
          value={jockey.stats.wins.toLocaleString()}
        />
        <StatCard
          label="勝率"
          value={`${jockey.stats.win_rate}%`}
          highlight={jockey.stats.win_rate >= 10}
        />
        <StatCard
          label="連対率"
          value={`${jockey.stats.place_rate}%`}
          highlight={jockey.stats.place_rate >= 20}
        />
        <StatCard
          label="複勝率"
          value={`${jockey.stats.show_rate}%`}
          highlight={jockey.stats.show_rate >= 30}
        />
      </div>

      {/* Race History */}
      <Card>
        <CardHeader>
          <CardTitle>騎乗履歴 (直近30件)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {jockey.race_history.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              騎乗履歴がありません
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>日付</TableHead>
                  <TableHead>レース名</TableHead>
                  <TableHead>コース</TableHead>
                  <TableHead className="text-center">馬番</TableHead>
                  <TableHead>騎乗馬</TableHead>
                  <TableHead className="text-center">着順</TableHead>
                  <TableHead className="text-center">人気</TableHead>
                  <TableHead className="text-right">オッズ</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {jockey.race_history.map((race, index) => (
                  <TableRow key={`${race.race_id}-${index}`}>
                    <TableCell className="text-gray-500 text-sm">
                      {race.date || '-'}
                    </TableCell>
                    <TableCell className="font-medium">
                      <Link
                        href={`/central/races/${race.race_id}`}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        {race.race_name}
                      </Link>
                    </TableCell>
                    <TableCell className="text-gray-600">
                      {race.course} {race.track_type} {race.distance}m
                    </TableCell>
                    <TableCell className="text-center">
                      {race.horse_number}
                    </TableCell>
                    <TableCell className="text-gray-600">
                      {race.horse_name || '-'}
                    </TableCell>
                    <TableCell className="text-center">
                      {race.result ? (
                        <span className={`font-medium ${
                          race.result === 1 ? 'text-yellow-600' :
                          race.result === 2 ? 'text-gray-500' :
                          race.result === 3 ? 'text-orange-600' :
                          'text-gray-600'
                        }`}>
                          {race.result}着
                        </span>
                      ) : '-'}
                    </TableCell>
                    <TableCell className="text-center">
                      {race.popularity ? `${race.popularity}人気` : '-'}
                    </TableCell>
                    <TableCell className="text-right">
                      {race.odds || '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatCard({
  label,
  value,
  highlight = false,
}: {
  label: string;
  value: string;
  highlight?: boolean;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-gray-500">{label}</p>
        <p className={`text-2xl font-bold ${highlight ? 'text-green-600' : 'text-gray-900'}`}>
          {value}
        </p>
      </CardContent>
    </Card>
  );
}
