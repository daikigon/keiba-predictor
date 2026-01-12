-- 馬の事前計算済み特徴量テーブル
-- Option B: Colabでの当日予想用に特徴量を事前保存

-- horse_features テーブル
CREATE TABLE IF NOT EXISTS horse_features (
    id BIGSERIAL PRIMARY KEY,
    horse_id VARCHAR(20) NOT NULL UNIQUE,

    -- 基本情報
    horse_age INTEGER,
    horse_sex INTEGER,  -- 1:牡, 2:牝, 3:セ

    -- 過去成績（直近N走）
    avg_rank_last3 REAL,
    avg_rank_last5 REAL,
    avg_rank_last10 REAL,
    avg_rank_all REAL,

    -- 賞金
    prize_3races REAL,
    prize_5races REAL,
    prize_10races REAL,

    -- 勝率系
    win_rate REAL,
    place_rate REAL,
    show_rate REAL,
    best_rank INTEGER,
    total_runs INTEGER,

    -- 前走情報
    days_since_last INTEGER,
    last_result INTEGER,

    -- 上がり3F
    avg_last3f REAL,
    best_last3f REAL,

    -- コース適性（芝）
    turf_win_rate REAL,
    turf_show_rate REAL,
    turf_runs INTEGER,

    -- コース適性（ダート）
    dirt_win_rate REAL,
    dirt_show_rate REAL,
    dirt_runs INTEGER,

    -- 距離適性（短距離: ~1400m）
    short_win_rate REAL,
    short_show_rate REAL,
    short_runs INTEGER,

    -- 距離適性（マイル: 1401-1800m）
    mile_win_rate REAL,
    mile_show_rate REAL,
    mile_runs INTEGER,

    -- 距離適性（中距離: 1801-2200m）
    middle_win_rate REAL,
    middle_show_rate REAL,
    middle_runs INTEGER,

    -- 距離適性（長距離: 2201m~）
    long_win_rate REAL,
    long_show_rate REAL,
    long_runs INTEGER,

    -- 脚質
    running_style INTEGER,  -- 1:逃げ, 2:先行, 3:差し, 4:追込
    avg_first_corner REAL,
    avg_last_corner REAL,
    position_up_avg REAL,
    escape_rate REAL,
    front_rate REAL,
    stalker_rate REAL,
    closer_rate REAL,

    -- ペース
    avg_pace_first REAL,
    avg_pace_second REAL,
    avg_pace_diff REAL,
    pace_consistency REAL,

    -- 人気別成績
    high_pop_win_rate REAL,  -- 1-3番人気
    high_pop_show_rate REAL,
    high_pop_runs INTEGER,
    mid_pop_win_rate REAL,   -- 4-6番人気
    mid_pop_show_rate REAL,
    mid_pop_runs INTEGER,
    low_pop_win_rate REAL,   -- 7番人気以下
    low_pop_show_rate REAL,
    low_pop_runs INTEGER,
    avg_odds_when_win REAL,

    -- メタデータ
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- インデックス
    CONSTRAINT horse_features_horse_id_key UNIQUE (horse_id)
);

-- インデックス作成
CREATE INDEX IF NOT EXISTS idx_horse_features_horse_id ON horse_features(horse_id);
CREATE INDEX IF NOT EXISTS idx_horse_features_updated_at ON horse_features(updated_at);

-- jockey_features テーブル
CREATE TABLE IF NOT EXISTS jockey_features (
    id BIGSERIAL PRIMARY KEY,
    jockey_id VARCHAR(20) NOT NULL UNIQUE,

    -- 成績
    win_rate REAL,
    place_rate REAL,
    show_rate REAL,
    total_rides INTEGER,
    total_wins INTEGER,

    -- 年間成績
    year_rank INTEGER,
    year_wins INTEGER,
    year_rides INTEGER,
    year_earnings REAL,

    -- 芝/ダート別
    turf_win_rate REAL,
    dirt_win_rate REAL,

    -- メタデータ
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_jockey_features_jockey_id ON jockey_features(jockey_id);

-- trainer_features テーブル
CREATE TABLE IF NOT EXISTS trainer_features (
    id BIGSERIAL PRIMARY KEY,
    trainer_id VARCHAR(20) NOT NULL UNIQUE,

    -- 成績
    win_rate REAL,
    place_rate REAL,
    show_rate REAL,
    total_runs INTEGER,

    -- 年間成績
    year_rank INTEGER,
    year_wins INTEGER,

    -- メタデータ
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trainer_features_trainer_id ON trainer_features(trainer_id);

-- コメント
COMMENT ON TABLE horse_features IS '馬の事前計算済み特徴量（Colab予測用）';
COMMENT ON TABLE jockey_features IS '騎手の事前計算済み特徴量（Colab予測用）';
COMMENT ON TABLE trainer_features IS '調教師の事前計算済み特徴量（Colab予測用）';
