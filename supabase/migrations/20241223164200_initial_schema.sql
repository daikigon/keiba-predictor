-- ========================================
-- 競馬予想アプリ Supabase スキーマ
-- ========================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ========================================
-- Horses (馬)
-- ========================================
CREATE TABLE IF NOT EXISTS horses (
    horse_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    sex VARCHAR(5) NOT NULL,
    birth_year INTEGER NOT NULL,
    father VARCHAR(50),
    mother VARCHAR(50),
    mother_father VARCHAR(50),
    trainer VARCHAR(50),
    owner VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ========================================
-- Jockeys (騎手)
-- ========================================
CREATE TABLE IF NOT EXISTS jockeys (
    jockey_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    win_rate FLOAT,
    place_rate FLOAT,
    show_rate FLOAT,
    year_rank INTEGER,
    year_wins INTEGER,
    year_rides INTEGER,
    year_earnings INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ========================================
-- Trainers (調教師)
-- ========================================
CREATE TABLE IF NOT EXISTS trainers (
    trainer_id VARCHAR(20) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    win_rate FLOAT,
    place_rate FLOAT,
    show_rate FLOAT,
    year_rank INTEGER,
    year_wins INTEGER,
    year_entries INTEGER,
    year_earnings INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ========================================
-- Sires (種牡馬)
-- ========================================
CREATE TABLE IF NOT EXISTS sires (
    sire_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    win_rate FLOAT,
    place_rate FLOAT,
    show_rate FLOAT,
    year_rank INTEGER,
    year_wins INTEGER,
    year_runners INTEGER,
    year_earnings INTEGER,
    turf_win_rate FLOAT,
    dirt_win_rate FLOAT,
    short_win_rate FLOAT,
    mile_win_rate FLOAT,
    middle_win_rate FLOAT,
    long_win_rate FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ========================================
-- Races (レース)
-- ========================================
CREATE TABLE IF NOT EXISTS races (
    race_id VARCHAR(20) PRIMARY KEY,
    date DATE NOT NULL,
    course VARCHAR(10) NOT NULL,
    race_number INTEGER NOT NULL,
    race_name VARCHAR(100),
    distance INTEGER NOT NULL,
    track_type VARCHAR(10) NOT NULL,
    weather VARCHAR(10),
    condition VARCHAR(10),
    grade VARCHAR(10),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_races_date ON races(date);

-- ========================================
-- Entries (出走馬)
-- ========================================
CREATE TABLE IF NOT EXISTS entries (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(20) NOT NULL REFERENCES races(race_id),
    horse_id VARCHAR(20) NOT NULL REFERENCES horses(horse_id),
    jockey_id VARCHAR(20) REFERENCES jockeys(jockey_id),
    frame_number INTEGER,
    horse_number INTEGER NOT NULL,
    weight FLOAT,
    horse_weight INTEGER,
    weight_diff INTEGER,
    odds FLOAT,
    popularity INTEGER,
    result INTEGER,
    finish_time VARCHAR(10),
    margin VARCHAR(20),
    corner_position VARCHAR(20),
    last_3f FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_entries_race_id ON entries(race_id);
CREATE INDEX IF NOT EXISTS idx_entries_horse_id ON entries(horse_id);

-- ========================================
-- Trainings (調教データ)
-- ========================================
CREATE TABLE IF NOT EXISTS trainings (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(20) NOT NULL REFERENCES races(race_id),
    horse_id VARCHAR(20) NOT NULL REFERENCES horses(horse_id),
    horse_number INTEGER,
    training_course VARCHAR(50),
    training_time VARCHAR(20),
    lap_times VARCHAR(50),
    training_rank VARCHAR(5),
    training_date VARCHAR(20),
    rider VARCHAR(50),
    comment VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_trainings_race_id ON trainings(race_id);
CREATE INDEX IF NOT EXISTS idx_trainings_horse_id ON trainings(horse_id);

-- ========================================
-- Predictions (予測結果)
-- ========================================
CREATE TABLE IF NOT EXISTS predictions (
    id SERIAL PRIMARY KEY,
    race_id VARCHAR(20) NOT NULL REFERENCES races(race_id),
    model_version VARCHAR(50) NOT NULL,
    results_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_predictions_race_id ON predictions(race_id);
CREATE INDEX IF NOT EXISTS idx_predictions_created_at ON predictions(created_at);

-- ========================================
-- History (馬券履歴)
-- ========================================
CREATE TABLE IF NOT EXISTS history (
    id SERIAL PRIMARY KEY,
    prediction_id INTEGER NOT NULL REFERENCES predictions(id),
    bet_type VARCHAR(20) NOT NULL,
    bet_detail VARCHAR(50) NOT NULL,
    bet_amount INTEGER,
    is_hit BOOLEAN,
    payout INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL
);

-- ========================================
-- Updated_at トリガー関数
-- ========================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- トリガーの設定
CREATE TRIGGER update_horses_updated_at BEFORE UPDATE ON horses
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_jockeys_updated_at BEFORE UPDATE ON jockeys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_trainers_updated_at BEFORE UPDATE ON trainers
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_sires_updated_at BEFORE UPDATE ON sires
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_races_updated_at BEFORE UPDATE ON races
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_entries_updated_at BEFORE UPDATE ON entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ========================================
-- Row Level Security (RLS)
-- フロントエンドから読み取り専用でアクセス
-- ========================================
ALTER TABLE horses ENABLE ROW LEVEL SECURITY;
ALTER TABLE jockeys ENABLE ROW LEVEL SECURITY;
ALTER TABLE trainers ENABLE ROW LEVEL SECURITY;
ALTER TABLE sires ENABLE ROW LEVEL SECURITY;
ALTER TABLE races ENABLE ROW LEVEL SECURITY;
ALTER TABLE entries ENABLE ROW LEVEL SECURITY;
ALTER TABLE trainings ENABLE ROW LEVEL SECURITY;
ALTER TABLE predictions ENABLE ROW LEVEL SECURITY;
ALTER TABLE history ENABLE ROW LEVEL SECURITY;

-- 全ユーザーに読み取り許可
CREATE POLICY "Allow public read access" ON horses FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON jockeys FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON trainers FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON sires FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON races FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON entries FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON trainings FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON predictions FOR SELECT USING (true);
CREATE POLICY "Allow public read access" ON history FOR SELECT USING (true);

-- Service Role (Colab) には全権限
CREATE POLICY "Allow service role full access" ON horses FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON jockeys FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON trainers FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON sires FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON races FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON entries FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON trainings FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON predictions FOR ALL USING (auth.role() = 'service_role');
CREATE POLICY "Allow service role full access" ON history FOR ALL USING (auth.role() = 'service_role');
