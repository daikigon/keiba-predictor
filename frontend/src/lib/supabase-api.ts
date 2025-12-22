/**
 * Supabase直接接続用API関数
 *
 * Vercelデプロイ時（FastAPIバックエンドなし）に使用
 */
import { supabase, DbRace, DbEntry, DbHorse, DbJockey, DbPrediction } from './supabase';
import type { Race, RaceListResponse, RaceDetailResponse, Entry } from '@/types/race';
import type { Prediction } from '@/types/prediction';

// レース一覧を取得
export async function getRacesFromSupabase(targetDate?: string): Promise<RaceListResponse> {
  if (!supabase) throw new Error('Supabase is not configured');

  let query = supabase
    .from('races')
    .select('*')
    .order('date', { ascending: false })
    .order('race_number', { ascending: true });

  if (targetDate) {
    query = query.eq('date', targetDate);
  }

  const { data, error } = await query.limit(100);

  if (error) throw error;

  const races: Race[] = (data || []).map((race: DbRace) => ({
    race_id: race.race_id,
    date: race.date,
    course: race.course,
    race_number: race.race_number,
    race_name: race.race_name || '',
    distance: race.distance,
    track_type: race.track_type,
    weather: race.weather || undefined,
    condition: race.condition || undefined,
    grade: race.grade || undefined,
  }));

  return { total: races.length, races };
}

// レース詳細を取得
export async function getRaceDetailFromSupabase(raceId: string): Promise<RaceDetailResponse> {
  if (!supabase) throw new Error('Supabase is not configured');

  // レース情報
  const { data: race, error: raceError } = await supabase
    .from('races')
    .select('*')
    .eq('race_id', raceId)
    .single();

  if (raceError) throw raceError;

  // 出走馬情報（馬・騎手情報も取得）
  const { data: entries, error: entriesError } = await supabase
    .from('entries')
    .select(`
      *,
      horses:horse_id (name, sex, birth_year, father, trainer),
      jockeys:jockey_id (name)
    `)
    .eq('race_id', raceId)
    .order('horse_number', { ascending: true });

  if (entriesError) throw entriesError;

  const formattedEntries: Entry[] = (entries || []).map((entry: DbEntry & { horses?: DbHorse; jockeys?: DbJockey }) => ({
    horse_number: entry.horse_number,
    horse_id: entry.horse_id,
    horse_name: entry.horses?.name || '不明',
    jockey_id: entry.jockey_id || undefined,
    jockey_name: entry.jockeys?.name || undefined,
    frame_number: entry.frame_number || undefined,
    weight: entry.weight || undefined,
    horse_weight: entry.horse_weight || undefined,
    weight_diff: entry.weight_diff || undefined,
    odds: entry.odds || undefined,
    popularity: entry.popularity || undefined,
    result: entry.result || undefined,
    finish_time: entry.finish_time || undefined,
    margin: entry.margin || undefined,
    corner_position: entry.corner_position || undefined,
    last_3f: entry.last_3f || undefined,
    sex: entry.horses?.sex,
    age: entry.horses?.birth_year
      ? new Date().getFullYear() - entry.horses.birth_year
      : undefined,
    father: entry.horses?.father || undefined,
    trainer: entry.horses?.trainer || undefined,
  }));

  return {
    race_id: race.race_id,
    date: race.date,
    course: race.course,
    race_number: race.race_number,
    race_name: race.race_name || '',
    distance: race.distance,
    track_type: race.track_type,
    weather: race.weather || undefined,
    condition: race.condition || undefined,
    grade: race.grade || undefined,
    entries: formattedEntries,
  };
}

