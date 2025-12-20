'use client';

import useSWR from 'swr';
import { getPrediction, getHistory, getAccuracyStats, getScrapeStats } from '@/lib/api';
import type { Prediction, HistoryListResponse, AccuracyStats, ScrapeStats } from '@/types/prediction';

export function usePrediction(raceId: string) {
  const { data, error, isLoading, mutate } = useSWR<Prediction | null>(
    ['prediction', raceId],
    () => getPrediction(raceId),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    prediction: data,
    isLoading,
    isError: !!error,
    mutate,
  };
}

export function useHistory(params?: {
  from_date?: string;
  to_date?: string;
  limit?: number;
  offset?: number;
}) {
  const key = ['history', JSON.stringify(params)];
  const { data, error, isLoading, mutate } = useSWR<HistoryListResponse>(
    key,
    () => getHistory(params),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    history: data?.items ?? [],
    summary: data?.summary,
    total: data?.total ?? 0,
    isLoading,
    isError: !!error,
    mutate,
  };
}

export function useAccuracyStats(period?: string) {
  const { data, error, isLoading } = useSWR<AccuracyStats>(
    ['accuracy', period],
    () => getAccuracyStats(period),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    stats: data,
    isLoading,
    isError: !!error,
  };
}

export function useScrapeStats() {
  const { data, error, isLoading } = useSWR<ScrapeStats>(
    'scrapeStats',
    getScrapeStats,
    {
      revalidateOnFocus: false,
    }
  );

  return {
    stats: data,
    isLoading,
    isError: !!error,
  };
}
