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
  runSimulationSync,
  type CurrentModel,
  type ModelVersion,
  type RetrainingStatus,
  type FeatureImportance,
  type SimulationResult,
  type SimulationStatus,
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
} from 'lucide-react';

export default function ModelPage() {
  const [currentModel, setCurrentModel] = useState<CurrentModel | null>(null);
  const [versions, setVersions] = useState<ModelVersion[]>([]);
  const [retrainingStatus, setRetrainingStatus] = useState<RetrainingStatus | null>(null);
  const [featureImportance, setFeatureImportance] = useState<FeatureImportance[]>([]);
  const [simulationStatus, setSimulationStatus] = useState<SimulationStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRetraining, setIsRetraining] = useState(false);
  const [isSimulating, setIsSimulating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendAvailable, setBackendAvailable] = useState(true);

  // Training parameters
  const [trainParams, setTrainParams] = useState({
    use_time_split: true,
    train_end_date: '',
    valid_end_date: '',
    num_boost_round: 1000,
  });

  // Simulation parameters
  const [simParams, setSimParams] = useState({
    ev_threshold: 1.0,
    umaren_ev_threshold: 1.2,
    bet_type: 'all' as 'tansho' | 'umaren' | 'all',
    bet_amount: 100,
    limit: 200,
    start_date: '',  // テスト期間開始日
    end_date: '',    // テスト期間終了日
  });

  const loadData = useCallback(async () => {
    let failedCount = 0;
    try {
      const [model, vers, status, features, simStatus] = await Promise.all([
        getCurrentModel().catch(() => {
          failedCount++;
          return null;
        }),
        getModelVersions().catch(() => {
          failedCount++;
          return [];
        }),
        getRetrainingStatus().catch(() => {
          failedCount++;
          return null;
        }),
        getFeatureImportance(15).catch(() => {
          failedCount++;
          return [];
        }),
        getSimulationStatus().catch(() => {
          failedCount++;
          return null;
        }),
      ]);

      // 全てのAPIが失敗した場合はバックエンドが利用不可
      if (failedCount >= 5) {
        setBackendAvailable(false);
      } else {
        setBackendAvailable(true);
      }

      setCurrentModel(model);
      setVersions(vers);
      setRetrainingStatus(status);
      setFeatureImportance(features);
      setSimulationStatus(simStatus);
      setError(null);
    } catch {
      setBackendAvailable(false);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Poll for status updates during retraining or simulation
  useEffect(() => {
    if (retrainingStatus?.is_running || simulationStatus?.is_running) {
      const interval = setInterval(async () => {
        try {
          const [status, simStatus] = await Promise.all([
            getRetrainingStatus(),
            getSimulationStatus(),
          ]);
          setRetrainingStatus(status);
          setSimulationStatus(simStatus);

          if (!status.is_running && !simStatus.is_running) {
            loadData();
          }
        } catch (err) {
          console.error('Failed to poll status:', err);
        }
      }, 2000);

      return () => clearInterval(interval);
    }
  }, [retrainingStatus?.is_running, simulationStatus?.is_running, loadData]);

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
    try {
      const params = trainParams.use_time_split
        ? {
            use_time_split: true,
            train_end_date: trainParams.train_end_date,
            valid_end_date: trainParams.valid_end_date,
            num_boost_round: trainParams.num_boost_round,
          }
        : {
            num_boost_round: trainParams.num_boost_round,
          };
      await startRetraining(params);
      const status = await getRetrainingStatus();
      setRetrainingStatus(status);
    } catch (err) {
      setError('再学習の開始に失敗しました');
      console.error(err);
    } finally {
      setIsRetraining(false);
    }
  };

  const handleSwitchModel = async (version: string) => {
    try {
      const result = await switchModel(version);
      setCurrentModel(result.model);
      await loadData();
    } catch (err) {
      setError('モデルの切り替えに失敗しました');
      console.error(err);
    }
  };

  const handleSimulate = async () => {
    setIsSimulating(true);
    setError(null);
    try {
      // 空の日付は除外
      const params = {
        ...simParams,
        start_date: simParams.start_date || undefined,
        end_date: simParams.end_date || undefined,
      };
      const results = await runSimulationSync(params);
      setSimulationStatus({
        is_running: false,
        progress: 0,
        total: 0,
        results,
        error: null,
      });
    } catch (err) {
      setError('シミュレーションに失敗しました');
      console.error(err);
    } finally {
      setIsSimulating(false);
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
        <h1 className="text-2xl font-bold text-gray-900">モデル管理</h1>
        <p className="text-gray-500 mt-1">機械学習モデルの管理とシミュレーション</p>
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
              {retrainingStatus?.is_running ? (
                <div className="space-y-3 p-3 bg-blue-50 rounded-lg">
                  <div className="flex items-center gap-2 text-blue-600">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>再学習中... ({retrainingStatus.progress})</span>
                  </div>
                </div>
              ) : retrainingStatus?.result ? (
                <div className="space-y-2 p-3 bg-green-50 rounded-lg">
                  <div className="flex items-center gap-2 text-green-600">
                    <CheckCircle className="w-4 h-4" />
                    <span>最後の再学習: 成功</span>
                  </div>
                  <div className="text-sm text-gray-500">
                    <p>バージョン: {retrainingStatus.result.version}</p>
                    <p>検証スコア: {retrainingStatus.result.valid_score?.toFixed(4)}</p>
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
      <Card className={cn("mt-6", !backendAvailable && "opacity-60 pointer-events-none")}>
        <CardHeader>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-indigo-600" />
            <CardTitle>期待値シミュレーション</CardTitle>
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
                    単勝EV閾値
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
                    馬連EV閾値
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
              ) : simulationStatus?.results ? (
                <SimulationResultCard results={simulationStatus.results} />
              ) : simulationStatus?.error ? (
                <div className="text-red-600 p-4 bg-red-50 rounded-lg">
                  {simulationStatus.error}
                </div>
              ) : (
                <p className="text-gray-500 text-center py-8">
                  シミュレーションを実行してください
                </p>
              )}
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

function SimulationResultCard({ results }: { results: SimulationResult }) {
  const profitColor = results.profit >= 0 ? 'text-green-600' : 'text-red-600';
  const returnRateColor = results.return_rate >= 100 ? 'text-green-600' : 'text-red-600';

  return (
    <div className="space-y-4">
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
