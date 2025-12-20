'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { useParams } from 'next/navigation';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';
import { getHorseDetail } from '@/lib/api';
import type { HorseDetail } from '@/lib/api';
import { ArrowLeft } from 'lucide-react';

export default function HorseDetailPage() {
  const params = useParams();
  const horseId = params.id as string;
  const [horse, setHorse] = useState<HorseDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function fetchHorse() {
      setIsLoading(true);
      try {
        const data = await getHorseDetail(horseId);
        setHorse(data);
      } catch (err) {
        setError('競走馬データの取得に失敗しました');
        console.error('Failed to fetch horse:', err);
      } finally {
        setIsLoading(false);
      }
    }
    if (horseId) {
      fetchHorse();
    }
  }, [horseId]);

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
        </div>
      </div>
    );
  }

  if (error || !horse) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="text-center py-12 text-gray-500">
          {error || '競走馬が見つかりません'}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <Link
          href="/horses"
          className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          競走馬一覧に戻る
        </Link>
        <h1 className="text-2xl font-bold text-gray-900">{horse.name}</h1>
        <p className="text-gray-500 mt-1">競走馬詳細情報</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2 mb-8">
        {/* Basic Info */}
        <Card>
          <CardHeader>
            <CardTitle>基本情報</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
              <InfoRow label="馬名" value={horse.name} />
              <InfoRow
                label="性別"
                value={
                  <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                    horse.sex === '牡' ? 'bg-blue-100 text-blue-800' :
                    horse.sex === '牝' ? 'bg-pink-100 text-pink-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {horse.sex === '牡' ? '牡（オス）' :
                     horse.sex === '牝' ? '牝（メス）' :
                     'セン馬'}
                  </span>
                }
              />
              <InfoRow label="生年" value={horse.birth_year?.toString() || '-'} />
              <InfoRow label="調教師" value={horse.trainer || '-'} />
              <InfoRow label="馬主" value={horse.owner || '-'} />
            </dl>
          </CardContent>
        </Card>

        {/* Bloodline */}
        <Card>
          <CardHeader>
            <CardTitle>血統情報</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
              <InfoRow label="父" value={horse.father || '-'} />
              <InfoRow label="母" value={horse.mother || '-'} />
              <InfoRow label="母父" value={horse.mother_father || '-'} />
            </dl>
          </CardContent>
        </Card>
      </div>

      {/* Race History */}
      <Card>
        <CardHeader>
          <CardTitle>出走履歴 (直近20件)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {horse.race_history.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              出走履歴がありません
            </div>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>日付</TableHead>
                  <TableHead>レース名</TableHead>
                  <TableHead>コース</TableHead>
                  <TableHead className="text-center">馬番</TableHead>
                  <TableHead className="text-center">着順</TableHead>
                  <TableHead className="text-center">人気</TableHead>
                  <TableHead className="text-right">オッズ</TableHead>
                  <TableHead>騎手</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {horse.race_history.map((race, index) => (
                  <TableRow key={`${race.race_id}-${index}`}>
                    <TableCell className="text-gray-500 text-sm">
                      {race.date || '-'}
                    </TableCell>
                    <TableCell className="font-medium">
                      <Link
                        href={`/races/${race.race_id}`}
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
                    <TableCell className="text-gray-600">
                      {race.jockey_name || '-'}
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

function InfoRow({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between py-2 border-b last:border-0">
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-900">{value}</dd>
    </div>
  );
}
