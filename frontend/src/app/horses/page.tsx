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
import { getHorses } from '@/lib/api';
import type { Horse } from '@/lib/api';
import { Search, ChevronRight } from 'lucide-react';

export default function HorsesPage() {
  const [horses, setHorses] = useState<Horse[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState('');
  const [searchInput, setSearchInput] = useState('');
  const [sexFilter, setSexFilter] = useState('');
  const limit = 50;

  useEffect(() => {
    async function fetchHorses() {
      setIsLoading(true);
      try {
        const data = await getHorses({
          search: search || undefined,
          sex: sexFilter || undefined,
          limit,
          offset,
        });
        setHorses(data.horses);
        setTotal(data.total);
      } catch (error) {
        console.error('Failed to fetch horses:', error);
      } finally {
        setIsLoading(false);
      }
    }
    fetchHorses();
  }, [offset, search, sexFilter]);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearch(searchInput);
    setOffset(0);
  };

  const hasMore = offset + limit < total;
  const hasPrev = offset > 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">競走馬管理</h1>
        <p className="text-gray-500 mt-1">登録されている競走馬の一覧</p>
      </div>

      {/* Search and Filter */}
      <Card className="mb-6">
        <CardContent className="py-4">
          <div className="flex flex-wrap gap-4">
            <form onSubmit={handleSearch} className="flex gap-2 flex-1 min-w-[200px]">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
                <input
                  type="text"
                  placeholder="馬名で検索..."
                  value={searchInput}
                  onChange={(e) => setSearchInput(e.target.value)}
                  className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <Button type="submit">検索</Button>
            </form>
            <select
              value={sexFilter}
              onChange={(e) => {
                setSexFilter(e.target.value);
                setOffset(0);
              }}
              className="px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">全ての性別</option>
              <option value="牡">牡（オス）</option>
              <option value="牝">牝（メス）</option>
              <option value="セ">セン馬</option>
            </select>
          </div>
        </CardContent>
      </Card>

      {/* Horses Table */}
      <Card>
        <CardHeader>
          <CardTitle>競走馬一覧 ({total.toLocaleString()}頭)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            </div>
          ) : horses.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              競走馬が見つかりません
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>馬名</TableHead>
                    <TableHead className="text-center">性別</TableHead>
                    <TableHead className="text-center">生年</TableHead>
                    <TableHead>父</TableHead>
                    <TableHead>母</TableHead>
                    <TableHead>調教師</TableHead>
                    <TableHead className="text-right">出走数</TableHead>
                    <TableHead className="w-16">{''}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {horses.map((horse) => (
                    <TableRow key={horse.horse_id}>
                      <TableCell className="font-medium">
                        {horse.name}
                      </TableCell>
                      <TableCell className="text-center">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${
                          horse.sex === '牡' ? 'bg-blue-100 text-blue-800' :
                          horse.sex === '牝' ? 'bg-pink-100 text-pink-800' :
                          'bg-gray-100 text-gray-800'
                        }`}>
                          {horse.sex}
                        </span>
                      </TableCell>
                      <TableCell className="text-center">
                        {horse.birth_year || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {horse.father || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {horse.mother || '-'}
                      </TableCell>
                      <TableCell className="text-gray-600">
                        {horse.trainer || '-'}
                      </TableCell>
                      <TableCell className="text-right">
                        {horse.entries_count}
                      </TableCell>
                      <TableCell>
                        <Link
                          href={`/horses/${horse.horse_id}`}
                          className="text-blue-600 hover:text-blue-800 inline-flex items-center"
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
                  {offset + 1} - {Math.min(offset + limit, total)} / {total.toLocaleString()}頭
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
