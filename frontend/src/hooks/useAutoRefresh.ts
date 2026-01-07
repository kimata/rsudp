import { useState, useEffect, useRef, useCallback } from "react";

const STORAGE_KEY = "rsudp_auto_refresh_settings";
const DEFAULT_INTERVAL_MS = 10 * 60 * 1000; // 10分

interface AutoRefreshSettings {
    enabled: boolean;
    intervalMs: number;
}

interface UseAutoRefreshOptions {
    intervalMs?: number;
    onRefresh: () => Promise<void>;
    pauseWhenHidden?: boolean;
}

interface UseAutoRefreshReturn {
    isEnabled: boolean;
    setIsEnabled: (enabled: boolean) => void;
    lastRefreshed: Date | null;
    nextRefreshIn: number; // 残り秒数
    resetTimer: () => void; // 手動更新時にタイマーをリセット
}

/**
 * 自動更新機能を提供するカスタムフック
 *
 * - 指定間隔で自動的に onRefresh を呼び出す
 * - Page Visibility API でタブ非表示時に一時停止
 * - localStorage に設定を永続化
 */
export function useAutoRefresh(options: UseAutoRefreshOptions): UseAutoRefreshReturn {
    const { intervalMs = DEFAULT_INTERVAL_MS, onRefresh, pauseWhenHidden = true } = options;

    // localStorage から設定を読み込み
    const loadSettings = (): AutoRefreshSettings => {
        try {
            const saved = localStorage.getItem(STORAGE_KEY);
            if (saved) {
                const parsed = JSON.parse(saved) as AutoRefreshSettings;
                return {
                    enabled: parsed.enabled ?? false,
                    intervalMs: parsed.intervalMs ?? intervalMs,
                };
            }
        } catch (e) {
            console.error("Failed to load auto-refresh settings:", e);
        }
        return { enabled: false, intervalMs };
    };

    const [isEnabled, setIsEnabledState] = useState(() => loadSettings().enabled);
    const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
    const [nextRefreshIn, setNextRefreshIn] = useState(Math.floor(intervalMs / 1000));
    const [isPageVisible, setIsPageVisible] = useState(!document.hidden);

    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const countdownRef = useRef<ReturnType<typeof setInterval> | null>(null);
    const isRefreshingRef = useRef(false);
    const remainingTimeRef = useRef(intervalMs);

    // 設定を localStorage に保存
    const saveSettings = useCallback(
        (enabled: boolean) => {
            try {
                const settings: AutoRefreshSettings = { enabled, intervalMs };
                localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
            } catch (e) {
                console.error("Failed to save auto-refresh settings:", e);
            }
        },
        [intervalMs]
    );

    // isEnabled を変更し、localStorage にも保存
    const setIsEnabled = useCallback(
        (enabled: boolean) => {
            setIsEnabledState(enabled);
            saveSettings(enabled);
        },
        [saveSettings]
    );

    // タイマーをリセット（手動更新時に呼び出す）
    const resetTimer = useCallback(() => {
        remainingTimeRef.current = intervalMs;
        setNextRefreshIn(Math.floor(intervalMs / 1000));
        setLastRefreshed(new Date());
    }, [intervalMs]);

    // 更新を実行
    const executeRefresh = useCallback(async () => {
        if (isRefreshingRef.current) return;

        isRefreshingRef.current = true;
        try {
            await onRefresh();
            setLastRefreshed(new Date());
            remainingTimeRef.current = intervalMs;
            setNextRefreshIn(Math.floor(intervalMs / 1000));
        } catch (e) {
            console.error("Auto-refresh failed:", e);
        } finally {
            isRefreshingRef.current = false;
        }
    }, [onRefresh, intervalMs]);

    // Page Visibility API のハンドラ
    useEffect(() => {
        if (!pauseWhenHidden) return;

        const handleVisibilityChange = () => {
            const visible = !document.hidden;
            setIsPageVisible(visible);

            // タブが再表示されたら即座に更新を実行
            if (visible && isEnabled) {
                // 長時間非表示だった場合（残り時間が0以下になっている可能性）
                if (remainingTimeRef.current <= 0) {
                    executeRefresh();
                }
            }
        };

        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => {
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [pauseWhenHidden, isEnabled, executeRefresh]);

    // メインのインターバル処理
    useEffect(() => {
        // 有効でない、またはページが非表示の場合はタイマーを停止
        if (!isEnabled || (pauseWhenHidden && !isPageVisible)) {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
            if (countdownRef.current) {
                clearInterval(countdownRef.current);
                countdownRef.current = null;
            }
            return;
        }

        // カウントダウン用のインターバル（1秒ごと）
        countdownRef.current = setInterval(() => {
            remainingTimeRef.current -= 1000;
            const seconds = Math.max(0, Math.floor(remainingTimeRef.current / 1000));
            setNextRefreshIn(seconds);

            // 残り時間が0になったら更新を実行
            if (remainingTimeRef.current <= 0) {
                executeRefresh();
            }
        }, 1000);

        return () => {
            if (intervalRef.current) {
                clearInterval(intervalRef.current);
                intervalRef.current = null;
            }
            if (countdownRef.current) {
                clearInterval(countdownRef.current);
                countdownRef.current = null;
            }
        };
    }, [isEnabled, isPageVisible, pauseWhenHidden, executeRefresh]);

    return {
        isEnabled,
        setIsEnabled,
        lastRefreshed,
        nextRefreshIn,
        resetTimer,
    };
}
