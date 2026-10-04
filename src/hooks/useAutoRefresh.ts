'use client';

import { useState, useEffect, useCallback, useRef } from 'react';

interface UseAutoRefreshOptions<T> {
  fetchFn: () => Promise<T>;
  interval: number; // milliseconds
  enabled: boolean;
  resetKey?: string;
  onSuccess?: (data: T) => void;
  onError?: (error: Error) => void;
}

interface UseAutoRefreshResult<T> {
  data: T | null;
  isRefreshing: boolean;
  error: Error | null;
  secondsSinceUpdate: number;
  secondsUntilRefresh: number;
  hasSuccessfulRefresh: boolean;
  refresh: () => Promise<void>;
}

export function useAutoRefresh<T>({
  fetchFn,
  interval,
  enabled,
  resetKey,
  onSuccess,
  onError,
}: UseAutoRefreshOptions<T>): UseAutoRefreshResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<Error | null>(null);
  const [lastSuccessfulAt, setLastSuccessfulAt] = useState<number | null>(null);
  const [now, setNow] = useState(() => Date.now());
  const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(0);

  // Use refs for callbacks to avoid dependency issues
  const fetchFnRef = useRef(fetchFn);
  const onSuccessRef = useRef(onSuccess);
  const onErrorRef = useRef(onError);
  const inFlightRef = useRef(false);
  const generationRef = useRef(0);

  // Update refs when callbacks change
  useEffect(() => {
    fetchFnRef.current = fetchFn;
    onSuccessRef.current = onSuccess;
    onErrorRef.current = onError;
  }, [fetchFn, onSuccess, onError]);

  useEffect(() => {
    generationRef.current += 1;
    inFlightRef.current = false;
    setData(null);
    setError(null);
    setIsRefreshing(false);
    setLastSuccessfulAt(null);
    setNow(Date.now());
    setSecondsUntilRefresh(0);
  }, [resetKey]);

  const refresh = useCallback(async () => {
    if (inFlightRef.current) return;
    const generation = generationRef.current;
    inFlightRef.current = true;
    setIsRefreshing(true);
    try {
      const result = await fetchFnRef.current();
      if (generation !== generationRef.current) return;
      setData(result);
      setError(null);
      const completedAt = Date.now();
      setLastSuccessfulAt(completedAt);
      setNow(completedAt);
      setSecondsUntilRefresh(Math.floor(interval / 1000));
      onSuccessRef.current?.(result);
    } catch (error) {
      if (generation !== generationRef.current) return;
      const refreshError = error instanceof Error ? error : new Error('Refresh failed');
      setError(refreshError);
      setNow(Date.now());
      onErrorRef.current?.(refreshError);
    } finally {
      if (generation === generationRef.current) {
        inFlightRef.current = false;
        setIsRefreshing(false);
      }
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
      setNow(Date.now());
    }, 1000);

    return () => {
      clearTimeout(initialTimeout);
      clearInterval(refreshInterval);
      clearInterval(countdownInterval);
    };
  }, [enabled, interval, refresh, resetKey]);

  return {
    data,
    isRefreshing,
    error,
    secondsSinceUpdate: lastSuccessfulAt === null ? 0 : Math.max(0, Math.floor((now - lastSuccessfulAt) / 1000)),
    secondsUntilRefresh,
    hasSuccessfulRefresh: lastSuccessfulAt !== null,
    refresh,
  };
}
