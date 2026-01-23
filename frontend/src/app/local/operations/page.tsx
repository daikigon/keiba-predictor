'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  Database,
  Cloud,
  Monitor,
  Play,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Calendar,
  ExternalLink,
  Info,
  History,
  Trash2,
} from 'lucide-react';
import { getEnvironment, isLocalEnvironment } from '@/lib/environment';

type DataStats = {
  races: number;
  entries: number;
  horses: number;
  jockeys: number;
  predictions: number;
};

type ScrapeHistoryItem = {
  id: string;
  startDate: string;
  endDate: string;
  executedAt: string;
  status: 'success' | 'error';
  message: string;
  racesCount?: number;
};

const SCRAPE_HISTORY_KEY = 'keiba_scrape_history';

function loadScrapeHistory(): ScrapeHistoryItem[] {
  if (typeof window === 'undefined') return [];
  try {
    const saved = localStorage.getItem(SCRAPE_HISTORY_KEY);
    return saved ? JSON.parse(saved) : [];
  } catch {
    return [];
  }
}

function saveScrapeHistory(history: ScrapeHistoryItem[]) {
  if (typeof window === 'undefined') return;
  // 最新50件のみ保持
  const trimmed = history.slice(0, 50);
  localStorage.setItem(SCRAPE_HISTORY_KEY, JSON.stringify(trimmed));
}

