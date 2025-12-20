export interface HorseDetail {
  horse_id: string;
  name: string;
  sex: string;
  birth_year: number;
  father?: string;
  mother?: string;
  mother_father?: string;
  trainer?: string;
  owner?: string;
  breeder?: string;
}

export interface HorsePerformance {
  race_id: string;
  race_name: string;
  date: string;
  course: string;
  distance: number;
  track_type: string;
  result: number;
  odds: number;
  finish_time?: string;
  jockey_name?: string;
}
