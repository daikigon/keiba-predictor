# Next.js App Router ベストプラクティス

本プロジェクトで準拠するNext.js App Routerのベストプラクティスをまとめる。

---

## 1. ディレクトリ構造

### 推奨構造

```
frontend/
├── src/
│   ├── app/                    # App Router (ルーティングのみ)
│   │   ├── layout.tsx          # ルートレイアウト
│   │   ├── page.tsx            # トップページ (/)
│   │   ├── loading.tsx         # グローバルローディング
│   │   ├── error.tsx           # グローバルエラー
│   │   ├── not-found.tsx       # 404ページ
│   │   ├── (dashboard)/        # ルートグループ (URLに含まれない)
│   │   │   ├── page.tsx        # /
│   │   │   └── layout.tsx
│   │   ├── races/
│   │   │   ├── page.tsx        # /races
│   │   │   └── [id]/
│   │   │       └── page.tsx    # /races/[id]
│   │   ├── history/
│   │   │   └── page.tsx        # /history
│   │   ├── data/
│   │   │   └── page.tsx        # /data
│   │   └── api/                # API Routes (必要な場合のみ)
│   │       └── route.ts
│   │
│   ├── components/             # 共有コンポーネント
│   │   ├── ui/                 # 汎用UIコンポーネント
│   │   │   ├── Button.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Input.tsx
│   │   │   └── Table.tsx
│   │   ├── layout/             # レイアウトコンポーネント
│   │   │   ├── Header.tsx
│   │   │   ├── Sidebar.tsx
│   │   │   └── Footer.tsx
│   │   └── features/           # 機能別コンポーネント
│   │       ├── race/
│   │       │   ├── RaceCard.tsx
│   │       │   └── RaceList.tsx
│   │       └── prediction/
│   │           ├── PredictionResult.tsx
│   │           └── PredictionChart.tsx
│   │
│   ├── lib/                    # ユーティリティ・ヘルパー
│   │   ├── api.ts              # APIクライアント
│   │   ├── utils.ts            # 汎用ユーティリティ
│   │   └── constants.ts        # 定数
│   │
│   ├── hooks/                  # カスタムフック
│   │   ├── useRaces.ts
│   │   └── usePrediction.ts
│   │
│   ├── types/                  # TypeScript型定義
│   │   ├── race.ts
│   │   ├── horse.ts
│   │   └── prediction.ts
│   │
│   └── styles/                 # グローバルスタイル
│       └── globals.css
│
├── public/                     # 静的アセット
├── next.config.js
├── tsconfig.json
└── package.json
```

### ルール

1. **`app/` ディレクトリはルーティング専用**
   - `page.tsx`, `layout.tsx`, `loading.tsx`, `error.tsx` のみ配置
   - コンポーネントロジックは `components/` に分離

2. **ルートグループ `(groupName)` の活用**
   - URLに影響を与えずにファイルを整理
   - 例: `(dashboard)`, `(marketing)`, `(admin)`

3. **プライベートフォルダ `_folderName`**
   - ルーティングから除外したいファイル用
   - 例: `_components/`, `_lib/`

4. **深すぎるネストを避ける**
   - 最大4階層程度に抑える
   - 7階層以上のパスは設計を見直す

---

## 2. Server Components vs Client Components

### デフォルトはServer Components

App Routerでは、すべてのコンポーネントがデフォルトでServer Componentsとなる。

### Server Componentsを使う場面

| ユースケース | 理由 |
|-------------|------|
| データフェッチ | DBやAPIに直接アクセス可能 |
| 機密情報の使用 | APIキーなどをクライアントに露出しない |
| 静的コンテンツ | JSバンドルサイズ削減 |
| SEO重要ページ | サーバーレンダリングでSEO向上 |

```tsx
// Server Component (デフォルト)
// "use client" なし

async function RaceList() {
  const races = await fetch('http://api/races').then(r => r.json());
  
  return (
    <ul>
      {races.map(race => (
        <li key={race.id}>{race.name}</li>
      ))}
    </ul>
  );
}
```

### Client Componentsを使う場面

| ユースケース | 理由 |
|-------------|------|
| インタラクティブUI | onClick, onChange などのイベント |
| 状態管理 | useState, useReducer |
| ライフサイクル | useEffect |
| ブラウザAPI | localStorage, window, geolocation |

```tsx
// Client Component
"use client";

import { useState } from 'react';

function BetButton({ raceId }: { raceId: string }) {
  const [isLoading, setIsLoading] = useState(false);
  
  const handleClick = async () => {
    setIsLoading(true);
    // ...処理
  };
  
  return (
    <button onClick={handleClick} disabled={isLoading}>
      {isLoading ? '処理中...' : '予想を保存'}
    </button>
  );
}
```

### コンポジションパターン (推奨)

Server ComponentsとClient Componentsを組み合わせる。

```tsx
// app/races/[id]/page.tsx (Server Component)
import { RaceDetail } from '@/components/features/race/RaceDetail';
import { BetButton } from '@/components/features/race/BetButton';

async function RacePage({ params }: { params: { id: string } }) {
  const race = await fetchRace(params.id);  // サーバーでデータ取得
  
  return (
    <div>
      <RaceDetail race={race} />           {/* Server Component */}
      <BetButton raceId={params.id} />     {/* Client Component */}
    </div>
  );
}
```

