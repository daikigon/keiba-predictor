export interface PredictionHorse {
  horse_number: number;
  horse_id: string;
  horse_name?: string;
  predicted_rank: number;
  probability: number;
  score?: number;
  odds?: number;
  popularity?: number;
  tansho_ev?: number;  // 単勝期待値
}

export interface RecommendedBet {
  bet_type: string;
  detail: string;
  confidence: 'high' | 'medium' | 'low';
  horse_name?: string;
  horse_names?: string[];  // 馬連用
  expected_value?: number;  // 期待値
  probability?: number;
  odds?: number;
}

export interface PredictionResult {
  predictions: PredictionHorse[];
  recommended_bets: RecommendedBet[];
  model_type: 'ml' | 'baseline';
}

export interface Prediction {
  prediction_id: number;
  race_id: string;
  model_version: string;
  created_at: string;
  results: PredictionResult;
}

export interface History {
  id: number;
  prediction_id: number;
  bet_type: string;
  bet_detail: string;
  bet_amount?: number;
  is_hit?: boolean;
  payout?: number;
  created_at: string;
}

export interface HistorySummary {
  total_bets: number;
  total_hits: number;
  hit_rate: number;
  total_bet_amount: number;
  total_payout: number;
  roi: number;
}

export interface HistoryListResponse {
  total: number;
  items: History[];
  summary: HistorySummary;
}

export interface AccuracyStats {
  period: string;
  total_predictions: number;
  win_accuracy: number;
  show_accuracy: number;
  avg_top3_hit: number;
}

export interface ScrapeStats {
  total_races: number;
  total_entries: number;
  total_horses: number;
  total_jockeys: number;
  total_predictions: number;
  latest_race_date?: string;
}
