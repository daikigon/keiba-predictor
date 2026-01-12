-- racesテーブルに不足カラムを追加
ALTER TABLE races ADD COLUMN IF NOT EXISTS num_horses INTEGER;
ALTER TABLE races ADD COLUMN IF NOT EXISTS venue_detail VARCHAR(20);

-- entriesテーブルに不足カラムを追加
ALTER TABLE entries ADD COLUMN IF NOT EXISTS pace VARCHAR(20);
ALTER TABLE entries ADD COLUMN IF NOT EXISTS prize_money INTEGER;
ALTER TABLE entries ADD COLUMN IF NOT EXISTS winner_or_second VARCHAR(50);
