import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// Supabaseが設定されているかチェック
export const isSupabaseConfigured = Boolean(supabaseUrl && supabaseAnonKey);

// Supabaseクライアント（設定されている場合のみ作成）
export const supabase = isSupabaseConfigured
  ? createClient(supabaseUrl!, supabaseAnonKey!)
  : null;

// データベース型定義
export interface DbRace {
  race_id: string;
  date: string;
  course: string;
  race_number: number;
  race_name: string | null;
  distance: number;
  track_type: string;
  weather: string | null;
  condition: string | null;
  grade: string | null;
  created_at: string;
  updated_at: string;
}

export interface DbEntry {
  id: number;
  race_id: string;
  horse_id: string;
  jockey_id: string | null;
  frame_number: number | null;
  horse_number: number;
  weight: number | null;
  horse_weight: number | null;
  weight_diff: number | null;
  odds: number | null;
  popularity: number | null;
  result: number | null;
  finish_time: string | null;
  margin: string | null;
  corner_position: string | null;
  last_3f: number | null;
  created_at: string;
  updated_at: string;
}

export interface DbHorse {
  horse_id: string;
  name: string;
  sex: string;
  birth_year: number;
  father: string | null;
  mother: string | null;
  mother_father: string | null;
  trainer: string | null;
  owner: string | null;
  created_at: string;
  updated_at: string;
}

export interface DbJockey {
  jockey_id: string;
  name: string;
  win_rate: number | null;
  place_rate: number | null;
  show_rate: number | null;
  year_rank: number | null;
  year_wins: number | null;
  year_rides: number | null;
  year_earnings: number | null;
  created_at: string;
  updated_at: string;
}

export interface DbPrediction {
  id: number;
  race_id: string;
  model_version: string;
  results_json: Record<string, unknown>;
  created_at: string;
}
