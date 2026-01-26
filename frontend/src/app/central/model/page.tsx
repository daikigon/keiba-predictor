'use client';

import { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { cn } from '@/lib/utils';
import {
  getCurrentModel,
  getModelVersions,
  getRetrainingStatus,
  startRetraining,
  switchModel,
  getFeatureImportance,
  getSimulationStatus,
  startSimulation,
  startThresholdSweep,
  getThresholdSweepStatus,
  type CurrentModel,
  type ModelVersion,
  type RetrainingStatus,
  type FeatureImportance,
  type SimulationResult,
  type SimulationStatus,
  type ThresholdSweepResult,
  type ThresholdSweepDataPoint,
  type ThresholdSweepStatus,
} from '@/lib/api';
import {
  Cpu,
  RefreshCw,
  Play,
  CheckCircle,
  XCircle,
  Clock,
  BarChart2,
  TrendingUp,
  Settings,
  Loader2,
  AlertTriangle,
  Server,
  LineChart as LineChartIcon,
} from 'lucide-react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
} from 'recharts';

// SSE進捗イベントの型
type TrainingProgress = {
  type: string;
  step?: string;
  message?: string;
  progress_percent?: number;
  // データ準備の詳細進捗
  phase?: string;  // "train" | "valid" | "test"
  current?: number;
  total?: number;
  // 新しい評価指標（二値分類用）
  train_logloss?: number;
  valid_logloss?: number;
  test_logloss?: number;
  train_auc?: number;
  valid_auc?: number;
  test_auc?: number;
  best_iteration?: number;
  // サンプル数
  num_train_samples?: number;
  num_valid_samples?: number;
  num_test_samples?: number;
  num_features?: number;
  // 過学習チェック
  overfit_gap?: number;
  generalization_gap?: number;
  version?: string;
  error?: string;
};

