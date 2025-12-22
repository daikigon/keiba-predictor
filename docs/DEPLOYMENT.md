# デプロイメントガイド

このドキュメントでは、Vercel + Supabase + Google Colabを使用した本番環境のデプロイ方法を説明します。

## アーキテクチャ

```
Google Colab (スクレイピング + 予測)
         ↓
   Supabase (PostgreSQL)
         ↓
   Vercel (Next.js フロントエンド)
         ↓
   モバイル/PC ブラウザ
```

## 1. Supabase セットアップ

### 1.1 プロジェクト作成

1. [Supabase](https://supabase.com) でアカウント作成
2. 「New Project」をクリック
3. プロジェクト名を入力（例: `keiba-app`）
4. リージョン: `Northeast Asia (Tokyo)` を選択
5. データベースパスワードを設定

### 1.2 スキーマ適用

1. Supabaseダッシュボード → 「SQL Editor」
2. `supabase/migrations/001_initial_schema.sql` の内容をコピー＆ペースト
3. 「Run」で実行

### 1.3 API キー取得

Settings → API から以下を控える:

- **Project URL**: `https://xxxxx.supabase.co`
- **anon key**: フロントエンド用（読み取り専用）
- **service_role key**: Colab用（書き込み可能）

## 2. Vercel デプロイ

### 2.1 リポジトリ接続

1. [Vercel](https://vercel.com) でアカウント作成
2. 「New Project」をクリック
3. GitHubリポジトリを接続

### 2.2 プロジェクト設定

- **Framework Preset**: Next.js
- **Root Directory**: `frontend`
- **Build Command**: `npm run build`
- **Output Directory**: `.next`

### 2.3 環境変数設定

Environment Variables に以下を追加:

```
NEXT_PUBLIC_SUPABASE_URL=https://xxxxx.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs...
```

**重要**: `NEXT_PUBLIC_API_URL` は設定しない（空のまま）

### 2.4 デプロイ

「Deploy」をクリックしてデプロイを実行

## 3. Google Colab セットアップ

### 3.1 ノートブックをアップロード

1. `notebooks/keiba_scraper.ipynb` をGoogle Driveにアップロード
2. Google Colabで開く
3. 「ドライブにコピー」で自分のドライブにコピー

### 3.2 シークレット設定

1. Colab左サイドバー → 🔑 アイコン（Secrets）
2. 以下を追加:
   - `SUPABASE_URL`: `https://xxxxx.supabase.co`
   - `SUPABASE_SERVICE_KEY`: service_role key

### 3.3 スクレイピング実行

ノートブックのセルを順番に実行:

1. 環境セットアップ
2. 対象日設定
3. レース一覧取得
4. 詳細取得＆保存

## 4. 運用

### 毎日のスクレイピング

1. Google Colabでノートブックを開く
2. セル4まで実行してレースデータを取得

### スケジュール実行（オプション）

Colabのスケジュール機能を使用:

1. 「編集」→「ノートブックの設定」
2. スケジュールを設定

### モデル更新

1. ローカル環境でモデルを学習
2. モデルファイルをGoogle Driveにアップロード
3. Colabで予測を実行

## トラブルシューティング

### Vercelでエラーが発生する

1. 環境変数が正しく設定されているか確認
2. ビルドログを確認

### Supabaseに接続できない

1. API URLとキーが正しいか確認
2. RLSポリシーが設定されているか確認

### Colabでスクレイピングが失敗する

1. ネットワーク接続を確認
2. レート制限に注意（1.5秒間隔）
3. service_role keyが正しいか確認

## ローカル開発

ローカルで開発する場合は従来通りFastAPIバックエンドを使用:

```bash
# バックエンド
cd backend
uvicorn app.main:app --reload

# フロントエンド
cd frontend
npm run dev
```

環境変数（.env.local）:
```
NEXT_PUBLIC_API_URL=http://localhost:8000
```
