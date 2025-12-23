'use client';

import { useState, useEffect } from 'react';
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
} from 'lucide-react';
import { getEnvironment, getEnvironmentLabel, isLocalEnvironment } from '@/lib/environment';

type DataStats = {
  races: number;
  entries: number;
  horses: number;
  jockeys: number;
  predictions: number;
};

export default function OperationsPage() {
  const [environment] = useState(getEnvironment());
  const [stats, setStats] = useState<DataStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [scrapeStatus, setScrapeStatus] = useState<'idle' | 'running' | 'success' | 'error'>('idle');
  const [scrapeMessage, setScrapeMessage] = useState('');

  // 日付選択用
  const [startDate, setStartDate] = useState('');
  const [endDate, setEndDate] = useState('');

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
    setScrapeMessage('スクレイピングを実行中...');

    try {
      const res = await fetch('/api/scrape', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ startDate, endDate }),
      });

      if (res.ok) {
        const data = await res.json();
        setScrapeStatus('success');
        setScrapeMessage(`完了: ${data.success}件成功`);
        fetchStats();
      } else {
        const error = await res.json();
        setScrapeStatus('error');
        setScrapeMessage(error.message || 'エラーが発生しました');
      }
    } catch (error) {
      setScrapeStatus('error');
      setScrapeMessage('実行エラー: ' + (error instanceof Error ? error.message : '不明'));
    }
  };

  const isLocal = environment === 'local';

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">運用管理</h1>
        <p className="text-gray-500 mt-1">データ取得・予測処理の管理</p>
      </div>

      {/* 環境表示 */}
      <div className="mb-8">
        <Card>
          <CardContent className="p-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {isLocal ? (
                  <Monitor className="w-6 h-6 text-green-600" />
                ) : (
                  <Cloud className="w-6 h-6 text-blue-600" />
                )}
                <div>
                  <p className="font-medium text-gray-900">{getEnvironmentLabel()}</p>
                  <p className="text-sm text-gray-500">
                    {isLocal
                      ? '過去データのスクレイピングが可能です'
                      : '当日オッズ取得・予測のみ利用可能です'}
                  </p>
                </div>
              </div>
              <div
                className={`px-3 py-1 rounded-full text-sm font-medium ${
                  isLocal
                    ? 'bg-green-100 text-green-800'
                    : 'bg-blue-100 text-blue-800'
                }`}
              >
                {isLocal ? 'LOCAL' : 'CLOUD'}
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

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

      <div className="grid gap-8 lg:grid-cols-2">
        {/* ローカル専用: 過去データスクレイピング */}
        <Card className={!isLocal ? 'opacity-50' : ''}>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Monitor className="w-5 h-5 text-green-600" />
              過去データ取得
              {!isLocal && (
                <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                  ローカル専用
                </span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLocal ? (
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
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
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
                      className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                    />
                  </div>
                </div>

                {scrapeMessage && (
                  <div
                    className={`p-3 rounded-md flex items-center gap-2 ${
                      scrapeStatus === 'success'
                        ? 'bg-green-50 text-green-800'
                        : scrapeStatus === 'error'
                        ? 'bg-red-50 text-red-800'
                        : 'bg-blue-50 text-blue-800'
                    }`}
                  >
                    {scrapeStatus === 'success' ? (
                      <CheckCircle className="w-4 h-4" />
                    ) : scrapeStatus === 'error' ? (
                      <AlertTriangle className="w-4 h-4" />
                    ) : (
                      <RefreshCw className="w-4 h-4 animate-spin" />
                    )}
                    {scrapeMessage}
                  </div>
                )}

                <Button
                  onClick={runScraping}
                  disabled={scrapeStatus === 'running' || !startDate || !endDate}
                  className="w-full"
                >
                  <Play className="w-4 h-4 mr-2" />
                  スクレイピング実行
                </Button>

                <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded">
                  <p className="font-medium mb-1">コマンドラインでも実行可能:</p>
                  <code className="block bg-gray-100 p-2 rounded mt-1">
                    python3 scripts/scrape_local.py --start {startDate || 'YYYY-MM-DD'} --end{' '}
                    {endDate || 'YYYY-MM-DD'}
                  </code>
                </div>
              </div>
            ) : (
              <div className="text-center py-8">
                <AlertTriangle className="w-12 h-12 text-gray-300 mx-auto mb-3" />
                <p className="text-gray-500">
                  この機能はローカル環境でのみ利用可能です
                </p>
                <p className="text-sm text-gray-400 mt-2">
                  大量のデータ取得はサーバー負荷を避けるため
                  <br />
                  ローカル環境で実行してください
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* クラウド対応: 当日オッズ・予測 */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cloud className="w-5 h-5 text-blue-600" />
              当日オッズ取得・予測
              <span className="text-xs bg-blue-100 text-blue-600 px-2 py-1 rounded">
                Colab連携
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
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

              <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded">
                <p className="font-medium mb-1">Colabでの実行手順:</p>
                <ol className="list-decimal list-inside space-y-1 mt-2">
                  <li>keiba_scraper.ipynb を開く</li>
                  <li>シークレットを設定</li>
                  <li>当日オッズ取得セルを実行</li>
                  <li>予測実行セルを実行</li>
                </ol>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
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
