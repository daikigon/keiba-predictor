'use client';

import { useState, useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { startSyncToSupabase, getSyncStatus, SyncStatus } from '@/lib/api';
import { Cloud, RefreshCw, CheckCircle, AlertTriangle, Clock } from 'lucide-react';

interface SyncToSupabaseButtonProps {
  isBackendAvailable: boolean;
}

export function SyncToSupabaseButton({ isBackendAvailable }: SyncToSupabaseButtonProps) {
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null);
  const [isStarting, setIsStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Poll sync status
  useEffect(() => {
    if (!isBackendAvailable) return;

    const checkStatus = async () => {
      try {
        const status = await getSyncStatus();
        setSyncStatus(status);
      } catch (err) {
        console.error('Failed to get sync status:', err);
      }
    };

    checkStatus();

    // Poll every 2 seconds while running
    const interval = setInterval(checkStatus, 2000);
    return () => clearInterval(interval);
  }, [isBackendAvailable]);

  const handleStartSync = async (forceFull: boolean = false) => {
    if (isStarting || syncStatus?.is_running) return;
    setIsStarting(true);
    setError(null);

    try {
      await startSyncToSupabase(forceFull);
      const status = await getSyncStatus();
      setSyncStatus(status);
    } catch (err) {
      console.error('Failed to start sync:', err);
      setError(err instanceof Error ? err.message : '同期の開始に失敗しました');
    } finally {
      setIsStarting(false);
    }
  };

  const progressPercent = syncStatus?.total
    ? Math.round((syncStatus.progress / syncStatus.total) * 100)
    : 0;

  const tableLabels: Record<string, string> = {
    horses: '競走馬',
    jockeys: '騎手',
    races: 'レース',
    entries: '出走情報',
  };

  const formatDate = (isoString: string | null) => {
    if (!isoString) return null;
    const date = new Date(isoString);
    return date.toLocaleString('ja-JP', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  if (!isBackendAvailable) {
    return null;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Cloud className="w-5 h-5" />
          Supabaseへデータ同期
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-sm text-gray-600">
          ローカルDBのデータをSupabaseに同期します。
          差分同期では更新されたデータのみを同期します。
        </p>

        {/* Last Sync Info */}
        {syncStatus?.last_sync_at && !syncStatus.is_running && (
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <Clock className="w-4 h-4" />
            前回同期: {formatDate(syncStatus.last_sync_at)}
            {syncStatus.pending_retries > 0 && (
              <span className="text-orange-600">
                （{syncStatus.pending_retries}件リトライ待ち）
              </span>
            )}
          </div>
        )}

        {/* Sync Progress */}
        {syncStatus?.is_running && (
          <div className="p-4 bg-blue-50 border border-blue-200 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-blue-800">
                同期実行中: {syncStatus.current_table ? tableLabels[syncStatus.current_table] || syncStatus.current_table : '準備中...'}
              </span>
              <span className="text-sm text-blue-600">
                {syncStatus.progress.toLocaleString()} / {syncStatus.total.toLocaleString()} ({progressPercent}%)
              </span>
            </div>
            <div className="w-full bg-blue-200 rounded-full h-2">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
          </div>
        )}

        {/* Sync Results */}
        {syncStatus?.results && !syncStatus.is_running && (
          <div className="p-4 bg-green-50 border border-green-200 rounded-lg">
            <div className="flex items-center gap-2 mb-3">
              <CheckCircle className="w-5 h-5 text-green-600" />
              <span className="font-medium text-green-800">同期完了</span>
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm">
              {Object.entries(syncStatus.results).map(([table, result]) => (
                <div key={table} className="flex justify-between">
                  <span className="text-green-700">{tableLabels[table] || table}:</span>
                  <span className="font-medium">
                    {result.synced.toLocaleString()}件
                    {result.skipped > 0 && (
                      <span className="text-gray-500 ml-1">(スキップ: {result.skipped.toLocaleString()})</span>
                    )}
                    {result.errors > 0 && (
                      <span className="text-orange-600 ml-1">({result.errors}エラー)</span>
                    )}
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Sync Error */}
        {(syncStatus?.error || error) && !syncStatus?.is_running && (
          <div className="p-4 bg-red-50 border border-red-200 rounded-lg">
            <div className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-red-600" />
              <span className="font-medium text-red-800">同期エラー</span>
            </div>
            <p className="text-sm text-red-600 mt-1">{syncStatus?.error || error}</p>
          </div>
        )}

        <div className="flex gap-2">
          <Button
            onClick={() => handleStartSync(false)}
            disabled={isStarting || syncStatus?.is_running || !isBackendAvailable}
            className="flex-1"
          >
            <RefreshCw className={`w-4 h-4 mr-2 ${syncStatus?.is_running ? 'animate-spin' : ''}`} />
            {syncStatus?.is_running ? '同期中...' : '差分同期'}
          </Button>
          <Button
            onClick={() => handleStartSync(true)}
            disabled={isStarting || syncStatus?.is_running || !isBackendAvailable}
            variant="outline"
            className="flex-1"
          >
            全件同期
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
