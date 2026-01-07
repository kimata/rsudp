import { useState, useEffect, useRef, useCallback } from "react";

const SSE_ENDPOINT = "/rsudp/api/event";

interface UseAutoRefreshOptions {
    onRefresh: () => Promise<void>;
    pauseWhenHidden?: boolean;
}

interface UseAutoRefreshReturn {
    isConnected: boolean;
    lastRefreshed: Date | null;
    connectionError: string | null;
}

/**
 * SSE (Server-Sent Events) を使った自動更新機能を提供するカスタムフック
 *
 * - サーバーからの DATA イベントを受信したら onRefresh を呼び出す
 * - Page Visibility API でタブ非表示時に接続を一時停止
 * - 接続エラー時は自動で再接続
 */
export function useAutoRefresh(options: UseAutoRefreshOptions): UseAutoRefreshReturn {
    const { onRefresh, pauseWhenHidden = true } = options;

    const [isConnected, setIsConnected] = useState(false);
    const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
    const [connectionError, setConnectionError] = useState<string | null>(null);
    const [isPageVisible, setIsPageVisible] = useState(!document.hidden);

    const eventSourceRef = useRef<EventSource | null>(null);
    const isRefreshingRef = useRef(false);
    const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    // 更新を実行
    const executeRefresh = useCallback(async () => {
        if (isRefreshingRef.current) return;

        isRefreshingRef.current = true;
        try {
            await onRefresh();
            setLastRefreshed(new Date());
        } catch (e) {
            console.error("Auto-refresh failed:", e);
        } finally {
            isRefreshingRef.current = false;
        }
    }, [onRefresh]);

    // SSE 接続を開始
    const connect = useCallback(() => {
        // 既に接続中の場合はスキップ
        if (eventSourceRef.current) {
            return;
        }

        console.log("SSE: Connecting to", SSE_ENDPOINT);
        const eventSource = new EventSource(SSE_ENDPOINT);
        eventSourceRef.current = eventSource;

        eventSource.onopen = () => {
            console.log("SSE: Connected");
            setIsConnected(true);
            setConnectionError(null);
        };

        eventSource.onmessage = (event) => {
            const eventType = event.data;
            console.log("SSE: Received event:", eventType);

            // DATA イベントを受信したら更新を実行
            if (eventType === "data") {
                executeRefresh();
            }
            // dummy イベントは無視（キープアライブ用）
        };

        eventSource.onerror = () => {
            console.error("SSE: Connection error");
            setIsConnected(false);
            setConnectionError("サーバーとの接続が切断されました");

            // 接続を閉じてリセット
            eventSource.close();
            eventSourceRef.current = null;

            // 5秒後に再接続を試みる
            if (reconnectTimeoutRef.current) {
                clearTimeout(reconnectTimeoutRef.current);
            }
            reconnectTimeoutRef.current = setTimeout(() => {
                if (!document.hidden) {
                    connect();
                }
            }, 5000);
        };
    }, [executeRefresh]);

    // SSE 接続を切断
    const disconnect = useCallback(() => {
        if (eventSourceRef.current) {
            console.log("SSE: Disconnecting");
            eventSourceRef.current.close();
            eventSourceRef.current = null;
            setIsConnected(false);
        }
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current);
            reconnectTimeoutRef.current = null;
        }
    }, []);

    // Page Visibility API のハンドラ
    useEffect(() => {
        if (!pauseWhenHidden) return;

        const handleVisibilityChange = () => {
            const visible = !document.hidden;
            setIsPageVisible(visible);

            if (visible) {
                // タブが再表示されたら接続を再開し、即座に更新
                connect();
                executeRefresh();
            } else {
                // タブが非表示になったら接続を切断
                disconnect();
            }
        };

        document.addEventListener("visibilitychange", handleVisibilityChange);
        return () => {
            document.removeEventListener("visibilitychange", handleVisibilityChange);
        };
    }, [pauseWhenHidden, connect, disconnect, executeRefresh]);

    // コンポーネントマウント時に接続開始
    useEffect(() => {
        // ページが表示されている場合のみ接続
        if (!pauseWhenHidden || isPageVisible) {
            connect();
        }

        return () => {
            disconnect();
        };
    }, [connect, disconnect, pauseWhenHidden, isPageVisible]);

    return {
        isConnected,
        lastRefreshed,
        connectionError,
    };
}
