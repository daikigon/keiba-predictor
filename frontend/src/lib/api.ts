import { API_BASE_URL } from './constants';
import { isSupabaseConfigured } from './supabase';
import {
  getRacesFromSupabase,
  getRaceDetailFromSupabase,
  getPredictionFromSupabase,
  getHorsesFromSupabase,
  getJockeysFromSupabase,
  getStatsFromSupabase,
} from './supabase-api';
import type { RaceListResponse, RaceDetailResponse } from '@/types/race';
import type {
  Prediction,
  HistoryListResponse,
  History,
  HistorySummary,
  AccuracyStats,
  ScrapeStats,
} from '@/types/prediction';

// 本番環境（Supabase直接接続）かどうか
// API_BASE_URLが空で、かつSupabaseが設定されている場合のみSupabaseモード
const useSupabase = !API_BASE_URL && isSupabaseConfigured;

class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
    this.name = 'ApiError';
  }
}

interface FetchOptions extends RequestInit {
  timeout?: number;
}

async function fetchApi<T>(endpoint: string, options?: FetchOptions): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  const { timeout, ...fetchOptions } = options || {};

  const controller = new AbortController();
  const timeoutId = timeout ? setTimeout(() => controller.abort(), timeout) : null;

  try {
    const res = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
      headers: {
        'Content-Type': 'application/json',
        ...fetchOptions?.headers,
      },
    });

    if (!res.ok) {
      throw new ApiError(res.status, `API error: ${res.statusText}`);
    }

    return res.json();
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

// Races API
export async function getRaces(date?: string, raceType?: string): Promise<RaceListResponse> {
  if (useSupabase && isSupabaseConfigured) {
    return getRacesFromSupabase(date, raceType);
  }
  const params = new URLSearchParams();
  if (date) params.append('target_date', date);
  if (raceType) params.append('race_type', raceType);
  const queryString = params.toString() ? `?${params.toString()}` : '';
  return fetchApi<RaceListResponse>(`/api/v1/races${queryString}`);
}

export async function getRaceDetail(raceId: string): Promise<RaceDetailResponse> {
  if (useSupabase && isSupabaseConfigured) {
    return getRaceDetailFromSupabase(raceId);
  }
  return fetchApi<RaceDetailResponse>(`/api/v1/races/${raceId}`);
}

// Predictions API
export async function createPrediction(raceId: string): Promise<Prediction> {
  return fetchApi<Prediction>(`/api/v1/predictions?race_id=${raceId}`, {
    method: 'POST',
  });
}