export default function ModelPage() {
  const [currentModel, setCurrentModel] = useState<CurrentModel | null>(null);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [retrainingStatus, setRetrainingStatus] = useState<RetrainingStatus | null>(null);
  const [featureImportance, setFeatureImportance] = useState<FeatureImportance[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRetraining, setIsRetraining] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendAvailable, setBackendAvailable] = useState(true);

  // SSE進捗状態
  const [trainingProgress, setTrainingProgress] = useState<TrainingProgress | null>(null);
  const [progressLogs, setProgressLogs] = useState<string[]>([]);
  const [lastProgressPercent, setLastProgressPercent] = useState<number>(0);

  // Training parameters
  const [trainParams, setTrainParams] = useState({
    use_time_split: true,
    train_end_date: '',
    valid_end_date: '',
    num_boost_round: 3000,
    early_stopping: 100,
  });

  const raceType = 'central';

  // ページ読み込み時に保存したモデルバージョンを復元
  const restoreSavedModel = useCallback(async () => {
    if (typeof window === 'undefined') return;

    const savedVersion = localStorage.getItem(`selectedModelVersion_${raceType}`);
    if (savedVersion) {
      try {
        const result = await switchModel(savedVersion, raceType);
        setCurrentModel(result.model);
      } catch {
        // 保存されたバージョンが無効な場合は無視
        localStorage.removeItem(`selectedModelVersion_${raceType}`);
      }
    }
  }, []);

  const loadData = useCallback(async () => {
    let failedCount = 0;
    try {
      const [model, vers, status, features] = await Promise.all([
        getCurrentModel(raceType).catch(() => {
          failedCount++;
          return null;
        }),
        getModelVersions(raceType).catch(() => {
          failedCount++;
          return [];
        }),
        getRetrainingStatus().catch(() => {
          failedCount++;
          return null;
        }),
        getFeatureImportance(15, raceType).catch(() => {
          failedCount++;
          return [];
        }),
      ]);

      // 全てのAPIが失敗した場合はバックエンドが利用不可
      if (failedCount >= 4) {
        setBackendAvailable(false);
      } else {
        setBackendAvailable(true);
      }

      setCurrentModel(model);
      setVersions(vers);
      setRetrainingStatus(status);
      setFeatureImportance(features);
      setError(null);
    } catch {
      setBackendAvailable(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    restoreSavedModel();
  }, [loadData, restoreSavedModel]);

  // Poll for status updates during retraining
  useEffect(() => {
    if (retrainingStatus?.is_running) {
      const interval = setInterval(async () => {
        try {
          const status = await getRetrainingStatus();
          setRetrainingStatus(status);

          if (!status.is_running) {
            loadData();
          }
        } catch (err) {
          console.error('Failed to poll status:', err);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [retrainingStatus?.is_running, loadData]);

  const handleRetrain = async () => {
    // バリデーション
    if (trainParams.use_time_split) {
      if (!trainParams.train_end_date || !trainParams.valid_end_date) {
        setError('時系列分割モードでは学習終了日と検証終了日を指定してください');
        return;
      }
      if (trainParams.train_end_date >= trainParams.valid_end_date) {
        setError('学習終了日は検証終了日より前である必要があります');
        return;
      }
    }

    setIsRetraining(true);
    setError(null);
    setTrainingProgress(null);
    setProgressLogs([]);
    setLastProgressPercent(0);

    try {
      const params = trainParams.use_time_split
        ? {
            use_time_split: true,
            train_end_date: trainParams.train_end_date,
            valid_end_date: trainParams.valid_end_date,
            num_boost_round: trainParams.num_boost_round,
            early_stopping: trainParams.early_stopping,
            race_type: raceType,
          }
        : {
            num_boost_round: trainParams.num_boost_round,
            early_stopping: trainParams.early_stopping,
            race_type: raceType,
          };

      // 再学習を開始
      await startRetraining(params);

      // SSEストリームに接続
      const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000';
      const eventSource = new EventSource(`${apiBase}/api/v1/model/status/stream`);

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data) as TrainingProgress;
          setTrainingProgress(data);

          // 進捗パーセントを更新（常に最新値を保持）
          if (data.progress_percent !== undefined) {
            setLastProgressPercent(data.progress_percent);
          }

          // ログにメッセージを追加
          if (data.message) {
            setProgressLogs((prev) => [...prev, `[${data.type}] ${data.message}`]);
          }

          // 完了またはエラー時にSSE接続を閉じる
          if (data.type === 'complete' || data.type === 'error') {
            eventSource.close();
            setIsRetraining(false);
            loadData(); // データをリロード
          }
        } catch (e) {
          console.error('Failed to parse SSE data:', e);
        }
      };

      eventSource.onerror = () => {
        eventSource.close();
        setIsRetraining(false);
        // エラー時もステータスを確認
        getRetrainingStatus().then((status) => setRetrainingStatus(status));
      };

    } catch (err) {
      setError('再学習の開始に失敗しました');
      console.error(err);
      setIsRetraining(false);
    }
  };

  const handleSwitchModel = async (version: string) => {
    try {
      const result = await switchModel(version, raceType);
      setCurrentModel(result.model);
      // 選択したモデルバージョンをlocalStorageに保存
      if (typeof window !== 'undefined') {
        localStorage.setItem(`selectedModelVersion_${raceType}`, version);
      }
      await loadData();
    } catch (err) {
      setError('モデルの切り替えに失敗しました');
      console.error(err);
    }
  };

  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-blue-600" />
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">モデル管理（中央競馬）</h1>
        <p className="text-gray-500 mt-1">中央競馬用の機械学習モデルの管理とシミュレーション</p>
      </div>

      {/* FastAPIバックエンド必要の注意書き */}
      {!backendAvailable && (
        <div className="mb-6 p-4 bg-amber-50 border border-amber-200 rounded-lg">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
            <div>
              <h3 className="font-medium text-amber-800">FastAPIバックエンドが必要です</h3>
              <p className="text-sm text-amber-700 mt-1">
                モデル管理機能はローカルのFastAPIバックエンドが必要です。
                現在はSupabase直接接続モードのため、モデル管理機能は利用できません。
              </p>
              <div className="mt-2 text-xs text-amber-600 bg-amber-100 px-2 py-1 rounded inline-flex items-center gap-1">
                <Server className="w-3 h-3" />
                FastAPIバックエンド: 停止中
              </div>
              <div className="mt-3 p-3 bg-amber-100 rounded text-sm text-amber-800">
                <p className="font-medium mb-1">バックエンドの起動方法:</p>
                <code className="block bg-amber-200 px-2 py-1 rounded text-xs mt-1">
                  cd backend && source venv/bin/activate && uvicorn app.main:app --reload
                </code>
              </div>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="mb-4 p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      <div className={cn("grid gap-6 lg:grid-cols-2", !backendAvailable && "opacity-60 pointer-events-none")}>
        {/* Current Model Status */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-blue-600" />
              <CardTitle>現在のモデル</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {currentModel ? (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">バージョン</span>
                  <Badge variant="default">{currentModel.version}</Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">状態</span>
                  <Badge variant={currentModel.is_loaded ? 'success' : 'danger'}>
                    {currentModel.is_loaded ? '読み込み済み' : '未読み込み'}
                  </Badge>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-500">特徴量数</span>
                  <span className="font-medium">{currentModel.num_features}</span>
                </div>
                {currentModel.best_iteration && (
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-500">ベストイテレーション</span>
                    <span className="font-medium">{currentModel.best_iteration}</span>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-4">モデルが読み込まれていません</p>
            )}
          </CardContent>
        </Card>

        {/* Retraining */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <RefreshCw className="w-5 h-5 text-green-600" />
              <CardTitle>再学習</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* 期間設定 */}
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="use_time_split"
                    checked={trainParams.use_time_split}
                    onChange={(e) =>
                      setTrainParams({ ...trainParams, use_time_split: e.target.checked })
                    }
                    className="w-4 h-4"
                  />
                  <label htmlFor="use_time_split" className="text-sm font-medium">
                    時系列分割モード（推奨）
                  </label>
                </div>

                {trainParams.use_time_split && (
                  <div className="pl-6 space-y-3 border-l-2 border-green-200">
                    <p className="text-xs text-gray-500">
                      データリークを防ぐため、期間で学習・検証・テストを分割します
                    </p>
                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">
                          学習終了日
                        </label>
                        <input
                          type="date"
                          value={trainParams.train_end_date}
                          onChange={(e) =>
                            setTrainParams({ ...trainParams, train_end_date: e.target.value })
                          }
                          className="w-full px-2 py-1.5 border rounded text-sm"
                        />
                      </div>
                      <div>
                        <label className="block text-xs text-gray-600 mb-1">
                          検証終了日
                        </label>
                        <input
                          type="date"
                          value={trainParams.valid_end_date}
                          onChange={(e) =>
                            setTrainParams({ ...trainParams, valid_end_date: e.target.value })
                          }
                          className="w-full px-2 py-1.5 border rounded text-sm"
                        />
                      </div>
                    </div>
                    <p className="text-xs text-gray-400">
                      検証終了日以降がテストデータになります
                    </p>
                  </div>
                )}
              </div>

              {/* ステータス表示 */}
              {(isRetraining || retrainingStatus?.is_running) ? (
                <div className="space-y-3 p-3 bg-blue-50 rounded-lg">
                  <div className="flex items-center gap-2 text-blue-600">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>
                      再学習中...
                      {trainingProgress?.message && ` - ${trainingProgress.message}`}
                    </span>
                  </div>

                  {/* 進捗バー（常に表示） */}
                  <div className="space-y-1">
                    <div className="flex justify-between text-xs text-gray-600">
                      <span>
                        {trainingProgress?.step === 'preparing_data' && trainingProgress.phase
                          ? `データ準備中 (${trainingProgress.phase === 'train' ? '学習' : trainingProgress.phase === 'valid' ? '検証' : 'テスト'}データ)`
                          : trainingProgress?.step || '処理中...'}
                      </span>
                      <span>{lastProgressPercent}%</span>
                    </div>
                    <div className="w-full bg-blue-200 rounded-full h-2">
                      <div
                        className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                        style={{ width: `${lastProgressPercent}%` }}
                      />
                    </div>
                    {/* データ準備中の詳細進捗 */}
                    {trainingProgress?.step === 'preparing_data' && trainingProgress.total && (
                      <div className="text-xs text-gray-500 mt-1">
                        {trainingProgress.current} / {trainingProgress.total} レース処理中
                      </div>
                    )}
                  </div>

                  {/* 学習メトリクス */}
                  {trainingProgress?.train_auc && (
                    <div className="space-y-2 text-xs">
                      <div className="grid grid-cols-3 gap-2">
                        <div className="bg-white p-2 rounded">
                          <span className="text-gray-500">Train AUC:</span>
                          <span className="ml-1 font-medium">{trainingProgress.train_auc.toFixed(4)}</span>
                        </div>
                        <div className="bg-white p-2 rounded">
                          <span className="text-gray-500">Valid AUC:</span>
                          <span className="ml-1 font-medium">{trainingProgress.valid_auc?.toFixed(4) || '-'}</span>
                        </div>
                        {trainingProgress.test_auc && (
                          <div className="bg-white p-2 rounded">
                            <span className="text-gray-500">Test AUC:</span>
                            <span className="ml-1 font-medium">{trainingProgress.test_auc.toFixed(4)}</span>
                          </div>
                        )}
                      </div>
                      {trainingProgress.overfit_gap !== undefined && (
                        <div className={`bg-white p-2 rounded ${trainingProgress.overfit_gap > 0.1 ? 'border border-yellow-400' : ''}`}>
                          <span className="text-gray-500">過学習チェック:</span>
                          <span className={`ml-1 font-medium ${trainingProgress.overfit_gap > 0.1 ? 'text-yellow-600' : 'text-green-600'}`}>
                            Gap={trainingProgress.overfit_gap.toFixed(4)}
                            {trainingProgress.overfit_gap > 0.1 ? ' ⚠️' : ' ✓'}
                          </span>
                        </div>
                      )}
                    </div>
                  )}

                  {/* ログ表示 */}
                  {progressLogs.length > 0 && (
                    <div className="mt-2 max-h-32 overflow-y-auto bg-gray-900 text-green-400 text-xs p-2 rounded font-mono">
                      {progressLogs.map((log, i) => (
                        <div key={i}>{log}</div>
                      ))}
                    </div>
                  )}
                </div>
              ) : retrainingStatus?.last_result ? (
                <div className="space-y-2 p-3 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    <span>最後の再学習: {retrainingStatus.last_result.success ? '成功' : '失敗'}</span>
                  </div>
                  <div className="text-sm text-gray-500 space-y-1">
                    <p>バージョン: {retrainingStatus.last_result.model_version}</p>
                    {retrainingStatus.last_result.valid_auc && (
                      <p>Valid AUC: {retrainingStatus.last_result.valid_auc.toFixed(4)}</p>
                    )}
                    {retrainingStatus.last_result.test_auc && (
                      <p>Test AUC: {retrainingStatus.last_result.test_auc.toFixed(4)}</p>
                    )}
                    {retrainingStatus.last_result.best_iteration && (
                      <p>Best Iteration: {retrainingStatus.last_result.best_iteration}</p>
                    )}
                  </div>
                </div>
              ) : retrainingStatus?.error ? (
                <div className="flex items-center gap-2 text-red-600 p-3 bg-red-50 rounded-lg">
                  <XCircle className="w-4 h-4" />
                  <span>エラー: {retrainingStatus.error}</span>
                </div>
              ) : null}

              <Button
                onClick={handleRetrain}
                isLoading={isRetraining || retrainingStatus?.is_running}
                disabled={retrainingStatus?.is_running}
                className="w-full"
              >
                <Play className="w-4 h-4 mr-2" />
                再学習を開始
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Model Versions */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-purple-600" />
              <CardTitle>モデルバージョン</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {versions.length > 0 ? (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {versions.map((v) => (
                  <div
                    key={v.version}
                    className={cn(
                      'flex items-center justify-between p-3 rounded-lg border',
                      currentModel?.version === v.version
                        ? 'border-blue-300 bg-blue-50'
                        : 'border-gray-200'
                    )}
                  >
                    <div>
                      <p className="font-medium">{v.version}</p>
                      <p className="text-xs text-gray-500">
                        {new Date(v.created_at).toLocaleString('ja-JP')}
                      </p>
                      <p className="text-xs text-gray-400">
                        {v.size_bytes
                          ? `${(v.size_bytes / 1024 / 1024).toFixed(2)} MB`
                          : v.file_size_mb
                            ? `${v.file_size_mb.toFixed(2)} MB`
                            : '-'}
                      </p>
                    </div>
                    {currentModel?.version === v.version ? (
                      <Badge variant="success">使用中</Badge>
                    ) : (
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => handleSwitchModel(v.version)}
                      >
                        切り替え
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-4">バージョンがありません</p>
            )}
          </CardContent>
        </Card>

        {/* Feature Importance */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5 text-orange-600" />
              <CardTitle>特徴量重要度 (Top 15)</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            {featureImportance.length > 0 ? (
              <div className="space-y-2">
                {featureImportance.map((f, i) => {
                  const maxImportance = featureImportance[0]?.importance || 1;
                  const widthPercent = (f.importance / maxImportance) * 100;
                  return (
                    <div key={f.feature} className="space-y-1">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-600 truncate" title={f.feature}>
                          {i + 1}. {f.feature}
                        </span>
                        <span className="font-medium">{f.importance.toFixed(0)}</span>
                      </div>
                      <div className="w-full bg-gray-100 rounded-full h-1.5">
                        <div
                          className="bg-orange-500 h-1.5 rounded-full"
                          style={{ width: `${widthPercent}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            ) : (
              <p className="text-gray-500 text-center py-4">データがありません</p>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Simulation Section */}
      <SimulationSection backendAvailable={backendAvailable} />

      {/* Threshold Sweep Analysis Section */}
      <ThresholdSweepSection backendAvailable={backendAvailable} />
    </div>
  );
}

// シミュレーション履歴エントリの型
interface SimulationHistoryEntry {
  id: string;
  timestamp: string;
  params: {
    ev_threshold: number;
    max_ev: number;
    umaren_ev_threshold: number;
    umaren_max_ev: number;
    bet_type: string;
    limit: number;
  };
  result: SimulationResult;
}

const SIMULATION_HISTORY_KEY = 'simulation_history_central';
const MAX_SIMULATION_HISTORY = 5;

function SimulationSection({ backendAvailable }: { backendAvailable: boolean }) {
  const [simulationStatus, setSimulationStatus] = useState<SimulationStatus | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<SimulationHistoryEntry[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string>('');
  const [displayResult, setDisplayResult] = useState<SimulationResult | null>(null);

  // Simulation parameters (localStorageから復元)
  const [simParams, setSimParams] = useState(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem('simParams_central');
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch {}
      }
    }
    return {
      ev_threshold: 1.0,
      max_ev: 2.0,
      umaren_ev_threshold: 1.2,
      umaren_max_ev: 5.0,
      bet_type: 'all' as 'tansho' | 'umaren' | 'all',
      bet_amount: 100,
      limit: 200,
      start_date: '',
      end_date: '',
      min_probability: 0.01,
      umaren_top_n: 3,
    };
  });

  // simParamsが変更されたらlocalStorageに保存
  useEffect(() => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('simParams_central', JSON.stringify(simParams));
    }
  }, [simParams]);

  // 履歴をlocalStorageから読み込み
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(SIMULATION_HISTORY_KEY);
      if (saved) {
        try {
          setHistory(JSON.parse(saved));
        } catch {}
      }
    }
  }, []);

  // 履歴に保存
  const saveToHistory = (result: SimulationResult) => {
    const entry: SimulationHistoryEntry = {
      id: Date.now().toString(),
      timestamp: new Date().toLocaleString('ja-JP'),
      params: {
        ev_threshold: simParams.ev_threshold,
        max_ev: simParams.max_ev,
        umaren_ev_threshold: simParams.umaren_ev_threshold,
        umaren_max_ev: simParams.umaren_max_ev,
        bet_type: simParams.bet_type,
        limit: simParams.limit,
      },
      result,
    };

    const newHistory = [entry, ...history].slice(0, MAX_SIMULATION_HISTORY);
    setHistory(newHistory);
    localStorage.setItem(SIMULATION_HISTORY_KEY, JSON.stringify(newHistory));
  };

  // 履歴選択時
  const handleSelectHistory = (id: string) => {
    setSelectedHistoryId(id);
    if (id === '') {
      // 現在の結果を表示
      setDisplayResult(simulationStatus?.results || null);
      return;
    }
    const entry = history.find((h) => h.id === id);
    if (entry) {
      setDisplayResult(entry.result);
    }
  };

  const handleSimulate = async () => {
    setIsSimulating(true);
    setError(null);
    setSelectedHistoryId('');
    setDisplayResult(null);
    setSimulationStatus({
      is_running: true,
      progress: 0,
      total: 0,
      results: null,
      error: null,
    });

    try {
      // 空の日付は除外
      const params = {
        ...simParams,
        start_date: simParams.start_date || undefined,
        end_date: simParams.end_date || undefined,
        race_type: 'central',
      };

      // 非同期シミュレーション開始
      await startSimulation(params);

      // ポーリングで進捗を監視
      const pollInterval = setInterval(async () => {
        try {
          const status = await getSimulationStatus();
          setSimulationStatus(status);

          // 完了したらポーリング停止
          if (!status.is_running) {
            clearInterval(pollInterval);
            setIsSimulating(false);
            if (status.error) {
              setError(status.error);
            } else if (status.results) {
              setDisplayResult(status.results);
              // 履歴に保存
              saveToHistory(status.results);
            }
          }
        } catch (pollErr) {
          console.error('Failed to poll simulation status:', pollErr);
        }
      }, 500);

    } catch (err) {
      setError('シミュレーションの開始に失敗しました');
      console.error(err);
      setIsSimulating(false);
      setSimulationStatus({
        is_running: false,
        progress: 0,
        total: 0,
        results: null,
        error: null,
      });
    }
  };

  return (
    <Card className={cn("mt-6", !backendAvailable && "opacity-60 pointer-events-none")}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-indigo-600" />
            <CardTitle>期待値シミュレーション</CardTitle>
          </div>
          {/* 履歴セレクター */}
          {history.length > 0 && (
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" />
              <select
                value={selectedHistoryId}
                onChange={(e) => handleSelectHistory(e.target.value)}
                className="text-sm border rounded-lg px-2 py-1 bg-white"
              >
                <option value="">-- 履歴を選択 --</option>
                {history.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.timestamp} ({h.params.bet_type === 'all' ? '全て' : h.params.bet_type === 'tansho' ? '単勝' : '馬連'}, EV {h.params.ev_threshold}~{h.params.max_ev}{h.result.model_version ? `, ${h.result.model_version}` : ''})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Parameters */}
          <div className="space-y-4">
            <h4 className="font-medium flex items-center gap-2">
              <Settings className="w-4 h-4" />
              パラメータ設定
            </h4>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  単勝EV下限
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={simParams.ev_threshold}
                  onChange={(e) =>
                    setSimParams({ ...simParams, ev_threshold: parseFloat(e.target.value) })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  単勝EV上限
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={simParams.max_ev}
                  onChange={(e) =>
                    setSimParams({ ...simParams, max_ev: parseFloat(e.target.value) })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  馬連EV下限
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={simParams.umaren_ev_threshold}
                  onChange={(e) =>
                    setSimParams({
                      ...simParams,
                      umaren_ev_threshold: parseFloat(e.target.value),
                    })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  馬連EV上限
                </label>
                <input
                  type="number"
                  step="0.1"
                  min="0"
                  value={simParams.umaren_max_ev}
                  onChange={(e) =>
                    setSimParams({
                      ...simParams,
                      umaren_max_ev: parseFloat(e.target.value),
                    })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  最低確率 (%)
                </label>
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  value={Math.round(simParams.min_probability * 100)}
                  onChange={(e) =>
                    setSimParams({
                      ...simParams,
                      min_probability: parseFloat(e.target.value) / 100,
                    })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  馬連対象馬数
                </label>
                <input
                  type="number"
                  step="1"
                  min="2"
                  max="10"
                  value={simParams.umaren_top_n}
                  onChange={(e) =>
                    setSimParams({
                      ...simParams,
                      umaren_top_n: parseInt(e.target.value),
                    })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  賭け種別
                </label>
                <select
                  value={simParams.bet_type}
                  onChange={(e) =>
                    setSimParams({
                      ...simParams,
                      bet_type: e.target.value as 'tansho' | 'umaren' | 'all',
                    })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                >
                  <option value="all">全て</option>
                  <option value="tansho">単勝のみ</option>
                  <option value="umaren">馬連のみ</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 mb-1">
                  1点賭け金
                </label>
                <input
                  type="number"
                  step="100"
                  min="100"
                  value={simParams.bet_amount}
                  onChange={(e) =>
                    setSimParams({ ...simParams, bet_amount: parseInt(e.target.value) })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
              <div className="col-span-2">
                <label className="block text-sm text-gray-600 mb-1">
                  対象レース数（上限）
                </label>
                <input
                  type="number"
                  step="50"
                  min="10"
                  max="1000"
                  value={simParams.limit}
                  onChange={(e) =>
                    setSimParams({ ...simParams, limit: parseInt(e.target.value) })
                  }
                  className="w-full px-3 py-2 border rounded-lg text-sm"
                />
              </div>
            </div>

            {/* 期間指定 */}
            <div className="pt-3 border-t">
              <h5 className="text-sm font-medium text-gray-700 mb-2">
                テスト期間（データリーク防止用）
              </h5>
              <p className="text-xs text-gray-500 mb-3">
                学習に使っていない期間を指定することで、正確な回収率を確認できます
              </p>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    開始日
                  </label>
                  <input
                    type="date"
                    value={simParams.start_date}
                    onChange={(e) =>
                      setSimParams({ ...simParams, start_date: e.target.value })
                    }
                    className="w-full px-3 py-2 border rounded-lg text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm text-gray-600 mb-1">
                    終了日
                  </label>
                  <input
                    type="date"
                    value={simParams.end_date}
                    onChange={(e) =>
                      setSimParams({ ...simParams, end_date: e.target.value })
                    }
                    className="w-full px-3 py-2 border rounded-lg text-sm"
                  />
                </div>
              </div>
            </div>

            <Button
              onClick={handleSimulate}
              isLoading={isSimulating || simulationStatus?.is_running}
              disabled={simulationStatus?.is_running}
              className="w-full"
            >
              <Play className="w-4 h-4 mr-2" />
              シミュレーション実行
            </Button>
          </div>

          {/* Results */}
          <div>
            <h4 className="font-medium mb-4">結果</h4>

            {error && (
              <div className="text-red-600 p-4 bg-red-50 rounded-lg mb-4">
                {error}
              </div>
            )}

            {simulationStatus?.is_running ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2 text-blue-600">
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>
                    シミュレーション中... ({simulationStatus.progress}/{simulationStatus.total})
                  </span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all"
                    style={{
                      width: `${
                        simulationStatus.total > 0
                          ? (simulationStatus.progress / simulationStatus.total) * 100
                          : 0
                      }%`,
                    }}
                  />
                </div>
              </div>
            ) : displayResult ? (
              <SimulationResultCard results={displayResult} />
            ) : (
              <p className="text-gray-500 text-center py-8">
                シミュレーションを実行してください
              </p>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

// 閾値スイープ履歴エントリの型
interface SweepHistoryEntry {
  id: string;
  timestamp: string;
  params: {
    bet_type: string;
    ev_min: number;
    ev_max: number;
    limit: number;
    min_probability?: number;
  };
  result: ThresholdSweepResult;
}

const SWEEP_HISTORY_KEY = 'threshold_sweep_history_central';
const MAX_HISTORY = 5;

function ThresholdSweepSection({ backendAvailable }: { backendAvailable: boolean }) {
  const [sweepStatus, setSweepStatus] = useState<ThresholdSweepStatus | null>(null);
  const [sweepResult, setSweepResult] = useState<ThresholdSweepResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<SweepHistoryEntry[]>([]);
  const [selectedHistoryId, setSelectedHistoryId] = useState<string>('');
  const [sweepParams, setSweepParams] = useState({
    bet_type: 'tansho' as 'tansho' | 'umaren',
    ev_min: 0.8,
    ev_max: 2.0,
    ev_step: 0.05,
    min_probability: 0.05,  // 期待値シミュレーションと同じデフォルト値
    limit: 500,
    start_date: '',
    end_date: '',
  });

  // 履歴をlocalStorageから読み込み
  useEffect(() => {
    if (typeof window !== 'undefined') {
      const saved = localStorage.getItem(SWEEP_HISTORY_KEY);
      if (saved) {
        try {
          setHistory(JSON.parse(saved));
        } catch {}
      }
    }
  }, []);

  // 履歴に保存
  const saveToHistory = (result: ThresholdSweepResult) => {
    const entry: SweepHistoryEntry = {
      id: Date.now().toString(),
      timestamp: new Date().toLocaleString('ja-JP'),
      params: {
        bet_type: sweepParams.bet_type,
        ev_min: sweepParams.ev_min,
        ev_max: sweepParams.ev_max,
        limit: sweepParams.limit,
        min_probability: sweepParams.min_probability,
      },
      result,
    };

    const newHistory = [entry, ...history].slice(0, MAX_HISTORY);
    setHistory(newHistory);
    localStorage.setItem(SWEEP_HISTORY_KEY, JSON.stringify(newHistory));
  };

  // 履歴選択時
  const handleSelectHistory = (id: string) => {
    setSelectedHistoryId(id);
    if (id === '') {
      // 現在の結果を表示
      return;
    }
    const entry = history.find((h) => h.id === id);
    if (entry) {
      setSweepResult(entry.result);
    }
  };

  const handleRunSweep = async () => {
    setIsLoading(true);
    setError(null);
    setSweepResult(null);
    setSweepStatus(null);
    setSelectedHistoryId('');

    try {
      const params = {
        ...sweepParams,
        start_date: sweepParams.start_date || undefined,
        end_date: sweepParams.end_date || undefined,
        race_type: 'central',
      };
      await startThresholdSweep(params);

      // ポーリングで進捗を監視
      const pollInterval = setInterval(async () => {
        try {
          const status = await getThresholdSweepStatus();
          setSweepStatus(status);

          if (!status.is_running) {
            clearInterval(pollInterval);
            setIsLoading(false);

            if (status.error) {
              setError(status.error);
            } else if (status.results) {
              setSweepResult(status.results);
              // 履歴に保存
              saveToHistory(status.results);
            }
          }
        } catch (pollErr) {
          console.error('Failed to poll sweep status:', pollErr);
        }
      }, 300);

    } catch (err) {
      setError('閾値スイープ分析の開始に失敗しました');
      console.error(err);
      setIsLoading(false);
    }
  };

  // グラフ用にデータを変換（回収率をパーセント表示）
  const chartData = sweepResult?.data.map((d) => ({
    ...d,
    return_rate_pct: d.return_rate * 100,
  })) || [];

  return (
    <Card className={cn("mt-6", !backendAvailable && "opacity-60 pointer-events-none")}>
      <CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <LineChartIcon className="w-5 h-5 text-purple-600" />
            <CardTitle>閾値スイープ分析</CardTitle>
          </div>
          {/* 履歴セレクター */}
          {history.length > 0 && (
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-gray-400" />
              <select
                value={selectedHistoryId}
                onChange={(e) => handleSelectHistory(e.target.value)}
                className="text-sm border rounded-lg px-2 py-1 bg-white"
              >
                <option value="">-- 履歴を選択 --</option>
                {history.map((h) => (
                  <option key={h.id} value={h.id}>
                    {h.timestamp} ({h.params.bet_type === 'tansho' ? '単勝' : '馬連'}, EV {h.params.ev_min}~{h.params.ev_max}{h.result.model_version ? `, ${h.result.model_version}` : ''})
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="space-y-6">
          {/* パラメータ設定 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">賭け種別</label>
              <select
                value={sweepParams.bet_type}
                onChange={(e) =>
                  setSweepParams({ ...sweepParams, bet_type: e.target.value as 'tansho' | 'umaren' })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              >
                <option value="tansho">単勝</option>
                <option value="umaren">馬連</option>
              </select>
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">EV最小</label>
              <input
                type="number"
                step="0.1"
                value={sweepParams.ev_min}
                onChange={(e) =>
                  setSweepParams({ ...sweepParams, ev_min: parseFloat(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">EV最大</label>
              <input
                type="number"
                step="0.1"
                value={sweepParams.ev_max}
                onChange={(e) =>
                  setSweepParams({ ...sweepParams, ev_max: parseFloat(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">レース数</label>
              <input
                type="number"
                step="100"
                value={sweepParams.limit}
                onChange={(e) =>
                  setSweepParams({ ...sweepParams, limit: parseInt(e.target.value) })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
          </div>

          {/* 最低確率 */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">最低確率 (%)</label>
              <input
                type="number"
                step="1"
                min="0"
                max="100"
                value={Math.round(sweepParams.min_probability * 100)}
                onChange={(e) =>
                  setSweepParams({ ...sweepParams, min_probability: parseFloat(e.target.value) / 100 })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
          </div>

          {/* 期間指定 */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-600 mb-1">開始日</label>
              <input
                type="date"
                value={sweepParams.start_date}
                onChange={(e) =>
                  setSweepParams({ ...sweepParams, start_date: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-600 mb-1">終了日</label>
              <input
                type="date"
                value={sweepParams.end_date}
                onChange={(e) =>
                  setSweepParams({ ...sweepParams, end_date: e.target.value })
                }
                className="w-full px-3 py-2 border rounded-lg text-sm"
              />
            </div>
          </div>

          <Button onClick={handleRunSweep} isLoading={isLoading} disabled={isLoading} className="w-full">
            <Play className="w-4 h-4 mr-2" />
            分析実行
          </Button>

          {/* 進捗表示 */}
          {isLoading && sweepStatus && (
            <div className="space-y-3 p-4 bg-purple-50 rounded-lg">
              <div className="flex items-center gap-2 text-purple-600">
                <Loader2 className="w-4 h-4 animate-spin" />
                <span>
                  {sweepStatus.phase === 'preparing' && 'データ準備中...'}
                  {sweepStatus.phase === 'sweeping' && '閾値スイープ中...'}
                </span>
              </div>

              {sweepStatus.phase === 'preparing' && sweepStatus.total > 0 && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-gray-600">
                    <span>レースデータ準備</span>
                    <span>{sweepStatus.progress} / {sweepStatus.total}</span>
                  </div>
                  <div className="w-full bg-purple-200 rounded-full h-2">
                    <div
                      className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${(sweepStatus.progress / sweepStatus.total) * 100}%` }}
                    />
                  </div>
                </div>
              )}

              {sweepStatus.phase === 'sweeping' && sweepStatus.total_thresholds > 0 && (
                <div className="space-y-1">
                  <div className="flex justify-between text-xs text-gray-600">
                    <span>閾値分析</span>
                    <span>{sweepStatus.current_threshold} / {sweepStatus.total_thresholds}</span>
                  </div>
                  <div className="w-full bg-purple-200 rounded-full h-2">
                    <div
                      className="bg-purple-600 h-2 rounded-full transition-all duration-300"
                      style={{ width: `${(sweepStatus.current_threshold / sweepStatus.total_thresholds) * 100}%` }}
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          {/* グラフ表示 */}
          {sweepResult && chartData.length > 0 && (
            <div className="space-y-4">
              <div className="text-sm text-gray-600">
                対象: {sweepResult.total_races}レース / {sweepResult.bet_type === 'tansho' ? '単勝' : '馬連'}
                {sweepResult.model_version && (
                  <span className="ml-4 text-blue-600">
                    モデル: {sweepResult.model_version} ({sweepResult.num_features}特徴量)
                  </span>
                )}
              </div>

              <div className="h-80">
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={chartData} margin={{ top: 20, right: 60, left: 20, bottom: 20 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                    <XAxis
                      dataKey="ev_threshold"
                      label={{ value: '期待値閾値', position: 'bottom', offset: 0 }}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis
                      yAxisId="left"
                      domain={[0, 'auto']}
                      label={{ value: '回収率 (%)', angle: -90, position: 'insideLeft' }}
                      tick={{ fontSize: 12 }}
                    />
                    <YAxis
                      yAxisId="right"
                      orientation="right"
                      domain={['auto', 'auto']}
                      label={{ value: 'シャープレシオ', angle: 90, position: 'insideRight' }}
                      tick={{ fontSize: 12 }}
                    />
                    <Tooltip
                      formatter={(value, name) => {
                        if (typeof value !== 'number') return value;
                        if (name === '回収率') return `${value.toFixed(1)}%`;
                        if (name === 'シャープレシオ') return value.toFixed(3);
                        return value;
                      }}
                      labelFormatter={(label) => `EV閾値: ${label}`}
                    />
                    <Legend />
                    <ReferenceLine yAxisId="left" y={100} stroke="#10b981" strokeDasharray="5 5" label="100%" />
                    <Line
                      yAxisId="left"
                      type="monotone"
                      dataKey="return_rate_pct"
                      name="回収率"
                      stroke="#3b82f6"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      yAxisId="right"
                      type="monotone"
                      dataKey="sharpe_ratio"
                      name="シャープレシオ"
                      stroke="#ef4444"
                      strokeWidth={2}
                      dot={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {/* 最適閾値の表示 */}
              <div className="grid grid-cols-2 gap-4">
                <div className="p-3 bg-blue-50 rounded-lg">
                  <p className="text-xs text-blue-600 mb-1">最高回収率</p>
                  {(() => {
                    const best = chartData.reduce((a, b) =>
                      a.return_rate_pct > b.return_rate_pct ? a : b
                    );
                    return (
                      <div>
                        <p className="font-semibold text-blue-700">
                          {best.return_rate_pct.toFixed(1)}% (EV≥{best.ev_threshold})
                        </p>
                        <p className="text-xs text-blue-500">
                          {best.bet_count}点 / {best.race_count ?? '?'}レース / 的中{best.hit_count}回
                        </p>
                      </div>
                    );
                  })()}
                </div>
                <div className="p-3 bg-red-50 rounded-lg">
                  <p className="text-xs text-red-600 mb-1">最高シャープレシオ</p>
                  {(() => {
                    const best = chartData.reduce((a, b) =>
                      a.sharpe_ratio > b.sharpe_ratio ? a : b
                    );
                    return (
                      <div>
                        <p className="font-semibold text-red-700">
                          {best.sharpe_ratio.toFixed(3)} (EV≥{best.ev_threshold})
                        </p>
                        <p className="text-xs text-red-500">
                          回収率: {best.return_rate_pct.toFixed(1)}%
                        </p>
                      </div>
                    );
                  })()}
                </div>
              </div>

              {/* 詳細データテーブル */}
              <details className="mt-4">
                <summary className="cursor-pointer text-sm text-gray-600 hover:text-gray-800">
                  詳細データを表示
                </summary>
                <div className="mt-2 max-h-64 overflow-y-auto">
                  <table className="w-full text-xs">
                    <thead className="bg-gray-100 sticky top-0">
                      <tr>
                        <th className="p-2 text-left">EV閾値</th>
                        <th className="p-2 text-right">回収率</th>
                        <th className="p-2 text-right">シャープ</th>
                        <th className="p-2 text-right">賭数</th>
                        <th className="p-2 text-right">レース数</th>
                        <th className="p-2 text-right">的中</th>
                        <th className="p-2 text-right">収支</th>
                      </tr>
                    </thead>
                    <tbody>
                      {chartData.map((d, i) => (
                        <tr key={i} className={d.return_rate_pct >= 100 ? 'bg-green-50' : ''}>
                          <td className="p-2">{d.ev_threshold.toFixed(2)}</td>
                          <td className={cn('p-2 text-right', d.return_rate_pct >= 100 ? 'text-green-600' : 'text-red-600')}>
                            {d.return_rate_pct.toFixed(1)}%
                          </td>
                          <td className="p-2 text-right">{d.sharpe_ratio.toFixed(3)}</td>
                          <td className="p-2 text-right">{d.bet_count}</td>
                          <td className="p-2 text-right text-gray-500">{d.race_count ?? '-'}</td>
                          <td className="p-2 text-right">{d.hit_count}</td>
                          <td className={cn('p-2 text-right', d.profit >= 0 ? 'text-green-600' : 'text-red-600')}>
                            {d.profit >= 0 ? '+' : ''}{d.profit.toLocaleString()}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </details>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function SimulationResultCard({ results }: { results: SimulationResult }) {
  const profitColor = results.profit >= 0 ? 'text-green-600' : 'text-red-600';
  const returnRateColor = results.return_rate >= 100 ? 'text-green-600' : 'text-red-600';

  return (
    <div className="space-y-4">
      {/* Model Info */}
      {results.model_version && (
        <div className="text-xs text-blue-600 bg-blue-50 px-2 py-1 rounded inline-block">
          モデル: {results.model_version} ({results.num_features}特徴量)
        </div>
      )}
      {/* Summary */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-gray-50 p-3 rounded-lg">
          <p className="text-xs text-gray-500">対象レース</p>
          <p className="font-semibold">{results.total_races}レース</p>
        </div>
        <div className="bg-gray-50 p-3 rounded-lg">
          <p className="text-xs text-gray-500">総賭け数</p>
          <p className="font-semibold">{results.total_bets}点</p>
        </div>
        <div className="bg-gray-50 p-3 rounded-lg">
          <p className="text-xs text-gray-500">的中率</p>
          <p className="font-semibold">{results.hit_rate}%</p>
        </div>
        <div className={cn('bg-gray-50 p-3 rounded-lg', returnRateColor)}>
          <p className="text-xs text-gray-500">回収率</p>
          <p className="font-semibold">{results.return_rate}%</p>
        </div>
      </div>

      {/* Financial Summary */}
      <div className="border-t pt-3">
        <div className="flex justify-between text-sm">
          <span>投資額</span>
          <span>{results.total_bet_amount.toLocaleString()}円</span>
        </div>
        <div className="flex justify-between text-sm">
          <span>払戻額</span>
          <span>{results.total_payout.toLocaleString()}円</span>
        </div>
        <div className={cn('flex justify-between font-semibold mt-1', profitColor)}>
          <span>収支</span>
          <span>
            {results.profit >= 0 ? '+' : ''}
            {results.profit.toLocaleString()}円
          </span>
        </div>
      </div>

      {/* By Bet Type */}
      <div className="border-t pt-3 space-y-3">
        {results.tansho && results.tansho.count > 0 && (
          <div className="text-sm">
            <p className="font-medium">単勝</p>
            <div className="grid grid-cols-3 gap-2 mt-1 text-gray-600">
              <span>{results.tansho.count}点</span>
              <span>的中率 {results.tansho.hit_rate}%</span>
              <span className={results.tansho.return_rate >= 100 ? 'text-green-600' : 'text-red-600'}>
                回収率 {results.tansho.return_rate}%
              </span>
            </div>
          </div>
        )}
        {results.umaren && results.umaren.count > 0 && (
          <div className="text-sm">
            <p className="font-medium">馬連</p>
            <div className="grid grid-cols-3 gap-2 mt-1 text-gray-600">
              <span>{results.umaren.count}点</span>
              <span>的中率 {results.umaren.hit_rate}%</span>
              <span className={results.umaren.return_rate >= 100 ? 'text-green-600' : 'text-red-600'}>
                回収率 {results.umaren.return_rate}%
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
