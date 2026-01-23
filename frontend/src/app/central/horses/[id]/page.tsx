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
import { getHorseDetail, rescrapeHorseData } from '@/lib/api';
import type { HorseDetail, RescrapeResult } from '@/lib/api';
import { ArrowLeft, RefreshCw } from 'lucide-react';

export default function HorseDetailPage() {
  const params = useParams();
  const horseId = params.id as string;
  const [horse, setHorse] = useState<HorseDetail | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isRescraping, setIsRescraping] = useState(false);
  const [rescrapeResult, setRescrapeResult] = useState<RescrapeResult | null>(null);

  const fetchHorse = async () => {
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
  };

  useEffect(() => {
    if (horseId) {
      fetchHorse();
    }
  }, [horseId]);

  const handleRescrape = async () => {
    setIsRescraping(true);
    setRescrapeResult(null);
    try {
      const result = await rescrapeHorseData(horseId);
      setRescrapeResult(result);
      // Refresh horse data after successful rescrape
      await fetchHorse();
    } catch (err) {
      console.error('Failed to rescrape:', err);
      setRescrapeResult({
        success: false,
        horse_id: horseId,
        horse_name: horse?.name || '',
        scraped_races: 0,
        updated_entries: 0,
        created_entries: 0,
        updated_races: 0,
        created_races: 0,
      });
    } finally {
      setIsRescraping(false);
    }
  };

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
          href="/central/horses"
          className="inline-flex items-center text-blue-600 hover:text-blue-800 mb-4"
        >
          <ArrowLeft className="w-4 h-4 mr-1" />
          競走馬一覧に戻る
        </Link>
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900">{horse.name}</h1>
            <p className="text-gray-500 mt-1">競走馬詳細情報</p>
          </div>
          <button
            onClick={handleRescrape}
            disabled={isRescraping}
            className="inline-flex items-center px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${isRescraping ? 'animate-spin' : ''}`} />
            {isRescraping ? '取得中...' : 'データ補完'}
          </button>
        </div>

        {/* Rescrape Result */}
        {rescrapeResult && (
          <div className={`mt-4 p-4 rounded-lg ${rescrapeResult.success ? 'bg-green-50 text-green-800' : 'bg-red-50 text-red-800'}`}>
            {rescrapeResult.success ? (
              <div>
                <p className="font-medium">データ補完完了</p>
                <p className="text-sm mt-1">
                  スクレイピング: {rescrapeResult.scraped_races}レース /
                  新規作成: {rescrapeResult.created_entries}件のEntry, {rescrapeResult.created_races}件のRace /
                  更新: {rescrapeResult.updated_entries}件のEntry, {rescrapeResult.updated_races}件のRace
                </p>
              </div>
            ) : (
              <p className="font-medium">データ補完に失敗しました</p>
            )}
          </div>
        )}
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
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>日付</TableHead>
                    <TableHead>開催</TableHead>
                    <TableHead>天気</TableHead>
                    <TableHead className="text-center">頭数</TableHead>
                    <TableHead className="text-center">R</TableHead>
                    <TableHead>レース名</TableHead>
                    <TableHead className="text-center">着順</TableHead>
                    <TableHead className="text-center">枠</TableHead>
                    <TableHead className="text-center">馬番</TableHead>
                    <TableHead className="text-right">オッズ</TableHead>
                    <TableHead className="text-center">人気</TableHead>
                    <TableHead>着差</TableHead>
                    <TableHead>騎手</TableHead>
                    <TableHead className="text-right">斤量</TableHead>
                    <TableHead>距離</TableHead>
                    <TableHead>馬場</TableHead>
                    <TableHead className="text-right">タイム</TableHead>
                    <TableHead>通過</TableHead>
                    <TableHead>ペース</TableHead>
                    <TableHead className="text-right">上り</TableHead>
                    <TableHead className="text-right">馬体重</TableHead>
                    <TableHead>勝ち馬</TableHead>
                    <TableHead className="text-right">賞金</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {[...horse.race_history]
                    .sort((a, b) => {
                      // 日付の降順でソート（最新が上）
                      if (!a.date) return 1;
                      if (!b.date) return -1;
                      return b.date.localeCompare(a.date);
                    })
                    .map((race, index) => (
                    <TableRow key={`${race.race_id}-${index}`}>
                      <TableCell className="text-gray-500 text-sm whitespace-nowrap">
                        {race.date || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 text-sm whitespace-nowrap">
                        {race.venue_detail || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 text-sm">
                        {race.weather || '-'}
                      </TableCell>
                      <TableCell className="text-center text-gray-600">
                        {race.num_horses || '-'}
                      </TableCell>
                      <TableCell className="text-center text-gray-600">
                        {race.race_number || '-'}
                      </TableCell>
                      <TableCell className="font-medium whitespace-nowrap">
                        <Link
                          href={`/central/races/${race.race_id}`}
                          className="text-blue-600 hover:text-blue-800"
                        >
                          {race.race_name}
                        </Link>
                      </TableCell>
                      <TableCell className="text-center">
                        {race.result ? (
                          <span className={`font-medium ${
                            race.result === 1 ? 'text-yellow-600' :
                            race.result === 2 ? 'text-gray-500' :
                            race.result === 3 ? 'text-orange-600' :
                            'text-gray-600'
                          }`}>
                            {race.result}
                          </span>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-center text-gray-600">
                        {race.frame_number || '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        {race.horse_number}
                      </TableCell>
                      <TableCell className="text-right">
                        {race.odds || '-'}
                      </TableCell>
                      <TableCell className="text-center text-gray-600">
                        {race.popularity || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 text-sm">
                        {race.margin || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 whitespace-nowrap">
                        {race.jockey_name || '-'}
                      </TableCell>
                      <TableCell className="text-right text-gray-600">
                        {race.weight || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 whitespace-nowrap">
                        {race.track_type}{race.distance}
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {race.condition || '-'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-gray-600">
                        {race.finish_time || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 text-sm">
                        {race.corner_position || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 text-sm whitespace-nowrap">
                        {race.pace || '-'}
                      </TableCell>
                      <TableCell className="text-right font-mono text-gray-600">
                        {race.last_3f ? race.last_3f.toFixed(1) : '-'}
                      </TableCell>
                      <TableCell className="text-right text-gray-600 whitespace-nowrap">
                        {race.horse_weight ? (
                          <>
                            {race.horse_weight}
                            {race.weight_diff !== undefined && race.weight_diff !== null && (
                              <span className={`ml-1 text-xs ${
                                race.weight_diff > 0 ? 'text-red-500' :
                                race.weight_diff < 0 ? 'text-blue-500' :
                                'text-gray-400'
                              }`}>
                                ({race.weight_diff > 0 ? '+' : ''}{race.weight_diff})
                              </span>
                            )}
                          </>
                        ) : '-'}
                      </TableCell>
                      <TableCell className="text-gray-600 text-sm whitespace-nowrap">
                        {race.winner_or_second || '-'}
                      </TableCell>
                      <TableCell className="text-right text-gray-600">
                        {race.prize_money ? `${race.prize_money.toLocaleString()}` : '-'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
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
