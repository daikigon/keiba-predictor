'use client';

import useSWR from 'swr';
import { getRaces, getRaceDetail } from '@/lib/api';
import type { RaceListResponse, RaceDetailResponse } from '@/types/race';

export function useRaces(date?: string) {
  const { data, error, isLoading, mutate } = useSWR<RaceListResponse>(
    ['races', date],
    () => getRaces(date),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    races: data?.races ?? [],
    total: data?.total ?? 0,
    isLoading,
    isError: !!error,
    mutate,
  };
}

export function useRaceDetail(raceId: string) {
  const { data, error, isLoading, mutate } = useSWR<RaceDetailResponse>(
    ['race', raceId],
    () => getRaceDetail(raceId),
    {
      revalidateOnFocus: false,
    }
  );

  return {
    race: data,
    isLoading,
    isError: !!error,
    mutate,
  };
}
