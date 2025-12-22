import { clsx, type ClassValue } from 'clsx';

export function cn(...inputs: ClassValue[]) {
  return clsx(inputs);
}

export function formatDate(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleDateString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  });
}

export function formatDateTime(dateString: string): string {
  const date = new Date(dateString);
  return date.toLocaleString('ja-JP', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('ja-JP', {
    style: 'currency',
    currency: 'JPY',
  }).format(amount);
}

export function formatPercent(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatOdds(odds: number | undefined): string {
  if (odds === undefined || odds === null) return '-';
  return odds.toFixed(1);
}

export function getResultColor(result: number | undefined): string {
  if (!result) return 'text-gray-400';
  if (result === 1) return 'text-yellow-600 font-bold';
  if (result === 2) return 'text-gray-600 font-semibold';
  if (result === 3) return 'text-orange-600 font-semibold';
  return 'text-gray-500';
}

export function getPopularityLabel(popularity: number | undefined): string {
  if (!popularity) return '-';
  return `${popularity}番人気`;
}