export async function getPrediction(raceId: string): Promise<Prediction | null> {
  if (useSupabase && isSupabaseConfigured) {
    return getPredictionFromSupabase(raceId);
  }
  try {
    return await fetchApi<Prediction>(`/api/v1/predictions/${raceId}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

// History API
export async function getHistory(params?: {
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}): Promise<HistoryListResponse> {
  const searchParams = new URLSearchParams();
  if (params?.from_date) searchParams.set('from_date', params.from_date);
  if (params?.to_date) searchParams.set('to_date', params.to_date);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  const response = await fetchApi<{
    total: number;
    summary: HistorySummary;
    history: History[];
  }>(`/api/v1/history${query ? `?${query}` : ''}`);

  return {
    total: response.total,
    summary: response.summary,
    items: response.history,
  };
}

export async function createHistory(data: {
  prediction_id: number;
  bet_type: string;
  bet_detail: string;
  bet_amount?: number;
}): Promise<History> {
  return fetchApi<History>('/api/v1/history', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateHistoryResult(
  historyId: number,
  data: { is_hit: boolean; payout?: number }
): Promise<History> {
  return fetchApi<History>(`/api/v1/history/${historyId}/result`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// Stats API
export async function getAccuracyStats(period?: string): Promise<AccuracyStats> {
  const params = period ? `?period=${period}` : '';
  return fetchApi<AccuracyStats>(`/api/v1/stats/accuracy${params}`);
}

export async function getScrapeStats(raceType?: string): Promise<ScrapeStats> {
  if (useSupabase && isSupabaseConfigured) {
    return getStatsFromSupabase(raceType);
  }
  const params = raceType ? `?race_type=${raceType}` : '';
  const response = await fetchApi<{
    status: string;
    race_type: string | null;
    last_updated: string | null;
    counts: {
      total_races: number;
      total_horses: number;
      total_jockeys: number;
      total_entries: number;
      total_predictions: number;
      today_races: number;
    };
    date_range: {
      oldest: string | null;
      newest: string | null;
    };
  }>(`/api/v1/stats/scrape${params}`);

  return {
    total_races: response.counts.total_races,
    total_entries: response.counts.total_entries,
    total_horses: response.counts.total_horses,
    total_jockeys: response.counts.total_jockeys,
    total_predictions: response.counts.total_predictions,
    latest_race_date: response.date_range.newest || undefined,
  };
}

// Scraping API
export interface ScrapeResult {
  status: string;
  message: string;
  races_count: number;
  saved_count: number;
  races: Array<{ race_id: string; race_name: string }>;
}

export interface ScrapeDetailResult {
  status: string;
  saved: boolean;
  skipped: boolean;
  reason?: string;
  race: {
    race_id: string;
    race_name: string;
    entries?: Array<{ horse_number: number; horse_name: string }>;
    entries_count?: number;
  };
}

export async function scrapeRaceList(
  targetDate: string,
  jraOnly: boolean = false,
  raceType?: string
): Promise<ScrapeResult> {
  const params = new URLSearchParams();
  params.append('target_date', targetDate);
  params.append('save_to_db', 'true');
  if (raceType) {
    params.append('race_type', raceType);
  } else if (jraOnly) {
    params.append('jra_only', 'true');
  }
  return fetchApi<ScrapeResult>(`/api/v1/races/scrape?${params.toString()}`, { method: 'POST' });
}

export async function scrapeRaceDetail(raceId: string, force: boolean = false): Promise<ScrapeDetailResult> {
  return fetchApi<ScrapeDetailResult>(
    `/api/v1/races/scrape/${raceId}?save_to_db=true&force=${force}`,
    { method: 'POST' }
  );
}

// Today's Race Card Scraping API (出馬表)
export async function scrapeRaceCardList(
  targetDate: string,
  jraOnly: boolean = false,
  raceType?: string
): Promise<ScrapeResult> {
  const params = new URLSearchParams();
  params.append('target_date', targetDate);
  params.append('save_to_db', 'true');
  if (raceType) {
    params.append('race_type', raceType);
  } else if (jraOnly) {
    params.append('jra_only', 'true');
  }
  return fetchApi<ScrapeResult>(`/api/v1/races/scrape-card?${params.toString()}`, { method: 'POST' });
}

export async function scrapeRaceCardDetail(raceId: string, force: boolean = false): Promise<ScrapeDetailResult> {
  return fetchApi<ScrapeDetailResult>(
    `/api/v1/races/scrape-card/${raceId}?save_to_db=true&force=${force}`,
    { method: 'POST' }
  );
}

// Horses API
export interface Horse {
  horse_id: string;
  name: string;
  sex: string;
  birth_year: number;
  father?: string;
  mother?: string;
  trainer?: string;
  entries_count: number;
}

export interface HorseListResponse {
  total: number;
  horses: Horse[];
}

export interface HorseDetail extends Horse {
  mother_father?: string;
  owner?: string;
  race_history: Array<{
    race_id: string;
    date: string;
    venue_detail?: string;
    weather?: string;
    race_number?: number;
    race_name: string;
    num_horses?: number;
    course: string;
    distance: number;
    track_type: string;
    condition?: string;
    frame_number?: number;
    horse_number: number;
    odds?: number;
    popularity?: number;
    result?: number;
    jockey_name?: string;
    weight?: number;
    finish_time?: string;
    margin?: string;
    corner_position?: string;
    pace?: string;
    last_3f?: number;
    horse_weight?: number;
    weight_diff?: number;
    prize_money?: number;
    winner_or_second?: string;
  }>;
}

export async function getHorses(params?: {
  search?: string;
  sex?: string;
  race_type?: string;
  limit?: number;
  offset?: number;
}): Promise<HorseListResponse> {
  if (useSupabase && isSupabaseConfigured) {
    return getHorsesFromSupabase(params);
  }
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set('search', params.search);
  if (params?.sex) searchParams.set('sex', params.sex);
  if (params?.race_type) searchParams.set('race_type', params.race_type);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());
  const query = searchParams.toString();
  return fetchApi<HorseListResponse>(`/api/v1/horses${query ? `?${query}` : ''}`);
}

export async function getHorseDetail(horseId: string): Promise<HorseDetail> {
  return fetchApi<HorseDetail>(`/api/v1/horses/${horseId}`);
}

export interface RescrapeResult {
  success: boolean;
  horse_id: string;
  horse_name: string;
  scraped_races: number;
  updated_entries: number;
  created_entries: number;
  updated_races: number;
  created_races: number;
}

export async function rescrapeHorseData(horseId: string): Promise<RescrapeResult> {
  return fetchApi<RescrapeResult>(`/api/v1/horses/${horseId}/rescrape`, {
    method: 'POST',
  });
}

// Bulk Rescrape API
export interface BulkRescrapeStatus {
  is_running: boolean;
  progress: number;
  total: number;
  current_horse: string | null;
  results: {
    processed_horses: number;
    failed_horses: number;
    total_scraped_races: number;
    created_entries: number;
    updated_entries: number;
    created_races: number;
    updated_races: number;
    failures: Array<{ horse_id: string; name: string; error: string }>;
  } | null;
  error: string | null;
}

export async function startBulkRescrape(): Promise<{ status: string; message: string }> {
  return fetchApi<{ status: string; message: string }>('/api/v1/horses/bulk-rescrape', {
    method: 'POST',
  });
}

export async function getBulkRescrapeStatus(): Promise<BulkRescrapeStatus> {
  const response = await fetchApi<{ status: string; bulk_rescrape: BulkRescrapeStatus }>(
    '/api/v1/horses/bulk-rescrape/status'
  );
  return response.bulk_rescrape;
}

// Jockeys API
export interface Jockey {
  jockey_id: string;
  name: string;
  entries_count: number;
  wins: number;
  win_rate: number;
  place_rate: number;
  show_rate: number;
}

export interface JockeyListResponse {
  total: number;
  jockeys: Jockey[];
}

export interface JockeyDetail {
  jockey_id: string;
  name: string;
  stats: {
    total_entries: number;
    wins: number;
    win_rate: number;
    place_rate: number;
    show_rate: number;
  };
  race_history: Array<{
    race_id: string;
    date: string;
    race_name: string;
    course: string;
    distance: number;
    track_type: string;
    horse_number: number;
    horse_name?: string;
    result?: number;
    odds?: number;
    popularity?: number;
  }>;
}

export async function getJockeys(params?: {
  search?: string;
  race_type?: string;
  limit?: number;
  offset?: number;
}): Promise<JockeyListResponse> {
  if (useSupabase && isSupabaseConfigured) {
    return getJockeysFromSupabase(params);
  }
  const searchParams = new URLSearchParams();
  if (params?.search) searchParams.set('search', params.search);
  if (params?.race_type) searchParams.set('race_type', params.race_type);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());
  const query = searchParams.toString();
  return fetchApi<JockeyListResponse>(`/api/v1/jockeys${query ? `?${query}` : ''}`);
}

export async function getJockeyDetail(jockeyId: string): Promise<JockeyDetail> {
  return fetchApi<JockeyDetail>(`/api/v1/jockeys/${jockeyId}`);
}

export interface RefreshNamesResult {
  status: string;
  total: number;
  updated: number;
  errors: number;
}

export async function refreshJockeyNames(): Promise<RefreshNamesResult> {
  return fetchApi<RefreshNamesResult>('/api/v1/jockeys/refresh-names', {
    method: 'POST',
    timeout: 180000, // 3 minutes for processing many jockeys
  });
}

// Model API
export interface ModelVersion {
  version: string;
  created_at: string;
  file_path?: string;
  size_bytes?: number;
  file_size_mb?: number;
  num_features?: number;
}

export interface CurrentModel {
  version: string;
  is_loaded: boolean;
  num_features: number;
  best_iteration?: number;
}

export interface RetrainingStatus {
  is_running: boolean;
  progress?: string;
  started_at?: string;
  error?: string;
  last_result?: {
    success: boolean;
    model_version: string;
    model_path?: string;
    // 評価指標
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
    // その他
    error?: string;
    started_at?: string;
    completed_at?: string;
  };
}

export interface FeatureImportance {
  feature: string;
  importance: number;
  gain?: number;
}

export interface SimulationParams {
  ev_threshold?: number;
  max_ev?: number;  // 期待値上限（高すぎる穴馬を除外）
  umaren_ev_threshold?: number;
  umaren_max_ev?: number;  // 馬連期待値上限
  bet_type?: 'tansho' | 'umaren' | 'all';
  bet_amount?: number;
  limit?: number;
  start_date?: string;  // YYYY-MM-DD形式（テスト期間開始）
  end_date?: string;    // YYYY-MM-DD形式（テスト期間終了）
  min_probability?: number;  // 最低確率フィルター（0-1）
  umaren_top_n?: number;  // 馬連の組み合わせ対象馬数
}

export interface SimulationBetTypeResult {
  count: number;
  hits: number;
  hit_rate: number;
  bet_amount: number;
  payout: number;
  return_rate: number;
}

export interface SimulationResult {
  total_races: number;
  total_bets: number;
  total_hits: number;
  hit_rate: number;
  total_bet_amount: number;
  total_payout: number;
  profit: number;
  return_rate: number;
  roi: number;
  tansho: SimulationBetTypeResult;
  umaren: SimulationBetTypeResult;
  params: SimulationParams;
}

export interface SimulationStatus {
  is_running: boolean;
  progress: number;
  total: number;
  results: SimulationResult | null;
  error: string | null;
}

export async function getModelVersions(raceType?: string): Promise<ModelVersion[]> {
  const params = raceType ? `?race_type=${raceType}` : '';
  const response = await fetchApi<{
    status: string;
    race_type?: string;
    count: number;
    versions: ModelVersion[];
  }>(`/api/v1/model/versions${params}`);
  return response.versions;
}

export async function getCurrentModel(raceType?: string): Promise<CurrentModel> {
  const params = raceType ? `?race_type=${raceType}` : '';
  const response = await fetchApi<{
    status: string;
    model: CurrentModel;
  }>(`/api/v1/model/current${params}`);
  return response.model;
}

export async function getRetrainingStatus(): Promise<RetrainingStatus> {
  const response = await fetchApi<{
    status: string;
    retraining_status: RetrainingStatus;
  }>('/api/v1/model/status');
  return response.retraining_status;
}

export interface RetrainParams {
  num_boost_round?: number;
  early_stopping?: number;
  // 従来モード用
  min_date?: string;
  valid_fraction?: number;
  // 時系列分割モード用
  use_time_split?: boolean;
  train_end_date?: string;  // 学習データ終了日
  valid_end_date?: string;  // 検証データ終了日
  // 競馬タイプ
  race_type?: string;  // 'central' | 'local' | 'banei'
}

export async function startRetraining(params?: RetrainParams): Promise<{ started_at: string }> {
  return fetchApi<{ status: string; started_at: string }>(
    '/api/v1/model/retrain',
    {
      method: 'POST',
      body: JSON.stringify(params || {}),
    }
  );
}

export async function switchModel(version: string, raceType?: string): Promise<{ model: CurrentModel }> {
  const params = new URLSearchParams();
  params.append('version', version);
  if (raceType) params.append('race_type', raceType);
  return fetchApi<{ status: string; model: CurrentModel }>(
    `/api/v1/model/switch?${params.toString()}`,
    { method: 'POST' }
  );
}

export async function getFeatureImportance(limit?: number, raceType?: string): Promise<FeatureImportance[]> {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());
  if (raceType) params.append('race_type', raceType);
  const queryString = params.toString() ? `?${params.toString()}` : '';
  const response = await fetchApi<{
    status: string;
    model_version: string;
    race_type?: string;
    features: FeatureImportance[];
  }>(`/api/v1/model/feature-importance${queryString}`);
  return response.features;
}

export async function startSimulation(params: SimulationParams): Promise<void> {
  await fetchApi<{ status: string }>('/api/v1/model/simulate', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export async function getSimulationStatus(): Promise<SimulationStatus> {
  const response = await fetchApi<{
    status: string;
    simulation: SimulationStatus;
  }>('/api/v1/model/simulate/status');
  return response.simulation;
}

export async function runSimulationSync(params: SimulationParams): Promise<SimulationResult> {
  const response = await fetchApi<{
    status: string;
    results: SimulationResult;
  }>('/api/v1/model/simulate/sync', {
    method: 'POST',
    body: JSON.stringify(params),
    timeout: 300000, // 5 minutes for sync simulation
  });
  return response.results;
}

// 閾値スイープ分析
export interface ThresholdSweepParams {
  bet_type: 'tansho' | 'umaren';
  ev_min?: number;
  ev_max?: number;
  ev_step?: number;
  max_ev?: number;
  min_probability?: number;
  umaren_top_n?: number;
  bet_amount?: number;
  limit?: number;
  start_date?: string;
  end_date?: string;
}

export interface ThresholdSweepDataPoint {
  ev_threshold: number;
  return_rate: number;
  sharpe_ratio: number;
  bet_count: number;
  hit_count: number;
  hit_rate: number;
  total_bet: number;
  total_payout: number;
  profit: number;
  race_count?: number;
}

export interface ThresholdSweepResult {
  bet_type: string;
  total_races: number;
  data: ThresholdSweepDataPoint[];
}

export async function startThresholdSweep(params: ThresholdSweepParams): Promise<void> {
  await fetchApi<{ status: string }>('/api/v1/model/simulate/threshold-sweep', {
    method: 'POST',
    body: JSON.stringify(params),
  });
}

export interface ThresholdSweepStatus {
  is_running: boolean;
  phase: 'idle' | 'preparing' | 'sweeping' | 'complete' | 'error';
  progress: number;
  total: number;
  current_threshold: number;
  total_thresholds: number;
  results: ThresholdSweepResult | null;
  error: string | null;
}

export async function getThresholdSweepStatus(): Promise<ThresholdSweepStatus> {
  const response = await fetchApi<{
    status: string;
    sweep: ThresholdSweepStatus;
  }>('/api/v1/model/simulate/threshold-sweep/status');
  return response.sweep;
}

export async function runThresholdSweepSync(params: ThresholdSweepParams): Promise<ThresholdSweepResult> {
  const response = await fetchApi<{
    status: string;
    bet_type: string;
    total_races: number;
    data: ThresholdSweepDataPoint[];
  }>('/api/v1/model/simulate/threshold-sweep/sync', {
    method: 'POST',
    body: JSON.stringify(params),
    timeout: 600000, // 10 minutes for sweep
  });
  return {
    bet_type: response.bet_type,
    total_races: response.total_races,
    data: response.data,
  };
}

// Sync API
export interface SyncStatus {
  is_running: boolean;
  progress: number;
  total: number;
  current_table: string | null;
  results: {
    horses: { synced: number; errors: number; skipped: number };
    jockeys: { synced: number; errors: number; skipped: number };
    races: { synced: number; errors: number; skipped: number };
    entries: { synced: number; errors: number; skipped: number };
  } | null;
  error: string | null;
  last_sync_at: string | null;
  pending_retries: number;
}

export async function startSyncToSupabase(forceFull: boolean = false): Promise<{ status: string; message: string; mode: string }> {
  const params = forceFull ? '?force_full=true' : '';
  return fetchApi<{ status: string; message: string; mode: string }>(`/api/v1/sync/to-supabase${params}`, {
    method: 'POST',
  });
}

export async function getSyncStatus(): Promise<SyncStatus> {
  return fetchApi<SyncStatus>('/api/v1/sync/status');
}

export { ApiError };
