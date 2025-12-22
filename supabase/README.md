# Supabase セットアップガイド

## 1. Supabase プロジェクト作成

1. [Supabase](https://supabase.com) でアカウント作成
2. 「New Project」でプロジェクト作成
3. リージョン: `Northeast Asia (Tokyo)` 推奨
4. データベースパスワードを設定（控えておく）

## 2. データベーススキーマの適用

1. Supabase ダッシュボードで「SQL Editor」を開く
2. `migrations/001_initial_schema.sql` の内容をコピー＆ペースト
3. 「Run」で実行

## 3. API キーの取得

Supabase ダッシュボード → Settings → API から取得:

- **Project URL**: `https://xxxxx.supabase.co`
- **anon key**: フロントエンド用（読み取り専用）
- **service_role key**: Colab用（書き込み可能）

## 4. 環境変数の設定

### Vercel（フロントエンド）
```
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
```

### Google Colab
```python
import os
os.environ['SUPABASE_URL'] = 'https://xxxxx.supabase.co'
os.environ['SUPABASE_SERVICE_KEY'] = 'eyJhbGciOiJIUzI1NiIs...'
```

## 5. RLS（Row Level Security）について

スキーマでは以下のポリシーが設定されています：

- **anon key**: 全テーブル読み取り専用
- **service_role key**: 全テーブル読み書き可能

これにより：
- フロントエンド（Vercel）: データ閲覧のみ
- バックエンド（Colab）: データ更新可能

## ローカルデータの移行

既存のローカルDBからSupabaseへデータを移行する場合：

```bash
# ローカルDBからエクスポート
pg_dump -h localhost -U postgres -d keiba_db \
  --data-only --inserts \
  -t horses -t jockeys -t trainers -t sires \
  -t races -t entries -t trainings -t predictions -t history \
  > data_export.sql

# Supabase SQL Editorで data_export.sql を実行
```

または、Colabノートブックでスクレイピングから再収集することも可能です。
