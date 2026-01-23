'use client';

import { useState, useEffect } from 'react';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';
import { getHistory } from '@/lib/api';
import { formatDateTime, formatCurrency, formatPercent } from '@/lib/utils';
import type { History, HistorySummary } from '@/types/prediction';

export default function HistoryPage() {
  const [history, setHistory] = useState<History[]>([]);
  const [summary, setSummary] = useState<HistorySummary | null>(null);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [offset, setOffset] = useState(0);
  const limit = 20;

  useEffect(() => {
    async function fetchHistory() {
      setIsLoading(true);
      try {
        const data = await getHistory({ limit, offset });
        setHistory(data.items);
        setSummary(data.summary);
        setTotal(data.total);
      } catch (error) {
        console.error('Failed to fetch history:', error);
      } finally {
        setIsLoading(false);
      }
    }
    fetchHistory();
  }, [offset]);

  const hasMore = offset + limit < total;
  const hasPrev = offset > 0;

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900">予想履歴</h1>
        <p className="text-gray-500 mt-1">過去の予想と的中結果</p>
      </div>

      {/* Summary Cards */}
      {summary && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4 mb-8">
          <SummaryCard
            label="総予想数"
            value={summary.total_bets.toString()}
          />
          <SummaryCard
            label="的中数"
            value={`${summary.total_hits}件`}
            subValue={`的中率: ${formatPercent(summary.hit_rate)}`}
          />
          <SummaryCard
            label="総投資"
            value={formatCurrency(summary.total_bet_amount)}
          />
          <SummaryCard
            label="回収率"
            value={formatPercent(summary.roi + 100)}
            valueColor={summary.roi >= 0 ? 'text-green-600' : 'text-red-600'}
          />
        </div>
      )}

      {/* History Table */}
      <Card>
        <CardHeader>
          <CardTitle>予想履歴 ({total}件)</CardTitle>
        </CardHeader>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="text-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
            </div>
          ) : history.length === 0 ? (
            <div className="text-center py-12 text-gray-500">
              履歴がありません
            </div>
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>日時</TableHead>
                    <TableHead>馬券種</TableHead>
                    <TableHead>買い目</TableHead>
                    <TableHead className="text-right">金額</TableHead>
                    <TableHead className="text-center">結果</TableHead>
                    <TableHead className="text-right">払戻</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {history.map((item) => (
                    <TableRow key={item.id}>
                      <TableCell className="text-gray-500 text-sm">
                        {formatDateTime(item.created_at)}
                      </TableCell>
                      <TableCell className="font-medium">
                        {item.bet_type}
                      </TableCell>
                      <TableCell>{item.bet_detail}</TableCell>
                      <TableCell className="text-right">
                        {item.bet_amount ? formatCurrency(item.bet_amount) : '-'}
                      </TableCell>
                      <TableCell className="text-center">
                        {item.is_hit === null ? (
                          <Badge variant="default">未確定</Badge>
                        ) : item.is_hit ? (
                          <Badge variant="success">的中</Badge>
                        ) : (
                          <Badge variant="danger">ハズレ</Badge>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {item.payout ? (
                          <span className="text-green-600 font-medium">
                            {formatCurrency(item.payout)}
                          </span>
                        ) : (
                          '-'
                        )}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>

              {/* Pagination */}
              <div className="flex items-center justify-between px-4 py-3 border-t">
                <div className="text-sm text-gray-500">
                  {offset + 1} - {Math.min(offset + limit, total)} / {total}件
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

function SummaryCard({
  label,
  value,
  subValue,
  valueColor = 'text-gray-900',
}: {
  label: string;
  value: string;
  subValue?: string;
  valueColor?: string;
}) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-sm text-gray-500">{label}</p>
        <p className={`text-2xl font-bold ${valueColor}`}>{value}</p>
        {subValue && <p className="text-sm text-gray-500 mt-1">{subValue}</p>}
      </CardContent>
    </Card>
  );
}