export default function OperationsPage() {
  const [environment] = useState(getEnvironment());
  const [stats, setStats] = useState<DataStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [scrapeStatus, setScrapeStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [scrapeMessage, setScrapeMessage] = useState('');
  const [scrapeHistory, setScrapeHistory] = useState<ScrapeHistoryItem[]>([]);
  const [scrapeProgress, setScrapeProgress] = useState<{
    type: string;
    currentDate?: string;
    currentDateIndex?: number;
    totalDates?: number;
    current?: number;
    total?: number;
    raceName?: string;
    raceId?: string;
    scraped: number;
    skipped: number;
  } | null>(null);

  // 日付選択用
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');
  // オプション
  const [jraOnly, setJraOnly] = useState(true);
  const [forceOverwrite, setForceOverwrite] = useState(false);

  // 履歴をlocalStorageから読み込み
  useEffect(() => {
    setScrapeHistory(loadScrapeHistory());
  }, []);

  const addToHistory = useCallback((item: ScrapeHistoryItem) => {
    setScrapeHistory(prev => {
      const newHistory = [item, ...prev];
      saveScrapeHistory(newHistory);
      return newHistory;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setScrapeHistory([]);
    localStorage.removeItem(SCRAPE_HISTORY_KEY);
  }, []);

  useEffect(() => {
    fetchStats();
    // デフォルト日付を設定
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);
    setEndDate(yesterday.toISOString().split('T')[0]);
    setStartDate(yesterday.toISOString().split('T')[0]);
  }, []);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const res = await fetch('/api/stats');
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };

  const runScraping = async () => {
    if (!isLocalEnvironment()) {
      setScrapeMessage('クラウド環境ではスクレイピングを実行できません');
      setScrapeStatus('error');
      return;
    }

    setScrapeStatus('running');
    setScrapeMessage('スクレイピングを開始しています...');
    setScrapeProgress({ type: 'starting', scraped: 0, skipped: 0 });

    const executedAt = new Date().toISOString();
    let finalScraped = 0;
    let finalSkipped = 0;

    try {
      const res = await fetch('/api/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ startDate, endDate, jraOnly, forceOverwrite, stream: true }),
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.message || 'エラーが発生しました');
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('ストリームの読み取りに失敗しました');

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.substring(6));

              if (data.type === 'complete') {
                finalScraped = data.scraped || 0;
                finalSkipped = data.skipped || 0;
              } else if (data.type === 'error') {
                throw new Error(data.message);
              } else if (data.type === 'race_start' || data.type === 'race_saved' || data.type === 'race_skipped') {
                setScrapeProgress({
                  type: data.type,
                  currentDate: data.currentDate,
                  currentDateIndex: data.currentDateIndex,
                  totalDates: data.totalDates,
                  current: data.current,
                  total: data.total,
                  raceName: data.raceName,
                  raceId: data.raceId,
                  scraped: data.scraped || 0,
                  skipped: data.skipped || 0,
                });

                if (data.type === 'race_start') {
                  setScrapeMessage(`${data.currentDate}: ${data.raceName} を取得中...`);
                } else if (data.type === 'race_saved') {
                  setScrapeMessage(`${data.currentDate}: ${data.raceName} を保存しました`);
                } else if (data.type === 'race_skipped') {
                  setScrapeMessage(`${data.currentDate}: ${data.raceName} をスキップ (既存)`);
                }
              } else if (data.type === 'date_start') {
                setScrapeProgress({
                  type: data.type,
                  currentDate: data.currentDate,
                  currentDateIndex: data.currentDateIndex,
                  totalDates: data.totalDates,
                  scraped: data.scraped || 0,
                  skipped: data.skipped || 0,
                });
                setScrapeMessage(`${data.currentDate} のレース一覧を取得中...`);
              } else if (data.type === 'list_complete') {
                setScrapeMessage(`${data.currentDate}: ${data.racesCount}件のレースを取得中...`);
              }
            } catch (e) {
              // パースエラーは無視
              if (e instanceof Error && e.message !== 'Unexpected end of JSON input') {
                console.error('SSE parse error:', e);
              }
            }
          }
        }
      }

      setScrapeStatus('success');
      const message = `完了: ${finalScraped}件 保存成功 (スキップ: ${finalSkipped}件)`;
      setScrapeMessage(message);
      setScrapeProgress(null);
      fetchStats();

      // 履歴に追加
      addToHistory({
        id: `${Date.now()}`,
        startDate,
        endDate,
        executedAt,
        status: 'success',
        message,
        racesCount: finalScraped,
      });
    } catch (error) {
      setScrapeStatus('error');
      const message = '実行エラー: ' + (error instanceof Error ? error.message : '不明');
      setScrapeMessage(message);
      setScrapeProgress(null);

      // エラーも履歴に追加
      addToHistory({
        id: `${Date.now()}`,
        startDate,
        endDate,
        executedAt,
        status: 'error',
        message,
      });
    }
  };

  const isLocal = environment === 'local';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">運用管理</h1>
        <p className="text-gray-500 mt-1">データ取得・予測処理の管理</p>
      </div>

      {/* 環境情報バナー */}
      {isLocal ? (
        <div className="mb-6 p-4 bg-green-50 border border-green-200 rounded-lg">
          <div className="flex items-start gap-3">
            <Monitor className="w-5 h-5 text-green-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-green-800">ローカル環境</h3>
              <p className="text-sm text-green-700 mt-1">
                過去データのスクレイピングとColab連携の両方が利用可能です。
              </p>
              <div className="mt-2 text-xs text-green-600 bg-green-100 px-2 py-1 rounded inline-flex items-center gap-1">
                <CheckCircle className="w-3 h-3" />
                全機能利用可能
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="mb-6 p-4 bg-blue-50 border border-blue-200 rounded-lg">
          <div className="flex items-start gap-3">
            <Cloud className="w-5 h-5 text-blue-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-blue-800">クラウド環境（Vercel）</h3>
              <p className="text-sm text-blue-700 mt-1">
                Google Colabを使った当日オッズ取得・予測が利用可能です。
                過去データのスクレイピングはローカル環境で実行してください。
              </p>
              <div className="mt-2 text-xs text-blue-600 bg-blue-100 px-2 py-1 rounded inline-flex items-center gap-1">
                <Info className="w-3 h-3" />
                Colab連携のみ
              </div>
            </div>
          </div>
        </div>
      )}

      {/* データ統計 */}
      <div className="mb-8">
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5" />
                データ統計
              </CardTitle>
              <Button variant="outline" size="sm" onClick={fetchStats} disabled={loading}>
                <RefreshCw className={`w-4 h-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
                更新
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="text-center py-4 text-gray-500">読み込み中...</div>
            ) : stats ? (
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-4">
                <StatItem label="レース" value={stats.races} />
                <StatItem label="出走データ" value={stats.entries} />
                <StatItem label="競走馬" value={stats.horses} />
                <StatItem label="騎手" value={stats.jockeys} />
                <StatItem label="予測" value={stats.predictions} />
              </div>
            ) : (
              <div className="text-center py-4 text-gray-500">
                データを取得できませんでした
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Colab連携（常に利用可能） */}
      <Card className="mb-8">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Cloud className="w-5 h-5 text-blue-600" />
            Google Colab連携（当日オッズ取得・予測）
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <p className="text-sm text-gray-600">
                Google Colabで当日の出馬表・オッズを取得し、機械学習による予測を実行します。
              </p>

              <div className="bg-blue-50 p-4 rounded-lg space-y-3">
                <div className="flex items-start gap-2">
                  <Calendar className="w-5 h-5 text-blue-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-blue-900">当日オッズ取得</p>
                    <p className="text-sm text-blue-700">
                      レース直前のオッズ情報を取得
                    </p>
                  </div>
                </div>
                <div className="flex items-start gap-2">
                  <Play className="w-5 h-5 text-blue-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-blue-900">機械学習予測</p>
                    <p className="text-sm text-blue-700">
                      過去データと当日情報から予測を生成
                    </p>
                  </div>
                </div>
              </div>

              <a
                href="https://colab.research.google.com/"
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <Button variant="outline" className="w-full">
                  <ExternalLink className="w-4 h-4 mr-2" />
                  Google Colabを開く
                </Button>
              </a>
            </div>

            <div className="bg-gray-50 p-4 rounded-lg">
              <p className="font-medium text-gray-900 mb-3">Colabでの実行手順</p>
              <ol className="list-decimal list-inside space-y-2 text-sm text-gray-600">
                <li>keiba_scraper.ipynb を開く</li>
                <li>シークレットを設定（SUPABASE_URL, SUPABASE_KEY）</li>
                <li>当日オッズ取得セルを実行</li>
                <li>予測実行セルを実行</li>
              </ol>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* 過去データスクレイピング（ローカル専用） */}
      <div className={!isLocal ? 'opacity-60 pointer-events-none' : ''}>
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2">
                <Monitor className="w-5 h-5 text-green-600" />
                過去データ取得（ローカル専用）
              </CardTitle>
              {!isLocal && (
                <span className="text-xs bg-amber-100 text-amber-700 px-2 py-1 rounded flex items-center gap-1">
                  <AlertTriangle className="w-3 h-3" />
                  ローカル環境が必要
                </span>
              )}
            </div>
          </CardHeader>
          <CardContent>
            <div className="grid gap-6 lg:grid-cols-2">
              <div className="space-y-4">
                <p className="text-sm text-gray-600">
                  netkeiba.comから過去のレースデータを取得してSupabaseに保存します。
                </p>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      開始日
                    </label>
                    <input
                      type="date"
                      value={startDate}
                      onChange={(e) => setStartDate(e.target.value)}
                      disabled={scrapeStatus === 'running'}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      終了日
                    </label>
                    <input
                      type="date"
                      value={endDate}
                      onChange={(e) => setEndDate(e.target.value)}
                      disabled={scrapeStatus === 'running'}
                      min={startDate}
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-100"
                    />
                  </div>
                </div>

                {/* オプション */}
                <div className="space-y-2">
                  <div className="flex items-center gap-2 p-3 bg-green-50 border border-green-200 rounded-lg">
                    <input
                      type="checkbox"
                      id="jra-only"
                      checked={jraOnly}
                      onChange={(e) => setJraOnly(e.target.checked)}
                      disabled={scrapeStatus === 'running'}
                      className="h-4 w-4 text-green-600 border-gray-300 rounded focus:ring-green-500 disabled:opacity-50"
                    />
                    <label htmlFor="jra-only" className="text-sm text-green-800 font-medium">
                      地方競馬（JRA）のみ取得
                    </label>
                    <span className="text-xs text-green-600 ml-auto">
                      地方競馬を除外
                    </span>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="force-overwrite"
                      checked={forceOverwrite}
                      onChange={(e) => setForceOverwrite(e.target.checked)}
                      disabled={scrapeStatus === 'running'}
                      className="h-4 w-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500 disabled:opacity-50"
                    />
                    <label htmlFor="force-overwrite" className="text-sm text-gray-700">
                      既存データを上書き更新
                    </label>
                    <span className="text-xs text-gray-500 ml-auto">
                      通常は既存データをスキップ
                    </span>
                  </div>
                </div>

                {/* Progress */}
                {scrapeStatus === 'running' && scrapeProgress && (
                  <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg space-y-3">
                    {/* 日付進捗 */}
                    {scrapeProgress.totalDates && scrapeProgress.totalDates > 1 && (
                      <div className="pb-3 border-b border-blue-200">
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-blue-700">
                            日付: {scrapeProgress.currentDateIndex} / {scrapeProgress.totalDates}
                          </span>
                          <span className="text-xs text-blue-600">
                            {scrapeProgress.currentDate}
                          </span>
                        </div>
                        <div className="w-full bg-blue-200 rounded-full h-1.5">
                          <div
                            className="bg-blue-400 h-1.5 rounded-full transition-all"
                            style={{ width: `${((scrapeProgress.currentDateIndex || 0) / scrapeProgress.totalDates) * 100}%` }}
                          />
                        </div>
                      </div>
                    )}

                    {/* レース進捗 */}
                    {scrapeProgress.total && scrapeProgress.total > 0 && (
                      <>
                        <div className="flex items-center justify-between mb-1">
                          <span className="text-sm font-medium text-blue-700 flex items-center gap-2">
                            <RefreshCw className="w-4 h-4 animate-spin" />
                            {scrapeProgress.current} / {scrapeProgress.total} レース
                          </span>
                          <span className="text-sm text-blue-600">
                            {Math.round(((scrapeProgress.current || 0) / scrapeProgress.total) * 100)}%
                          </span>
                        </div>
                        <div className="w-full bg-blue-200 rounded-full h-2">
                          <div
                            className="bg-blue-600 h-2 rounded-full transition-all"
                            style={{ width: `${((scrapeProgress.current || 0) / scrapeProgress.total) * 100}%` }}
                          />
                        </div>
                      </>
                    )}

                    {/* 現在のレース */}
                    <div className="flex justify-between text-xs">
                      <span className="text-blue-600 truncate flex-1">
                        {scrapeProgress.raceName ? `処理中: ${scrapeProgress.raceName}` : scrapeMessage}
                      </span>
                      <span className="text-gray-500 ml-2 whitespace-nowrap">
                        保存: {scrapeProgress.scraped} / スキップ: {scrapeProgress.skipped}
                      </span>
                    </div>
                  </div>
                )}

                {/* Result */}
                {scrapeStatus === 'success' && scrapeMessage && (
                  <div className="p-4 bg-green-50 border border-green-200 rounded-lg flex items-start gap-3">
                    <CheckCircle className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-green-800">取得完了</p>
                      <p className="text-sm text-green-700 mt-1">{scrapeMessage}</p>
                    </div>
                  </div>
                )}

                {/* Error */}
                {scrapeStatus === 'error' && scrapeMessage && (
                  <div className="p-4 bg-red-50 border border-red-200 rounded-lg flex items-start gap-3">
                    <AlertTriangle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="font-medium text-red-800">エラー</p>
                      <p className="text-sm text-red-700 mt-1">{scrapeMessage}</p>
                    </div>
                  </div>
                )}

                <Button
                  onClick={runScraping}
                  disabled={scrapeStatus === 'running' || !startDate || !endDate || !isLocal}
                  className="w-full"
                >
                  {scrapeStatus === 'running' ? (
                    <>
                      <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                      実行中...
                    </>
                  ) : (
                    <>
                      <Play className="w-4 h-4 mr-2" />
                      スクレイピング実行
                    </>
                  )}
                </Button>
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <p className="font-medium text-gray-900 mb-3">コマンドラインでの実行</p>
                <div className="bg-gray-900 text-gray-100 p-3 rounded-lg font-mono text-sm overflow-x-auto space-y-2">
                  <p className="text-gray-400"># 特定の日付を取得</p>
                  <p className="text-green-400">python3 scripts/scrape_local.py --date 2024-12-22</p>
                  <p className="text-gray-400 mt-2"># 期間指定でスクレイピング</p>
                  <p className="text-green-400">python3 scripts/scrape_local.py --start {startDate || 'YYYY-MM-DD'} --end {endDate || 'YYYY-MM-DD'}</p>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* スクレイピング履歴 */}
      <Card className="mt-8">
        <CardHeader>
          <div className="flex items-center justify-between">
            <CardTitle className="flex items-center gap-2">
              <History className="w-5 h-5 text-gray-600" />
              スクレイピング履歴
            </CardTitle>
            {scrapeHistory.length > 0 && (
              <Button
                variant="outline"
                size="sm"
                onClick={clearHistory}
                className="text-red-600 hover:text-red-700 hover:bg-red-50"
              >
                <Trash2 className="w-4 h-4 mr-1" />
                履歴をクリア
              </Button>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {scrapeHistory.length === 0 ? (
            <div className="text-center py-8 text-gray-500">
              <History className="w-12 h-12 mx-auto mb-3 text-gray-300" />
              <p>まだ履歴がありません</p>
              <p className="text-sm mt-1">スクレイピングを実行すると履歴が表示されます</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b bg-gray-50">
                    <th className="text-left py-3 px-4 font-medium text-gray-600">実行日時</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">対象期間</th>
                    <th className="text-left py-3 px-4 font-medium text-gray-600">結果</th>
                    <th className="text-right py-3 px-4 font-medium text-gray-600">取得件数</th>
                  </tr>
                </thead>
                <tbody>
                  {scrapeHistory.map((item) => (
                    <tr key={item.id} className="border-b last:border-0 hover:bg-gray-50">
                      <td className="py-3 px-4 text-gray-900">
                        {new Date(item.executedAt).toLocaleString('ja-JP', {
                          year: 'numeric',
                          month: '2-digit',
                          day: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}
                      </td>
                      <td className="py-3 px-4 text-gray-600">
                        {item.startDate === item.endDate ? (
                          item.startDate
                        ) : (
                          <>{item.startDate} ~ {item.endDate}</>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {item.status === 'success' ? (
                          <span className="inline-flex items-center gap-1 text-green-700 bg-green-50 px-2 py-1 rounded text-xs">
                            <CheckCircle className="w-3 h-3" />
                            成功
                          </span>
                        ) : (
                          <span className="inline-flex items-center gap-1 text-red-700 bg-red-50 px-2 py-1 rounded text-xs">
                            <AlertTriangle className="w-3 h-3" />
                            エラー
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4 text-right text-gray-900 font-medium">
                        {item.racesCount !== undefined ? `${item.racesCount}件` : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function StatItem({ label, value }: { label: string; value: number }) {
  return (
    <div className="text-center p-3 bg-gray-50 rounded-lg">
      <p className="text-2xl font-bold text-gray-900">{value.toLocaleString()}</p>
      <p className="text-sm text-gray-500">{label}</p>
    </div>
  );
}
