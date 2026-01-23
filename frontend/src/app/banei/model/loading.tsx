import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Cpu, RefreshCw, Clock, BarChart2, TrendingUp } from 'lucide-react';

export default function ModelLoading() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">モデル管理</h1>
        <p className="text-gray-500 mt-1">機械学習モデルの管理とシミュレーション</p>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Skeleton cards */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Cpu className="w-5 h-5 text-blue-600" />
              <CardTitle>現在のモデル</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-3/4"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
              <div className="h-4 bg-gray-200 rounded w-2/3"></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <RefreshCw className="w-5 h-5 text-green-600" />
              <CardTitle>再学習</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 animate-pulse">
              <div className="h-4 bg-gray-200 rounded w-full"></div>
              <div className="h-10 bg-gray-200 rounded w-full"></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="w-5 h-5 text-purple-600" />
              <CardTitle>モデルバージョン</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-3 animate-pulse">
              <div className="h-16 bg-gray-200 rounded"></div>
              <div className="h-16 bg-gray-200 rounded"></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <BarChart2 className="w-5 h-5 text-orange-600" />
              <CardTitle>特徴量重要度</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 animate-pulse">
              {[...Array(5)].map((_, i) => (
                <div key={i} className="space-y-1">
                  <div className="h-3 bg-gray-200 rounded w-3/4"></div>
                  <div className="h-1.5 bg-gray-200 rounded"></div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="mt-6">
        <CardHeader>
          <div className="flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-indigo-600" />
            <CardTitle>期待値シミュレーション</CardTitle>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid gap-6 lg:grid-cols-2 animate-pulse">
            <div className="space-y-4">
              <div className="h-4 bg-gray-200 rounded w-1/3"></div>
              <div className="grid grid-cols-2 gap-4">
                {[...Array(4)].map((_, i) => (
                  <div key={i} className="h-16 bg-gray-200 rounded"></div>
                ))}
              </div>
              <div className="h-10 bg-gray-200 rounded"></div>
            </div>
            <div className="h-64 bg-gray-200 rounded"></div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