// 予測を取得
export async function getPredictionFromSupabase(raceId: string): Promise<Prediction | null> {
  if (!supabase) throw new Error('Supabase is not configured');

  const { data, error } = await supabase
    .from('predictions')
    .select('*')
    .eq('race_id', raceId)
    .order('created_at', { ascending: false })
    .limit(1)
    .single();

  if (error) {
    if (error.code === 'PGRST116') {
      // No rows found
      return null;
    }
    throw error;
  }

  const resultsJson = data.results_json as {
    predictions?: Array<{
      horse_number: number;
      horse_id: string;
      horse_name?: string;
      predicted_rank: number;
      probability: number;
      score?: number;
      odds?: number;
      popularity?: number;
      tansho_ev?: number;
    }>;
    recommended_bets?: Array<{
      bet_type: string;
      detail: string;
      confidence: 'high' | 'medium' | 'low';
      horse_name?: string;
      horse_names?: string[];
      expected_value?: number;
      probability?: number;
      odds?: number;
    }>;
    model_type?: 'ml' | 'baseline';
  };

  return {
    prediction_id: data.id,
    race_id: data.race_id,
    model_version: data.model_version,
    created_at: data.created_at,
    results: {
      predictions: resultsJson?.predictions || [],
      recommended_bets: resultsJson?.recommended_bets || [],
      model_type: resultsJson?.model_type || 'ml',
    },
  };
}

// 馬一覧を取得
export async function getHorsesFromSupabase(params?: {
  search?: string;
  sex?: string;
  limit?: number;
  offset?: number;
}) {
  if (!supabase) throw new Error('Supabase is not configured');

  let query = supabase
    .from('horses')
    .select('*', { count: 'exact' });

  if (params?.search) {
    query = query.ilike('name', `%${params.search}%`);
  }
  if (params?.sex) {
    query = query.eq('sex', params.sex);
  }

  const limit = params?.limit || 50;
  const offset = params?.offset || 0;
  query = query.range(offset, offset + limit - 1);

  const { data, count, error } = await query.order('name');

  if (error) throw error;

  return {
    total: count || 0,
    horses: (data || []).map((horse: DbHorse) => ({
      horse_id: horse.horse_id,
      name: horse.name,
      sex: horse.sex,
      birth_year: horse.birth_year,
      father: horse.father || undefined,
      mother: horse.mother || undefined,
      trainer: horse.trainer || undefined,
      entries_count: 0, // 別途取得が必要
    })),
  };
}

// 騎手一覧を取得
export async function getJockeysFromSupabase(params?: {
  search?: string;
  limit?: number;
  offset?: number;
}) {
  if (!supabase) throw new Error('Supabase is not configured');

  let query = supabase
    .from('jockeys')
    .select('*', { count: 'exact' });

  if (params?.search) {
    query = query.ilike('name', `%${params.search}%`);
  }

  const limit = params?.limit || 50;
  const offset = params?.offset || 0;
  query = query.range(offset, offset + limit - 1);

  const { data, count, error } = await query.order('name');

  if (error) throw error;

  return {
    total: count || 0,
    jockeys: (data || []).map((jockey: DbJockey) => ({
      jockey_id: jockey.jockey_id,
      name: jockey.name,
      entries_count: 0,
      wins: jockey.year_wins || 0,
      win_rate: jockey.win_rate || 0,
      place_rate: jockey.place_rate || 0,
      show_rate: jockey.show_rate || 0,
    })),
  };
}

// 統計情報を取得
export async function getStatsFromSupabase() {
  if (!supabase) throw new Error('Supabase is not configured');

  const [races, entries, horses, jockeys, predictions] = await Promise.all([
    supabase.from('races').select('*', { count: 'exact', head: true }),
    supabase.from('entries').select('*', { count: 'exact', head: true }),
    supabase.from('horses').select('*', { count: 'exact', head: true }),
    supabase.from('jockeys').select('*', { count: 'exact', head: true }),
    supabase.from('predictions').select('*', { count: 'exact', head: true }),
  ]);

  // 最新レース日付
  const { data: latestRace } = await supabase
    .from('races')
    .select('date')
    .order('date', { ascending: false })
    .limit(1)
    .single();

  return {
    total_races: races.count || 0,
    total_entries: entries.count || 0,
    total_horses: horses.count || 0,
    total_jockeys: jockeys.count || 0,
    total_predictions: predictions.count || 0,
    latest_race_date: latestRace?.date,
  };
}
