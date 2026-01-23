'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Button } from '@/components/ui/Button';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';
import { getJockeys, refreshJockeyNames } from '@/lib/api';
import type { Jockey } from '@/lib/api';
import { Search, ChevronRight, RefreshCw, Database, Cloud } from 'lucide-react';
import { API_BASE_URL } from '@/lib/constants';

export default function JockeysPage() {
  const [jockeys, setJockeys] = useState<Jockey[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshResult, setRefreshResult] = useState<{ updated: number; errors: number } | null>(null);
  const limit = 50;

  // Backend connection state
  const [isBackendAvailable, setIsBackendAvailable] = useState<boolean | null>(null);

  // Check backend health
  useEffect(() => {
    async function checkBackend() {
      if (!API_BASE_URL) {
        setIsBackendAvailable(false);
        return;
      }
      try {
        const res = await fetch(`${API_BASE_URL}/api/v1/stats/scrape`, {
          signal: AbortSignal.timeout(3000),
        });
        setIsBackendAvailable(res.ok);
      } catch {
        setIsBackendAvailable(false);
      }
    }
    checkBackend();
  }, []);

  useEffect(() => {
    async function fetchJockeys() {
      setIsLoading(true);
      try {
        const data = await getJockeys({
          search: search || undefined,
          race_type: 'banei',
          limit,
          offset,
        });
        setJockeys(data.jockeys);
        setTotal(data.total);
      } catch (error) {
        console.error('Failed to fetch jockeys:', error);
      } finally {
        setIsLoading(false);
      }
    }
    fetchJockeys();
  }, [offset, search]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setOffset(0);
  };

  const handleRefreshNames = async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    setRefreshResult(null);
    try {
      const result = await refreshJockeyNames();
      setRefreshResult({ updated: result.updated, errors: result.errors });
      // Refresh the list
      const data = await getJockeys({ search: search || undefined, limit, offset });
      setJockeys(data.jockeys);
    } catch (error) {
      console.error('Failed to refresh names:', error);
    } finally {
      setIsRefreshing(false);
    }
  };

  const hasMore = offset + limit < total;
  const hasPrev = offset > 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <div className="flex items-center gap-3">
          <h1 className="text-2xl font-bold text-gray-900">ばんえい競馬 騎手管理</h1>
          {/* DB接続状態バッジ */}
          {isBackendAvailable !== null && (
            <div className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
              isBackendAvailable
                ? 'bg-purple-100 text-purple-800'
                : 'bg-blue-100 text-blue-800'
            }`}>
              {isBackendAvailable ? (
                <>
                  <Database className="w-3 h-3" />
                  ローカルDB
                </>
              ) : (
                <>
                  <Cloud className="w-3 h-3" />
                  Supabase
                </>
              )}
            </div>
          )}
        </div>
        <p className="text-gray-500 mt-1">登録されている騎手の一覧</p>
      </div>

      {/* Search and Actions */}
      <Card className="mb-6">
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4 items-start justify-between">
            <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-[200px] max-w-md">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="騎手名で検索..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-purple-500 focus:border-purple-500"
                />
              </div>
              <Button type="submit">検索</Button>
            </form>
            <div className="flex items-center gap-4">
              {refreshResult && (
                <span className="text-sm text-gray-600">
                  {refreshResult.updated}件更新
                  {refreshResult.errors > 0 && ` (${refreshResult.errors}件エラー)`}
                </span>
              )}
              <Button
                variant="outline"
                onClick={handleRefreshNames}
                disabled={isRefreshing}
              >
                <RefreshCw className={`w-4 h-4 mr-2 ${isRefreshing ? 'animate-spin' : ''}`} />
                {isRefreshing ? '更新中...' : '名前を更新'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Jockeys Table */}
      <Card>
        <CardHeader>
          <CardTitle>騎手一覧 ({total.toLocaleString()}人)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600 mx-auto"></div>
            </div>
          ) : jockeys.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              騎手が見つかりません
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>騎手名</TableHead>
                    <TableHead className="text-right">騎乗数</TableHead>
                    <TableHead className="text-right">勝利数</TableHead>
                    <TableHead className="text-right">勝率</TableHead>
                    <TableHead className="text-right">連対率</TableHead>
                    <TableHead className="text-right">複勝率</TableHead>
                    <TableHead className="w-16">{''}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {jockeys.map((jockey) => (
                    <TableRow key={jockey.jockey_id}>
                      <TableCell className="font-medium">
                        {jockey.name}
                      </TableCell>
                      <TableCell className="text-right">
                        {jockey.entries_count}
                      </TableCell>
                      <TableCell className="text-right">
                        {jockey.wins}
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={jockey.win_rate >= 10 ? 'text-green-600 font-medium' : ''}>
                          {jockey.win_rate}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={jockey.place_rate >= 20 ? 'text-blue-600 font-medium' : ''}>
                          {jockey.place_rate}%
                        </span>
                      </TableCell>
                      <TableCell className="text-right">
                        <span className={jockey.show_rate >= 30 ? 'text-purple-600 font-medium' : ''}>
                          {jockey.show_rate}%
                        </span>
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/banei/jockeys/${jockey.jockey_id}`}
                          className="text-purple-600 hover:text-purple-800 inline-flex items-center"
                        >
                          詳細 <ChevronRight className="w-4 h-4" />
                        </Link>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <div className="text-sm text-gray-500">
                  {offset + 1} - {Math.min(offset + limit, total)} / {total.toLocaleString()}人
                </div>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasPrev}
                    onClick={() => setOffset(offset - limit)}
                  >
                    前へ
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={!hasMore}
                    onClick={() => setOffset(offset + limit)}
                  >
                    次へ
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
