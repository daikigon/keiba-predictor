'use client';

import { useEffect } from 'react';
import { Button } from '@/components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { AlertTriangle } from 'lucide-react';

export default function ModelError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error('Model page error:', error);
  }, [error]);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">モデル管理</h1>
        <p className="text-gray-500 mt-1">機械学習モデルの管理とシミュレーション</p>
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-center gap-2 text-red-600">
            <AlertTriangle className="w-5 h-5" />
            <CardTitle>エラーが発生しました</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <p className="text-gray-600">
              モデル管理ページの読み込み中にエラーが発生しました。
            </p>
            <div className="p-3 bg-red-50 rounded-lg text-sm text-red-700 font-mono">
              {error.message || 'Unknown error'}
            </div>
            <p className="text-sm text-gray-500">
              バックエンドサーバーが起動していることを確認してください。
            </p>
            <div className="flex gap-3">
              <Button onClick={() => reset()}>再試行</Button>
              <Button variant="outline" onClick={() => window.location.reload()}>
                ページを再読み込み
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
