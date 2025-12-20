export interface Horse {
  horse_id: string;
  name: string;
  sex?: string;
  birth_year?: number;
  father?: string;
  mother?: string;
  trainer?: string;
}

export interface Jockey {
  jockey_id: string;
  name: string;
  win_rate?: number;
  place_rate?: number;
  show_rate?: number;
}

export interface Entry {
  horse_number: number;
  frame_number?: number;
  horse_id: string;
  horse_name?: string;
  horse?: Horse;
  jockey_id?: string;
  jockey_name?: string;
  jockey?: Jockey;
  weight?: number;
  horse_weight?: number;
  weight_diff?: number;
  odds?: number;
  popularity?: number;
  result?: number;
  finish_time?: string;
  last_3f?: number;
}

export interface Race {
  race_id: string;
  date: string;
  course: string;
  race_number: number;
  race_name?: string;
  distance: number;
  track_type: string;
  weather?: string;
  condition?: string;
  grade?: string;
  entries?: Entry[];
}

export interface RaceListResponse {
  total: number;
  races: Race[];
}

export interface RaceDetailResponse extends Race {
  entries: Entry[];
}