### 判断フローチャート

```
コンポーネントを作成
    |
    v
インタラクティブ機能が必要？
(useState, useEffect, onClick等)
    |
    +---> Yes ---> "use client" を追加
    |
    +---> No ---> Server Component のまま
```

---

## 3. ファイル規約

### 特殊ファイル

| ファイル | 用途 | 必須 |
|---------|------|------|
| `page.tsx` | ルートを公開 | ○ |
| `layout.tsx` | 共有レイアウト | △ |
| `loading.tsx` | ローディングUI (Suspense) | △ |
| `error.tsx` | エラーバウンダリ | △ |
| `not-found.tsx` | 404ページ | △ |
| `route.ts` | APIエンドポイント | △ |

### コンポーネント階層

```
layout.tsx
  └── template.tsx (あれば)
        └── error.tsx (エラーバウンダリ)
              └── loading.tsx (Suspense)
                    └── not-found.tsx
                          └── page.tsx
```

---

## 4. データフェッチ

### Server Componentsでのフェッチ (推奨)

```tsx
// app/races/page.tsx
async function RacesPage() {
  const res = await fetch('http://localhost:8000/api/v1/races', {
    cache: 'no-store',  // 動的データ
    // cache: 'force-cache',  // 静的データ
  });
  const data = await res.json();
  
  return <RaceList races={data.races} />;
}
```

### キャッシュ戦略

| オプション | 用途 |
|-----------|------|
| `cache: 'force-cache'` | 静的データ (デフォルト) |
| `cache: 'no-store'` | 常に最新データ |
| `next: { revalidate: 60 }` | 60秒ごとに再検証 |

---

## 5. 本プロジェクトでの適用

### レース一覧 (Server Component)

```tsx
// app/races/page.tsx
async function RacesPage() {
  const races = await fetchRaces();  // Server側でAPI呼び出し
  return <RaceList races={races} />;
}
```

### レース詳細 + 予想ボタン (混合)

```tsx
// app/races/[id]/page.tsx
import { PredictionPanel } from '@/components/features/prediction/PredictionPanel';

async function RaceDetailPage({ params }) {
  const race = await fetchRace(params.id);  // Server
  
  return (
    <div>
      <RaceInfo race={race} />              {/* Server */}
      <EntryTable entries={race.entries} /> {/* Server */}
      <PredictionPanel raceId={params.id} /> {/* Client - インタラクティブ */}
    </div>
  );
}
```

### 予想履歴 (Client Component - フィルター機能)

```tsx
// components/features/history/HistoryFilter.tsx
"use client";

function HistoryFilter({ onFilter }) {
  const [dateRange, setDateRange] = useState({ from: '', to: '' });
  // フィルターUI...
}
```

---

## 6. 命名規則

| 対象 | 規則 | 例 |
|------|------|-----|
| コンポーネント | PascalCase | `RaceCard.tsx` |
| フック | camelCase + use接頭辞 | `useRaces.ts` |
| ユーティリティ | camelCase | `formatDate.ts` |
| 型定義 | PascalCase | `Race`, `Horse` |
| 定数 | UPPER_SNAKE_CASE | `API_BASE_URL` |

---

## 7. パフォーマンス最適化

### 1. 動的インポート

```tsx
import dynamic from 'next/dynamic';

const Chart = dynamic(() => import('@/components/Chart'), {
  loading: () => <p>Loading...</p>,
  ssr: false,  // クライアントのみ
});
```

### 2. 画像最適化

```tsx
import Image from 'next/image';

<Image
  src="/horse.jpg"
  alt="Horse"
  width={400}
  height={300}
  priority  // LCP対象の場合
/>
```

### 3. Suspenseによるストリーミング

```tsx
import { Suspense } from 'react';

function Page() {
  return (
    <div>
      <Header />
      <Suspense fallback={<RaceListSkeleton />}>
        <RaceList />
      </Suspense>
    </div>
  );
}
```

---

## 8. 避けるべきパターン

### ❌ appディレクトリにすべてを詰め込む

```
// BAD
app/
  ├── components/
  ├── utils/
  └── hooks/
```

### ❌ 深すぎるネスト

```
// BAD
src/components/features/dashboard/widgets/weather/current/small/index.tsx
```

### ❌ 巨大なユーティリティファイル

```
// BAD - 2000行のutils.ts
lib/utils.ts
```

### ❌ Client Componentの過剰使用

```tsx
// BAD - 不要な "use client"
"use client";

function StaticText() {
  return <p>Hello World</p>;  // インタラクティブ要素なし
}
```

---

## 参考資料

- [Next.js 公式: Project Structure](https://nextjs.org/docs/app/getting-started/project-structure)
- [Next.js 公式: Server and Client Components](https://nextjs.org/docs/app/getting-started/server-and-client-components)
- [Next.js 公式: App Router Guides](https://nextjs.org/docs/app/guides)
