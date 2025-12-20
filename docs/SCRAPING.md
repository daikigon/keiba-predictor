# スクレイピング設計書

## 1. 対象サイト

- **サイト名**: netkeiba.com
- **URL**: https://race.netkeiba.com/
- **利用規約**: 確認済み (個人利用の範囲内で使用)

---

## 2. 取得対象ページ

### 2.1 レース一覧
- **URL**: `https://race.netkeiba.com/top/race_list.html?kaisai_date=YYYYMMDD`
- **取得情報**: 開催日のレース一覧

### 2.2 レース詳細 (出馬表)
- **URL**: `https://race.netkeiba.com/race/shutuba.html?race_id=XXXXXXXXXXXX`
- **取得情報**: 出走馬、騎手、斤量、オッズ等

### 2.3 レース結果
- **URL**: `https://race.netkeiba.com/race/result.html?race_id=XXXXXXXXXXXX`
- **取得情報**: 着順、タイム、上がり3F等

### 2.4 馬詳細
- **URL**: `https://db.netkeiba.com/horse/XXXXXXXXXX/`
- **取得情報**: 血統、過去成績等

### 2.5 騎手詳細
- **URL**: `https://db.netkeiba.com/jockey/XXXXX/`
- **取得情報**: 騎手成績

### 2.6 オッズ
- **URL**: `https://race.netkeiba.com/odds/index.html?race_id=XXXXXXXXXXXX`
- **取得情報**: 各種オッズ情報

---

## 3. race_id 形式

```
YYYYCCDDRRNN
|   |  |  ||
|   |  |  |+-- レース番号 (01-12)
|   |  |  +--- 日目 (01-12)
|   |  +------ 回数 (01-05)
|   +--------- 競馬場コード
+------------- 年
```

**競馬場コード:**
| コード | 競馬場 |
|--------|--------|
| 01 | 札幌 |
| 02 | 函館 |
| 03 | 福島 |
| 04 | 新潟 |
| 05 | 東京 |
| 06 | 中山 |
| 07 | 中京 |
| 08 | 京都 |
| 09 | 阪神 |
| 10 | 小倉 |

---

## 4. 実装方針

### 4.1 使用ライブラリ

```python
# HTTP リクエスト
requests  # 基本のHTTPリクエスト
httpx     # 非同期対応

# HTML パース
beautifulsoup4  # HTMLパース
lxml           # 高速パーサー

# JavaScript レンダリング (必要時)
selenium       # ブラウザ自動操作
playwright     # 代替
```

### 4.2 リクエスト設定

```python
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) ...",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
}

# リクエスト間隔
REQUEST_INTERVAL = 1.5  # 秒

# タイムアウト
TIMEOUT = 30  # 秒

# リトライ
MAX_RETRIES = 3
```

### 4.3 エラーハンドリング

```python
class ScraperError(Exception):
    pass

class RateLimitError(ScraperError):
    pass

class PageNotFoundError(ScraperError):
    pass

# リトライ戦略
# - 429: 待機時間を増やしてリトライ
# - 503: 一定時間後にリトライ
# - 404: スキップしてログ記録
```

---

## 5. データ取得フロー

```
[開始]
   |
   v
[日付指定] --> [レース一覧取得]
                    |
                    v
              [レースIDリスト]
                    |
          +---------+---------+
          |         |         |
          v         v         v
      [出馬表]  [オッズ]  [結果]
          |         |         |
          v         v         v
      [馬ID取得]    |         |
          |         |         |
          v         |         |
      [馬詳細]      |         |
          |         |         |
          +---------+---------+
                    |
                    v
              [DB保存]
                    |
                    v
                [完了]
```

---

## 6. クラス設計

```python
class BaseScraper:
    """スクレイパー基底クラス"""
    def __init__(self, session: requests.Session):
        self.session = session
    
    def fetch(self, url: str) -> str:
        """URL取得 (リトライ・間隔制御付き)"""
        pass
    
    def parse(self, html: str) -> dict:
        """HTMLパース (サブクラスで実装)"""
        raise NotImplementedError

class RaceListScraper(BaseScraper):
    """レース一覧スクレイパー"""
    def get_races(self, date: str) -> list[str]:
        pass

class RaceDetailScraper(BaseScraper):
    """レース詳細スクレイパー"""
    def get_entries(self, race_id: str) -> list[dict]:
        pass

class HorseScraper(BaseScraper):
    """馬情報スクレイパー"""
    def get_horse(self, horse_id: str) -> dict:
        pass
    
    def get_past_results(self, horse_id: str) -> list[dict]:
        pass

class OddsScraper(BaseScraper):
    """オッズスクレイパー"""
    def get_odds(self, race_id: str) -> dict:
        pass
```

---

## 7. スケジュール

| タイミング | 処理 |
|-----------|------|
| 毎週木曜 18:00 | 週末の出馬表取得 |
| レース当日 9:00 | オッズ情報更新 |
| レース当日 17:00 | 結果取得 |
| 毎日深夜 | 過去データ補完 |

---

## 8. 注意事項

1. **アクセス頻度**: 1.5秒以上の間隔を空ける
2. **robots.txt**: 確認して従う
3. **負荷**: 大量リクエストは深夜帯に実行
4. **個人利用**: 取得データは個人利用に限る
5. **キャッシュ**: 同一ページは再取得しない
