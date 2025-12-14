'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

interface UseAutoRefreshOptions<T> {
  fetchFn: () => Promise<T>;
  interval: number; // milliseconds
  enabled: boolean;
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
}

interface UseAutoRefreshResult<T> {
  data: T | null;
  isRefreshing: boolean;
  lastUpdated: Date | null;
  secondsUntilRefresh: number;
  refresh: () => Promise<void>;
}

export function useAutoRefresh<T>({
  fetchFn,
  interval,
  enabled,
  onSuccess,
  onError,
}: UseAutoRefreshOptions<T>): UseAutoRefreshResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(0);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const result = await fetchFn();
      setData(result);
      setLastUpdated(new Date());
      setSecondsUntilRefresh(Math.floor(interval / 1000));
      onSuccess?.(result);
    } catch (error) {
      onError?.(error instanceof Error ? error : new Error('Refresh failed'));
    } finally {
      setIsRefreshing(false);
    }
  }, [fetchFn, interval, onSuccess, onError]);

  // Set up polling interval
  useEffect(() => {
    if (!enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
        countdownRef.current = null;
      }
      setSecondsUntilRefresh(0);
      return;
    }

    // Initial fetch
    refresh();

    // Set up refresh interval
    intervalRef.current = setInterval(refresh, interval);

    // Set up countdown
    countdownRef.current = setInterval(() => {
      setSecondsUntilRefresh((prev) => Math.max(0, prev - 1));
    }, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
      if (countdownRef.current) {
        clearInterval(countdownRef.current);
      }
    };
  }, [enabled, interval, refresh]);

  return {
    data,
    isRefreshing,
    lastUpdated,
    secondsUntilRefresh,
    refresh,
  };
}
