import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from '@/components/ui/Table';
import { formatOdds, getResultColor } from '@/lib/utils';
import type { Entry } from '@/types/race';

interface EntryTableProps {
  entries: Entry[];
  showResult?: boolean;
}

export function EntryTable({ entries, showResult = false }: EntryTableProps) {
  const sortedEntries = [...entries].sort((a, b) => a.horse_number - b.horse_number);

  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className="w-12">枠</TableHead>
          <TableHead className="w-12">馬番</TableHead>
          <TableHead>馬名</TableHead>
          <TableHead>騎手</TableHead>
          <TableHead className="text-right">斤量</TableHead>
          <TableHead className="text-right">オッズ</TableHead>
          <TableHead className="text-right">人気</TableHead>
          {showResult && <TableHead className="text-right">着順</TableHead>}
        </TableRow>
      </TableHeader>
      <TableBody>
        {sortedEntries.map((entry) => (
          <TableRow key={entry.horse_number}>
            <TableCell className="font-medium">{entry.frame_number || '-'}</TableCell>
            <TableCell className="font-medium">{entry.horse_number}</TableCell>
            <TableCell>
              <div>
                <div className="font-medium text-gray-900">
                  {entry.horse_name || entry.horse?.name || '-'}
                </div>
                {entry.horse && (
                  <div className="text-xs text-gray-500">
                    {entry.horse.sex} {entry.horse.father && `父: ${entry.horse.father}`}
                  </div>
                )}
              </div>
            </TableCell>
            <TableCell>
              {entry.jockey_name || entry.jockey?.name || '-'}
            </TableCell>
            <TableCell className="text-right">
              {entry.weight ? `${entry.weight}kg` : '-'}
            </TableCell>
            <TableCell className="text-right">
              {formatOdds(entry.odds)}
            </TableCell>
            <TableCell className="text-right">
              {entry.popularity ? `${entry.popularity}` : '-'}
            </TableCell>
            {showResult && (
              <TableCell className={`text-right ${getResultColor(entry.result)}`}>
                {entry.result || '-'}
              </TableCell>
            )}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
