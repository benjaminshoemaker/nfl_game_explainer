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
  secondsSinceUpdate: number;
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
  const [secondsSinceUpdate, setSecondsSinceUpdate] = useState(0);
  const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(0);

  // Use refs for callbacks to avoid dependency issues
  const fetchFnRef = useRef(fetchFn);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);

  // Update refs when callbacks change
  useEffect(() => {
    fetchFnRef.current = fetchFn;
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
  }, [fetchFn, onSuccess, onError]);

  const refresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      const result = await fetchFnRef.current();
      setData(result);
      setSecondsSinceUpdate(0);
      setSecondsUntilRefresh(Math.floor(interval / 1000));
      onSuccessRef.current?.(result);
    } catch (error) {
      onErrorRef.current?.(error instanceof Error ? error : new Error('Refresh failed'));
    } finally {
      setIsRefreshing(false);
    }
  }, [interval]);

  // Set up polling and countdown
  useEffect(() => {
    if (!enabled) {
      setSecondsUntilRefresh(0);
      return;
    }

    // Initial fetch after a short delay to prevent flash
    const initialTimeout = setTimeout(() => {
      refresh();
    }, 100);

    // Set up refresh interval
    const refreshInterval = setInterval(refresh, interval);

    // Set up countdown timer (updates both counters every second)
    const countdownInterval = setInterval(() => {
      setSecondsUntilRefresh((prev) => Math.max(0, prev - 1));
      setSecondsSinceUpdate((prev) => prev + 1);
    }, 1000);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(refreshInterval);
      clearInterval(countdownInterval);
    };
  }, [enabled, interval, refresh]);

  return {
    data,
    isRefreshing,
    secondsSinceUpdate,
    secondsUntilRefresh,
    refresh,
  };
}
