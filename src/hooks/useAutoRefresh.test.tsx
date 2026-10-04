import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook } from '@testing-library/react';
import { useAutoRefresh } from './useAutoRefresh';

afterEach(() => vi.useRealTimers());

describe('useAutoRefresh', () => {
  it('reports an outage, retains the last value, then clears the error on recovery', async () => {
    vi.useFakeTimers();
    const fetchFn = vi.fn()
      .mockResolvedValueOnce('first report')
      .mockRejectedValueOnce(new Error('offline'))
      .mockResolvedValueOnce('recovered report');
    const { result } = renderHook(() => useAutoRefresh({ fetchFn, interval: 60000, enabled: true }));

    expect(result.current.hasSuccessfulRefresh).toBe(false);
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    expect(result.current.data).toBe('first report');
    expect(result.current.hasSuccessfulRefresh).toBe(true);
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(result.current.data).toBe('first report');
    expect(result.current.error?.message).toBe('offline');
    expect(result.current.secondsSinceUpdate).toBe(59);
    await act(async () => { await result.current.refresh(); });
    expect(result.current.data).toBe('recovered report');
    expect(result.current.error).toBeNull();
    expect(result.current.secondsSinceUpdate).toBe(0);
  });

  it('does not overlap slow polls', async () => {
    vi.useFakeTimers();
    let resolveFetch: (value: string) => void = () => {};
    const fetchFn = vi.fn(() => new Promise<string>(resolve => { resolveFetch = resolve; }));
    const { result } = renderHook(() => useAutoRefresh({ fetchFn, interval: 60000, enabled: true }));
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    await act(async () => { await vi.advanceTimersByTimeAsync(60000); });
    expect(fetchFn).toHaveBeenCalledTimes(1);
    await act(async () => { resolveFetch('done'); });
    await act(async () => { const next = result.current.refresh(); resolveFetch('again'); await next; });
    expect(fetchFn).toHaveBeenCalledTimes(2);
  });

  it('ignores a slow response from the previous game after navigation', async () => {
    vi.useFakeTimers();
    let resolveOld: (value: string) => void = () => {};
    const fetchFn = vi.fn()
      .mockImplementationOnce(() => new Promise<string>(resolve => { resolveOld = resolve; }))
      .mockResolvedValueOnce('new game');
    const { result, rerender } = renderHook(({ key }) => useAutoRefresh({ fetchFn, interval: 60000, enabled: true, resetKey: key }), {
      initialProps: { key: 'old' },
    });
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    rerender({ key: 'new' });
    await act(async () => { await vi.advanceTimersByTimeAsync(100); });
    expect(result.current.data).toBe('new game');
    await act(async () => { resolveOld('old game'); });
    expect(result.current.data).toBe('new game');
    expect(result.current.hasSuccessfulRefresh).toBe(true);
  });
});
