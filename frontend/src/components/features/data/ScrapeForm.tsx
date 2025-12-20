'use client';

import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  scrapeRaceList,
  scrapeRaceDetail,
  scrapeRaceCardList,
  scrapeRaceCardDetail,
} from '@/lib/api';
import {
  Download,
  Loader2,
  CheckCircle,
  XCircle,
  AlertCircle,
  SkipForward,
  Clock,
  Trash2,
  Calendar,
  CalendarDays,
} from 'lucide-react';

type ScrapeStatus = 'idle' | 'scraping_list' | 'scraping_details' | 'completed' | 'error';
type ScrapeMode = 'past' | 'today';
type DateMode = 'single' | 'range';

interface ScrapeProgress {
  total: number;
  current: number;
  currentRace: string;
  skipped: number;
  scraped: number;
  // For range mode
  currentDate?: string;
  totalDates?: number;
  currentDateIndex?: number;
}

interface SkippedRace {
  race_id: string;
  race_name: string;
  entries_count: number;
}

interface ScrapeHistory {
  date: string;
  scrapedAt: string;
  racesCount: number;
  scrapedCount: number;
  skippedCount: number;
  mode: ScrapeMode;
}

const HISTORY_KEY = 'scrape_history';
const MAX_HISTORY = 5;

function loadHistory(): ScrapeHistory[] {
  if (typeof window === 'undefined') return [];
  try {
    const saved = localStorage.getItem(HISTORY_KEY);
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
}

function saveHistory(history: ScrapeHistory[]) {
  if (typeof window === 'undefined') return;
  localStorage.setItem(HISTORY_KEY, JSON.stringify(history.slice(0, MAX_HISTORY)));
}

function getDateRange(startDate: string, endDate: string): string[] {
  const dates: string[] = [];
  const start = new Date(startDate);
  const end = new Date(endDate);

  for (let d = new Date(start); d <= end; d.setDate(d.getDate() + 1)) {
    dates.push(d.toISOString().split('T')[0]);
  }
  return dates;
}

export function ScrapeForm() {
  const [targetDate, setTargetDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [endDate, setEndDate] = useState(() => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  });
  const [mode, setMode] = useState<ScrapeMode>('today');
  const [dateMode, setDateMode] = useState<DateMode>('single');
  const [jraOnly, setJraOnly] = useState(false);
  const [forceOverwrite, setForceOverwrite] = useState(false);
  const [status, setStatus] = useState<ScrapeStatus>('idle');
  const [progress, setProgress] = useState<ScrapeProgress | null>(null);
  const [result, setResult] = useState<{
    racesCount: number;
    scrapedCount: number;
    skippedCount: number;
    entriesCount: number;
    skippedRaces: SkippedRace[];
    errors: string[];
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showSkippedList, setShowSkippedList] = useState(false);
  const [history, setHistory] = useState<ScrapeHistory[]>([]);

  // Load history on mount
  useEffect(() => {
    setHistory(loadHistory());
  }, []);

  const addToHistory = (entry: ScrapeHistory) => {
    const newHistory = [
      entry,
      ...history.filter(h => !(h.date === entry.date && h.mode === entry.mode)),
    ].slice(0, MAX_HISTORY);
    setHistory(newHistory);
    saveHistory(newHistory);
  };

  const clearHistory = () => {
    setHistory([]);
    localStorage.removeItem(HISTORY_KEY);
  };

  const handleScrape = async () => {
    setStatus('scraping_list');
    setProgress(null);
    setResult(null);
    setError(null);
    setShowSkippedList(false);

    // Select the appropriate API functions based on mode
    const scrapeList = mode === 'today' ? scrapeRaceCardList : scrapeRaceList;
    const scrapeDetail = mode === 'today' ? scrapeRaceCardDetail : scrapeRaceDetail;

    // Get dates to process
    const datesToProcess = dateMode === 'range' ? getDateRange(targetDate, endDate) : [targetDate];
    const totalDates = datesToProcess.length;

    try {
      let totalRacesCount = 0;
      let totalEntriesCount = 0;
      let totalSkippedCount = 0;
      let totalScrapedCount = 0;
      const allSkippedRaces: SkippedRace[] = [];
      const allErrors: string[] = [];

      for (let dateIndex = 0; dateIndex < datesToProcess.length; dateIndex++) {
        const currentDate = datesToProcess[dateIndex];

        // Step 1: Scrape race list for this date
        setStatus('scraping_list');
        setProgress({
          total: 0,
          current: 0,
          currentRace: '',
          skipped: totalSkippedCount,
          scraped: totalScrapedCount,
          currentDate,
          totalDates,
          currentDateIndex: dateIndex + 1,
        });

        const listResult = await scrapeList(currentDate, jraOnly);

        if (listResult.races_count === 0) {
          // No races for this date, continue to next
          continue;
        }

        totalRacesCount += listResult.races_count;

        // Step 2: Scrape each race detail
        setStatus('scraping_details');
        const races = listResult.races;

        for (let i = 0; i < races.length; i++) {
          const race = races[i];
          setProgress({
            total: races.length,
            current: i + 1,
            currentRace: race.race_name || race.race_id,
            skipped: totalSkippedCount,
            scraped: totalScrapedCount,
            currentDate,
            totalDates,
            currentDateIndex: dateIndex + 1,
          });

          try {
            const detailResult = await scrapeDetail(race.race_id, forceOverwrite);

            if (detailResult.skipped) {
              totalSkippedCount++;
              allSkippedRaces.push({
                race_id: detailResult.race.race_id,
                race_name: detailResult.race.race_name,
                entries_count: detailResult.race.entries_count || 0,
              });
            } else {
              totalScrapedCount++;
              totalEntriesCount += detailResult.race.entries?.length || 0;
            }
          } catch (e) {
            allErrors.push(`${race.race_id}: ${e instanceof Error ? e.message : 'Unknown error'}`);
          }

          // Rate limiting
          if (i < races.length - 1 || dateIndex < datesToProcess.length - 1) {
            await new Promise((resolve) => setTimeout(resolve, 500));
          }
        }
      }

      setStatus('completed');
      setResult({
        racesCount: totalRacesCount,
        scrapedCount: totalScrapedCount,
        skippedCount: totalSkippedCount,
        entriesCount: totalEntriesCount,
        skippedRaces: allSkippedRaces,
        errors: allErrors,
      });

      // Add to history (for range mode, use start date)
      addToHistory({
        date: dateMode === 'range' ? `${targetDate}~${endDate}` : targetDate,
        scrapedAt: new Date().toISOString(),
        racesCount: totalRacesCount,
        scrapedCount: totalScrapedCount,
        skippedCount: totalSkippedCount,
        mode,
      });
    } catch (e) {
      setStatus('error');
      setError(e instanceof Error ? e.message : 'スクレイピングに失敗しました');
    }
  };

  const isLoading = status === 'scraping_list' || status === 'scraping_details';

  const formatDate = (dateStr: string) => {
    // Handle range format like "2024-12-01~2024-12-15"
    if (dateStr.includes('~')) {
      const [start, end] = dateStr.split('~');
      const startDate = new Date(start);
      const endDate = new Date(end);
      return `${startDate.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })}~${endDate.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' })}`;
    }
    const date = new Date(dateStr);
    return date.toLocaleDateString('ja-JP', { month: 'short', day: 'numeric' });
  };

  const formatDateTime = (isoStr: string) => {
    const date = new Date(isoStr);
    return date.toLocaleString('ja-JP', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Download className="w-5 h-5" />
          レースデータ取得
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          {/* Mode Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">データソース</label>
            <div className="flex gap-2">
              <button
                onClick={() => setMode('today')}
                disabled={isLoading}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  mode === 'today'
                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                    : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                } disabled:opacity-50`}
              >
                <CalendarDays className="w-4 h-4" />
                当日レース（出馬表）
              </button>
              <button
                onClick={() => setMode('past')}
                disabled={isLoading}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  mode === 'past'
                    ? 'bg-blue-50 border-blue-300 text-blue-700'
                    : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                } disabled:opacity-50`}
              >
                <Calendar className="w-4 h-4" />
                過去レース（結果）
              </button>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              {mode === 'today'
                ? 'race.netkeiba.com から当日・直近の出馬表を取得（予想用）'
                : 'db.netkeiba.com から過去のレース結果を取得（学習用）'}
            </p>
          </div>

          {/* Date Mode Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">日付指定方法</label>
            <div className="flex gap-2">
              <button
                onClick={() => setDateMode('single')}
                disabled={isLoading}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  dateMode === 'single'
                    ? 'bg-green-50 border-green-300 text-green-700'
                    : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                } disabled:opacity-50`}
              >
                単一日
              </button>
              <button
                onClick={() => setDateMode('range')}
                disabled={isLoading}
                className={`flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border text-sm font-medium transition-colors ${
                  dateMode === 'range'
                    ? 'bg-green-50 border-green-300 text-green-700'
                    : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                } disabled:opacity-50`}
              >
                日付範囲
              </button>
            </div>
          </div>

          {/* Date Selection */}
          <div className={dateMode === 'range' ? 'grid grid-cols-2 gap-4' : ''}>
            <div>
              <label htmlFor="target-date" className="block text-sm font-medium text-gray-700 mb-1">
                {dateMode === 'range' ? '開始日' : '取得対象日'}
              </label>
              <input
                type="date"
                id="target-date"
                value={targetDate}
                onChange={(e) => setTargetDate(e.target.value)}
                disabled={isLoading}
                className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
              />
            </div>
            {dateMode === 'range' && (
              <div>
                <label htmlFor="end-date" className="block text-sm font-medium text-gray-700 mb-1">
                  終了日
                </label>
                <input
                  type="date"
                  id="end-date"
                  value={endDate}
                  onChange={(e) => setEndDate(e.target.value)}
                  disabled={isLoading}
                  min={targetDate}
                  className="block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
                />
              </div>
            )}
          </div>

          {/* JRA Only Option */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="jra-only"
              checked={jraOnly}
              onChange={(e) => setJraOnly(e.target.checked)}
              disabled={isLoading}
              className="h-4 w-4 text-green-600 border-gray-300 rounded focus:ring-green-500 disabled:opacity-50"
            />
            <label htmlFor="jra-only" className="text-sm text-gray-700">
              中央競馬のみ取得（地方競馬を除外）
            </label>
          </div>

          {/* Force Overwrite Option */}
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="force-overwrite"
              checked={forceOverwrite}
              onChange={(e) => setForceOverwrite(e.target.checked)}
              disabled={isLoading}
              className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 disabled:opacity-50"
            />
            <label htmlFor="force-overwrite" className="text-sm text-gray-700">
              既存データを上書き更新（オッズ更新など）
            </label>
          </div>

          {/* History */}
          {history.length > 0 && (
            <div className="p-3 bg-gray-50 rounded-lg">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-1 text-sm font-medium text-gray-700">
                  <Clock className="w-4 h-4" />
                  取得履歴
                </div>
                <button
                  onClick={clearHistory}
                  className="text-xs text-gray-400 hover:text-gray-600 flex items-center gap-1"
                  title="履歴をクリア"
                >
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
              <div className="flex flex-wrap gap-2">
                {history.map((h, idx) => (
                  <button
                    key={`${h.date}-${h.mode}-${idx}`}
                    onClick={() => {
                      // Handle range format like "2024-12-01~2024-12-15"
                      if (h.date.includes('~')) {
                        const [start, end] = h.date.split('~');
                        setTargetDate(start);
                        setEndDate(end);
                        setDateMode('range');
                      } else {
                        setTargetDate(h.date);
                        setDateMode('single');
                      }
                      setMode(h.mode);
                    }}
                    disabled={isLoading}
                    className={`px-2 py-1 text-xs rounded border transition-colors ${
                      ((h.date.includes('~') && dateMode === 'range' && h.date === `${targetDate}~${endDate}`) ||
                       (!h.date.includes('~') && dateMode === 'single' && h.date === targetDate)) &&
                      mode === h.mode
                        ? 'bg-blue-100 border-blue-300 text-blue-700'
                        : 'bg-white border-gray-200 text-gray-600 hover:border-gray-300'
                    } disabled:opacity-50`}
                    title={`取得日時: ${formatDateTime(h.scrapedAt)}\n${h.racesCount}R (新規${h.scrapedCount}/スキップ${h.skippedCount})`}
                  >
                    {formatDate(h.date)}
                    <span className="ml-1 text-gray-400">
                      ({h.scrapedCount}/{h.racesCount})
                    </span>
                    <span
                      className={`ml-1 px-1 rounded text-[10px] ${
                        h.mode === 'today' ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-500'
                      }`}
                    >
                      {h.mode === 'today' ? '当日' : '過去'}
                    </span>
                  </button>
                ))}
              </div>
            </div>
          )}

          <Button onClick={handleScrape} disabled={isLoading || !targetDate} className="w-full">
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                {status === 'scraping_list' ? 'レース一覧を取得中...' : 'レース詳細を取得中...'}
              </>
            ) : (
              <>
                <Download className="w-4 h-4 mr-2" />
                {mode === 'today' ? '出馬表を取得' : 'データを取得'}
              </>
            )}
          </Button>

          {/* Progress */}
          {progress && (status === 'scraping_list' || status === 'scraping_details') && (
            <div className="p-4 bg-blue-50 rounded-lg">
              {/* Date progress for range mode */}
              {progress.totalDates && progress.totalDates > 1 && (
                <div className="mb-3 pb-3 border-b border-blue-200">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-blue-700">
                      日付: {progress.currentDateIndex} / {progress.totalDates} ({progress.currentDate})
                    </span>
                  </div>
                  <div className="w-full bg-blue-200 rounded-full h-1.5">
                    <div
                      className="bg-blue-400 h-1.5 rounded-full transition-all"
                      style={{ width: `${((progress.currentDateIndex || 0) / progress.totalDates) * 100}%` }}
                    />
                  </div>
                </div>
              )}
              {status === 'scraping_details' && progress.total > 0 && (
                <>
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-medium text-blue-700">
                      {progress.current} / {progress.total} レース
                    </span>
                    <span className="text-sm text-blue-600">
                      {Math.round((progress.current / progress.total) * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-blue-200 rounded-full h-2">
                    <div
                      className="bg-blue-600 h-2 rounded-full transition-all"
                      style={{ width: `${(progress.current / progress.total) * 100}%` }}
                    />
                  </div>
                  <div className="mt-2 flex justify-between text-xs">
                    <span className="text-blue-600 truncate flex-1">処理中: {progress.currentRace}</span>
                    <span className="text-gray-500 ml-2">
                      取得: {progress.scraped} / スキップ: {progress.skipped}
                    </span>
                  </div>
                </>
              )}
              {status === 'scraping_list' && (
                <div className="text-sm text-blue-700">
                  レース一覧を取得中...
                  {progress.currentDate && ` (${progress.currentDate})`}
                </div>
              )}
            </div>
          )}

          {/* Result */}
          {status === 'completed' && result && (
            <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
              <div className="flex items-start gap-3">
                <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-green-800">取得完了</p>
                  {result.racesCount > 0 ? (
                    <div className="text-sm text-green-700 mt-1 space-y-1">
                      <p>全{result.racesCount}レース中:</p>
                      <ul className="list-disc list-inside ml-2">
                        <li>
                          新規取得: {result.scrapedCount}レース ({result.entriesCount}頭)
                        </li>
                        {result.skippedCount > 0 && (
                          <li className="text-gray-600">
                            スキップ: {result.skippedCount}レース (既存データ)
                          </li>
                        )}
                      </ul>
                    </div>
                  ) : (
                    <p className="text-sm text-green-700 mt-1">
                      指定日のレースデータはありませんでした
                    </p>
                  )}

                  {/* Skipped races list */}
                  {result.skippedCount > 0 && (
                    <div className="mt-3">
                      <button
                        onClick={() => setShowSkippedList(!showSkippedList)}
                        className="flex items-center gap-1 text-sm text-gray-600 hover:text-gray-800"
                      >
                        <SkipForward className="w-4 h-4" />
                        スキップしたレースを{showSkippedList ? '隠す' : '表示'}
                      </button>
                      {showSkippedList && (
                        <div className="mt-2 p-2 bg-gray-50 rounded text-xs max-h-40 overflow-y-auto">
                          {result.skippedRaces.map((race) => (
                            <div key={race.race_id} className="py-1 border-b last:border-0">
                              <span className="font-mono text-gray-500">{race.race_id}</span>
                              <span className="ml-2 text-gray-700">{race.race_name}</span>
                              <span className="ml-2 text-gray-400">({race.entries_count}頭)</span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}

                  {result.errors.length > 0 && (
                    <div className="mt-2 p-2 bg-yellow-50 rounded text-xs text-yellow-700">
                      <p className="font-medium">{result.errors.length}件のエラー:</p>
                      {result.errors.slice(0, 3).map((err, i) => (
                        <p key={i} className="truncate">
                          {err}
                        </p>
                      ))}
                      {result.errors.length > 3 && <p>...他 {result.errors.length - 3}件</p>}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}

          {/* Error */}
          {status === 'error' && error && (
            <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
              <div className="flex items-start gap-3">
                <XCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-red-800">エラーが発生しました</p>
                  <p className="text-sm text-red-700 mt-1">{error}</p>
                </div>
              </div>
            </div>
          )}

          {/* Warning */}
          <div className={`p-3 border rounded-lg ${forceOverwrite ? 'bg-orange-50 border-orange-200' : 'bg-yellow-50 border-yellow-200'}`}>
            <div className="flex items-start gap-2">
              <AlertCircle className={`w-4 h-4 flex-shrink-0 mt-0.5 ${forceOverwrite ? 'text-orange-600' : 'text-yellow-600'}`} />
              <p className={`text-xs ${forceOverwrite ? 'text-orange-700' : 'text-yellow-700'}`}>
                {forceOverwrite
                  ? '上書きモード: 既存データを最新の情報で上書きします。全レースの取得には数分かかる場合があります。'
                  : '既に出走馬データがあるレースは自動的にスキップされます。全レースの取得には数分かかる場合があります。'}
              </p>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
