import React, { useState, useEffect, useCallback, useMemo, useRef } from "react";
import type { Screenshot, StatisticsResponse } from "./types";
import { screenshotApi } from "./api";
import DateSelector from "./components/DateSelector";
import ImageViewer from "./components/ImageViewer";
import FileList from "./components/FileList";
import Footer from "./components/Footer";
import SignalFilter from "./components/SignalFilter";
import { useAutoRefresh } from "./hooks/useAutoRefresh";
import { Icon } from "./components/Icon";

// URLパラメータの型定義
interface UrlParams {
    file: string | null;
    earthquake: boolean | null;
    signal: number | null;
}

// URLからパラメータを取得
const getUrlParams = (): UrlParams => {
    const params = new URLSearchParams(window.location.search);
    const file = params.get("file");
    const earthquakeStr = params.get("earthquake");
    const signalStr = params.get("signal");

    return {
        file,
        earthquake: earthquakeStr !== null ? earthquakeStr === "true" : null,
        signal: signalStr !== null ? parseInt(signalStr, 10) : null,
    };
};

// URL更新用のフラグ
interface UrlUpdateFlags {
    includeFile: boolean;
    includeEarthquake: boolean;
    includeSignal: boolean;
}

// URLを更新（履歴に追加）- フラグに応じてパラメータを含める
const updateUrl = (
    params: { file?: string | null; earthquake?: boolean; signal?: number },
    flags: UrlUpdateFlags,
    replace = false
) => {
    const url = new URL(window.location.href);

    if (flags.includeFile && params.file) {
        url.searchParams.set("file", params.file);
    } else {
        url.searchParams.delete("file");
    }

    if (flags.includeEarthquake && params.earthquake !== undefined) {
        url.searchParams.set("earthquake", params.earthquake.toString());
    } else {
        url.searchParams.delete("earthquake");
    }

    if (flags.includeSignal && params.signal !== undefined) {
        url.searchParams.set("signal", params.signal.toString());
    } else {
        url.searchParams.delete("signal");
    }

    if (replace) {
        window.history.replaceState({}, "", url.toString());
    } else {
        window.history.pushState({}, "", url.toString());
    }
};

const App: React.FC = () => {
    const [selectedYear, setSelectedYear] = useState<number | null>(null);
    const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
    const [selectedDay, setSelectedDay] = useState<number | null>(null);

    // allScreenshots: 地震フィルタ適用後の全データ（振幅フィルタ前）
    const [allScreenshots, setAllScreenshots] = useState<Screenshot[]>([]);
    const [currentScreenshot, setCurrentScreenshot] = useState<Screenshot | null>(null);

    // URL連携用
    const initialUrlParams = useRef<UrlParams>(getUrlParams());
    const hasProcessedInitialUrl = useRef(false); // 初回URL処理済みフラグ
    const isHandlingPopstate = useRef(false);
    const wasInitialLoad = useRef(true); // 前回のisInitialLoad値を追跡

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // URLパラメータから初期値を取得（signal は後で統計情報と照合）
    const [minMaxSignalThreshold, setMinMaxSignalThreshold] = useState<number | undefined>(
        initialUrlParams.current.signal !== null ? initialUrlParams.current.signal : undefined,
    );
    const [statistics, setStatistics] = useState<StatisticsResponse | null>(null);
    const [isInitialLoad, setIsInitialLoad] = useState(true);
    // URLパラメータから地震フィルタの初期値を取得（未指定ならtrue）
    const [earthquakeOnly, setEarthquakeOnly] = useState(
        initialUrlParams.current.earthquake !== null ? initialUrlParams.current.earthquake : true,
    );
    const [shouldScrollToCurrentImage, setShouldScrollToCurrentImage] = useState(false);
    const [isFiltering, setIsFiltering] = useState(false); // フィルタ適用中フラグ
    const [isRefreshing, setIsRefreshing] = useState(false); // 更新ボタン押下中フラグ
    const [notification, setNotification] = useState<{
        message: string;
        type: "success" | "info";
    } | null>(null); // 通知メッセージ

    // ユーザーが明示的に操作したかを追跡するフラグ
    // URLにはユーザーが明示的に変更したパラメータのみ含める
    const userSelectedFile = useRef(initialUrlParams.current.file !== null);
    const userChangedEarthquake = useRef(initialUrlParams.current.earthquake !== null);
    const userChangedSignal = useRef(initialUrlParams.current.signal !== null);

    // クライアント側で振幅フィルタを適用（APIリクエスト不要）
    // max_count が null の場合はフィルタを通過させる（メタデータ未取得のため）
    const signalFilteredScreenshots = useMemo(() => {
        if (minMaxSignalThreshold === undefined) {
            return allScreenshots;
        }
        return allScreenshots.filter((s) => s.max_count === null || s.max_count >= minMaxSignalThreshold);
    }, [allScreenshots, minMaxSignalThreshold]);

    // クライアント側で年リストを計算
    const years = useMemo(() => {
        const yearSet = new Set(signalFilteredScreenshots.map((s) => s.year));
        return Array.from(yearSet).sort((a, b) => b - a);
    }, [signalFilteredScreenshots]);

    // クライアント側で月リストを計算
    const months = useMemo(() => {
        if (!selectedYear) return [];
        const monthSet = new Set(
            signalFilteredScreenshots.filter((s) => s.year === selectedYear).map((s) => s.month),
        );
        return Array.from(monthSet).sort((a, b) => b - a);
    }, [signalFilteredScreenshots, selectedYear]);

    // クライアント側で日リストを計算
    const days = useMemo(() => {
        if (!selectedYear || !selectedMonth) return [];
        const daySet = new Set(
            signalFilteredScreenshots
                .filter((s) => s.year === selectedYear && s.month === selectedMonth)
                .map((s) => s.day),
        );
        return Array.from(daySet).sort((a, b) => b - a);
    }, [signalFilteredScreenshots, selectedYear, selectedMonth]);

    // 日付フィルタ適用後のスクリーンショット
    const filteredScreenshots = useMemo(() => {
        let filtered = signalFilteredScreenshots;
        if (selectedYear) {
            filtered = filtered.filter((s) => s.year === selectedYear);
        }
        if (selectedMonth) {
            filtered = filtered.filter((s) => s.month === selectedMonth);
        }
        if (selectedDay) {
            filtered = filtered.filter((s) => s.day === selectedDay);
        }
        return filtered;
    }, [signalFilteredScreenshots, selectedYear, selectedMonth, selectedDay]);

    // データ読み込み関数（useCallbackでメモ化）
    const loadInitialData = useCallback(async () => {
        setLoading(true);
        setError(null);
        try {
            console.log("Loading initial data from API...");
            // Load statistics and screenshots in parallel
            const [stats, screenshotsData] = await Promise.all([
                screenshotApi.getStatistics(earthquakeOnly),
                screenshotApi.getAllScreenshots(undefined, earthquakeOnly),
            ]);

            setStatistics(stats);
            setAllScreenshots(screenshotsData);

            // Set initial minimum maximum signal threshold to the actual minimum value
            // URLパラメータで指定されていなければ、統計情報の最小値を使用
            const initialMinMaxSignal =
                stats.min_signal !== undefined ? Math.floor(stats.min_signal) : undefined;
            if (initialUrlParams.current.signal === null && initialMinMaxSignal !== undefined) {
                setMinMaxSignalThreshold(initialMinMaxSignal);
            }

            console.log("API Response - Screenshots:", screenshotsData.length);

            // URLにファイル名が指定されている場合はそれを選択、なければ最新を選択
            if (screenshotsData.length > 0) {
                // 初回URL処理済みの場合はスキップ（StrictModeの2回目の呼び出し対策）
                if (hasProcessedInitialUrl.current) {
                    // 既に処理済みなので何もしない
                    setIsInitialLoad(false);
                    return;
                }

                const urlFilename = initialUrlParams.current.file;
                // URLからのシグナル閾値を優先、なければ統計情報の最小値を使用
                const signalThreshold =
                    initialUrlParams.current.signal !== null
                        ? initialUrlParams.current.signal
                        : initialMinMaxSignal;

                if (urlFilename) {
                    const targetScreenshot = screenshotsData.find((s) => s.filename === urlFilename);
                    if (targetScreenshot) {
                        setCurrentScreenshot(targetScreenshot);
                        // URLで指定されたファイルがシグナル閾値より低い場合、閾値を調整
                        let adjustedSignalThreshold = signalThreshold;
                        if (signalThreshold !== undefined && targetScreenshot.max_count < signalThreshold) {
                            adjustedSignalThreshold = Math.floor(targetScreenshot.max_count);
                            setMinMaxSignalThreshold(adjustedSignalThreshold);
                            // シグナル閾値を調整した場合、ユーザーが変更したとみなす
                            userChangedSignal.current = true;
                        }
                        // URLが正しい場合は履歴を置き換え（初回のみ）
                        // URLで指定されていたパラメータのみを維持
                        updateUrl(
                            {
                                file: urlFilename,
                                earthquake: earthquakeOnly,
                                signal: adjustedSignalThreshold,
                            },
                            {
                                includeFile: userSelectedFile.current,
                                includeEarthquake: userChangedEarthquake.current,
                                includeSignal: userChangedSignal.current,
                            },
                            true,
                        );
                    } else {
                        // URLのファイルが見つからない場合は最新を表示
                        setCurrentScreenshot(screenshotsData[0]);
                        // ファイルが見つからなかった場合、file パラメータは含めない
                        userSelectedFile.current = false;
                        updateUrl(
                            {
                                file: screenshotsData[0].filename,
                                earthquake: earthquakeOnly,
                                signal: signalThreshold,
                            },
                            {
                                includeFile: false,
                                includeEarthquake: userChangedEarthquake.current,
                                includeSignal: userChangedSignal.current,
                            },
                            true,
                        );
                    }
                } else {
                    setCurrentScreenshot(screenshotsData[0]);
                    // 初回読み込み時はURLパラメータを設定しない（ユーザーが明示的に操作していないため）
                    updateUrl(
                        {
                            file: screenshotsData[0].filename,
                            earthquake: earthquakeOnly,
                            signal: signalThreshold,
                        },
                        {
                            includeFile: false,
                            includeEarthquake: userChangedEarthquake.current,
                            includeSignal: userChangedSignal.current,
                        },
                        true,
                    );
                }

                // 初回URL処理完了をマーク
                hasProcessedInitialUrl.current = true;
            }

            setIsInitialLoad(false);
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Unknown error";
            setError(`Failed to load screenshots: ${errorMessage}`);
            console.error("API Error:", err);
        } finally {
            setLoading(false);
        }
    }, [earthquakeOnly]);

    // 地震フィルタ変更時に呼ばれる（振幅フィルタ変更時はAPIを呼ばない）
    const loadDataWithFilter = useCallback(async () => {
        setIsFiltering(true);
        setLoading(true);
        setError(null);
        try {
            // Load statistics and screenshots in parallel
            const [stats, screenshotsData] = await Promise.all([
                screenshotApi.getStatistics(earthquakeOnly),
                screenshotApi.getAllScreenshots(undefined, earthquakeOnly),
            ]);

            setStatistics(stats);
            setAllScreenshots(screenshotsData);

            // Update threshold to be within new range if needed
            if (stats.min_signal !== undefined) {
                const newMin = Math.floor(stats.min_signal);
                setMinMaxSignalThreshold((prev) => (prev === undefined || prev < newMin ? newMin : prev));
            }

            // Set the latest screenshot as current (フィルタ変更時はスクロールしない)
            if (screenshotsData.length > 0) {
                setCurrentScreenshot(screenshotsData[0]);
            } else {
                setCurrentScreenshot(null);
            }
        } catch (err) {
            const errorMessage = err instanceof Error ? err.message : "Unknown error";
            setError(`Failed to load screenshots: ${errorMessage}`);
            console.error("API Error:", err);
        } finally {
            setLoading(false);
            setIsFiltering(false);
        }
    }, [earthquakeOnly]);

    // Load data on mount
    useEffect(() => {
        loadInitialData();

        // バックグラウンドでサーバー側のスキャンも実行（結果は待たない）
        screenshotApi.scanScreenshots().catch((err) => {
            console.error("Background scan error:", err);
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    // 地震フィルタ変更時はAPIからデータ再取得（初回ロード後のみ）
    // isInitialLoadがfalseになった瞬間ではなく、既にfalseだった時のみ実行
    useEffect(() => {
        if (!isInitialLoad) {
            // 前回既にisInitialLoad=falseだった場合のみ実行
            // （＝earthquakeOnlyの変更による発火）
            if (!wasInitialLoad.current) {
                loadDataWithFilter();
            }
        }
        wasInitialLoad.current = isInitialLoad;
    }, [earthquakeOnly, loadDataWithFilter, isInitialLoad]);

    // フィルタ変更時にURLを更新（popstate処理中は除く）
    useEffect(() => {
        if (!isInitialLoad && !isHandlingPopstate.current && currentScreenshot) {
            updateUrl(
                {
                    file: currentScreenshot.filename,
                    earthquake: earthquakeOnly,
                    signal: minMaxSignalThreshold,
                },
                {
                    includeFile: userSelectedFile.current,
                    includeEarthquake: userChangedEarthquake.current,
                    includeSignal: userChangedSignal.current,
                },
                true,
            );
        }
    }, [earthquakeOnly, minMaxSignalThreshold, isInitialLoad, currentScreenshot]);

    // 年選択がリストに存在しなくなった場合はリセット
    useEffect(() => {
        if (selectedYear && !years.includes(selectedYear)) {
            setSelectedYear(null);
        }
    }, [years, selectedYear]);

    // 月選択がリストに存在しなくなった場合はリセット
    useEffect(() => {
        if (selectedMonth && !months.includes(selectedMonth)) {
            setSelectedMonth(null);
        }
    }, [months, selectedMonth]);

    // 日選択がリストに存在しなくなった場合はリセット
    useEffect(() => {
        if (selectedDay && !days.includes(selectedDay)) {
            setSelectedDay(null);
        }
    }, [days, selectedDay]);

    // filteredScreenshotsが変わったら、現在の画像が範囲外なら先頭に移動
    // ただし初回ロード中はスキップ（URLからの指定を優先するため）
    useEffect(() => {
        if (isInitialLoad) return;

        setCurrentScreenshot((prev) => {
            if (filteredScreenshots.length > 0) {
                if (!prev || !filteredScreenshots.find((s) => s.filename === prev.filename)) {
                    return filteredScreenshots[0];
                }
            } else if (signalFilteredScreenshots.length > 0) {
                if (!prev || !signalFilteredScreenshots.find((s) => s.filename === prev.filename)) {
                    return signalFilteredScreenshots[0];
                }
            }
            return prev;
        });
    }, [filteredScreenshots, signalFilteredScreenshots, isInitialLoad]);

    const handleYearChange = (year: number | null) => {
        setSelectedYear(year);
        setSelectedMonth(null);
        setSelectedDay(null);
    };

    const handleMonthChange = (month: number | null) => {
        setSelectedMonth(month);
        setSelectedDay(null);
    };

    const handleDayChange = (day: number | null) => {
        setSelectedDay(day);
    };

    // 地震フィルタ変更ハンドラ（ユーザーの明示的な操作を記録）
    const handleEarthquakeFilterChange = useCallback((checked: boolean) => {
        userChangedEarthquake.current = true;
        setEarthquakeOnly(checked);
    }, []);

    // 振幅フィルタ変更ハンドラ（ユーザーの明示的な操作を記録）
    const handleSignalThresholdChange = useCallback((value: number | undefined) => {
        userChangedSignal.current = true;
        setMinMaxSignalThreshold(value);
    }, []);

    const handleNavigate = useCallback(
        (screenshot: Screenshot) => {
            setShouldScrollToCurrentImage(true);
            setCurrentScreenshot(screenshot);
            // ユーザーがファイルを明示的に選択したことを記録
            userSelectedFile.current = true;
            // popstate処理中でなければURLを更新
            if (!isHandlingPopstate.current) {
                updateUrl(
                    {
                        file: screenshot.filename,
                        earthquake: earthquakeOnly,
                        signal: minMaxSignalThreshold,
                    },
                    {
                        includeFile: true,
                        includeEarthquake: userChangedEarthquake.current,
                        includeSignal: userChangedSignal.current,
                    },
                );
            }
            // スクロール後にフラグをリセット
            setTimeout(() => setShouldScrollToCurrentImage(false), 100);
        },
        [earthquakeOnly, minMaxSignalThreshold],
    );

    // 通知を表示（3秒後に自動消去）
    const showNotification = useCallback((message: string, type: "success" | "info") => {
        setNotification({ message, type });
        setTimeout(() => setNotification(null), 3000);
    }, []);

    const handleRefresh = useCallback(
        async (fullScan: boolean = false) => {
            setIsRefreshing(true);
            try {
                // まずサーバー側で新規ファイルをスキャン
                let newFiles = 0;
                try {
                    const scanResult = await screenshotApi.scanScreenshots(fullScan);
                    newFiles = scanResult.new_files ?? 0;
                } catch (err) {
                    console.error("Scan error:", err);
                    // スキャンが失敗してもデータ読み込みは続行
                }

                // データを再読み込み
                await loadInitialData();

                // 新規ファイルの通知を表示
                if (newFiles > 0) {
                    showNotification(`${newFiles}件の新しいスクリーンショットが追加されました`, "success");
                } else if (fullScan) {
                    // 手動更新時に新規ファイルがない場合も通知
                    showNotification("新しいスクリーンショットはありません", "info");
                }
            } finally {
                setIsRefreshing(false);
            }
        },
        [loadInitialData, showNotification]
    );

    // 手動更新（完全スキャン）
    const handleManualRefresh = useCallback(async () => {
        await handleRefresh(true);
    }, [handleRefresh]);

    // SSE による自動更新フック
    const { isConnected, lastRefreshed, connectionError, manualRefresh } = useAutoRefresh({
        onRefresh: handleRefresh,
        pauseWhenHidden: true,
    });

    // ステータスタグクリック時のハンドラ（完全スキャンを実行）
    const handleStatusClick = useCallback(async () => {
        setIsRefreshing(true);
        try {
            // 未接続の場合は再接続を試みる
            if (!isConnected) {
                manualRefresh();
            }
            // 完全スキャンを実行
            await handleManualRefresh();
        } finally {
            setIsRefreshing(false);
        }
    }, [isConnected, manualRefresh, handleManualRefresh]);

    // 最終更新時刻のフォーマット
    const formatLastRefreshed = (date: Date | null): string => {
        if (!date) return "-";
        return date.toLocaleTimeString("ja-JP", {
            hour: "2-digit",
            minute: "2-digit",
            second: "2-digit",
        });
    };

    // 表示用の画像リスト（日付フィルタが適用されている場合はfilteredScreenshots、そうでなければ振幅フィルタ適用後のリスト）
    const displayImages = useMemo(() => {
        return filteredScreenshots.length > 0 ? filteredScreenshots : signalFilteredScreenshots;
    }, [filteredScreenshots, signalFilteredScreenshots]);

    // グローバルなナビゲーション機能
    const navigateToNext = useCallback(() => {
        if (displayImages.length === 0) return;

        if (!currentScreenshot) {
            // 画像が選択されていない場合は最初の画像を選択
            setCurrentScreenshot(displayImages[0]);
            return;
        }

        const currentIndex = displayImages.findIndex((img) => img.filename === currentScreenshot.filename);
        if (currentIndex < displayImages.length - 1) {
            setCurrentScreenshot(displayImages[currentIndex + 1]);
        }
    }, [currentScreenshot, displayImages]);

    const navigateToPrevious = useCallback(() => {
        if (displayImages.length === 0) return;

        if (!currentScreenshot) {
            // 画像が選択されていない場合は最初の画像を選択
            setCurrentScreenshot(displayImages[0]);
            return;
        }

        const currentIndex = displayImages.findIndex((img) => img.filename === currentScreenshot.filename);
        if (currentIndex > 0) {
            setCurrentScreenshot(displayImages[currentIndex - 1]);
        }
    }, [currentScreenshot, displayImages]);

    // グローバルキーボードイベントハンドラー
    const handleGlobalKeyDown = useCallback(
        (event: KeyboardEvent) => {
            // フォーカスが入力フィールドにある場合はスキップ
            if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) {
                return;
            }

            if (event.key === "ArrowLeft") {
                event.preventDefault();
                navigateToPrevious();
            } else if (event.key === "ArrowRight") {
                event.preventDefault();
                navigateToNext();
            }
        },
        [navigateToPrevious, navigateToNext],
    );

    // グローバルキーボードイベントの登録
    useEffect(() => {
        document.addEventListener("keydown", handleGlobalKeyDown);
        return () => {
            document.removeEventListener("keydown", handleGlobalKeyDown);
        };
    }, [handleGlobalKeyDown]);

    // ブラウザの戻る/進むボタン対応
    useEffect(() => {
        const handlePopstate = () => {
            const urlParams = getUrlParams();
            isHandlingPopstate.current = true;

            // フラグを復元（URLにパラメータがあればそのパラメータは明示的に設定されたとみなす）
            userSelectedFile.current = urlParams.file !== null;
            userChangedEarthquake.current = urlParams.earthquake !== null;
            userChangedSignal.current = urlParams.signal !== null;

            // フィルタ状態を復元
            if (urlParams.earthquake !== null) {
                setEarthquakeOnly(urlParams.earthquake);
            }
            if (urlParams.signal !== null) {
                setMinMaxSignalThreshold(urlParams.signal);
            }

            // ファイル選択を復元
            if (urlParams.file && allScreenshots.length > 0) {
                const targetScreenshot = allScreenshots.find((s) => s.filename === urlParams.file);
                if (targetScreenshot) {
                    setShouldScrollToCurrentImage(true);
                    setCurrentScreenshot(targetScreenshot);
                    setTimeout(() => {
                        setShouldScrollToCurrentImage(false);
                    }, 100);
                }
            }

            setTimeout(() => {
                isHandlingPopstate.current = false;
            }, 100);
        };

        window.addEventListener("popstate", handlePopstate);
        return () => {
            window.removeEventListener("popstate", handlePopstate);
        };
    }, [allScreenshots]);

    return (
        <div className="w-full max-w-full p-2">
            <nav className="flex items-center justify-between bg-gray-800 px-4 py-2 rounded w-full" role="navigation">
                <div className="flex items-center">
                    <a className="flex items-center px-3 py-2 text-white hover:bg-gray-700 rounded transition-colors" href="/rsudp/">
                        <h1 className="text-xl font-semibold text-white flex items-center">
                            <Icon name="camera" className="size-6 mx-2" />
                            <span className="hidden lg:inline">RSUDP スクリーンショットビューア</span>
                            <span className="lg:hidden">
                                RSUDP
                                <br />
                                <span className="text-sm">スクリーンショットビューア</span>
                            </span>
                        </h1>
                    </a>
                </div>

                {/* デスクトップ表示時 */}
                <div className="hidden lg:flex items-center">
                    <div className="px-3 py-2">
                        <span
                            className={`inline-flex items-center px-3 py-1.5 text-base rounded cursor-pointer ${isConnected ? "bg-green-500 text-white" : "bg-yellow-500 text-white"}`}
                            onClick={handleStatusClick}
                            title={
                                isConnected
                                    ? "クリックで更新（サーバーと接続中・新しいデータがあれば自動更新）"
                                    : "クリックで再接続・更新"
                            }
                        >
                            {isRefreshing ? (
                                <Icon name="arrow-path" className="size-4 mr-1" spin />
                            ) : isConnected ? (
                                <Icon name="wifi" className="size-4 mr-1" />
                            ) : (
                                <Icon name="exclamation-triangle" className="size-4 mr-1" />
                            )}
                            <span>{isRefreshing ? "更新中" : isConnected ? "自動更新" : "未接続"}</span>
                        </span>
                    </div>
                    {lastRefreshed && (
                        <div className="px-3 py-2">
                            <span className="text-sm text-gray-400">
                                最終: {formatLastRefreshed(lastRefreshed)}
                            </span>
                        </div>
                    )}
                </div>

                {/* モバイル/タブレット表示時 */}
                <div className="lg:hidden flex items-center">
                    <div className="px-3 py-2">
                        <span
                            className={`inline-flex items-center px-2 py-1 text-sm rounded cursor-pointer ${isConnected ? "bg-green-500 text-white" : "bg-yellow-500 text-white"}`}
                            onClick={handleStatusClick}
                            title={isConnected ? "タップで更新" : connectionError || "タップで再接続・更新"}
                        >
                            {isRefreshing ? (
                                <Icon name="arrow-path" className="size-4 mr-1" spin />
                            ) : isConnected ? (
                                <Icon name="wifi" className="size-4 mr-1" />
                            ) : (
                                <Icon name="exclamation-triangle" className="size-4 mr-1" />
                            )}
                            <span>{isRefreshing ? "更新中" : isConnected ? "自動更新" : "未接続"}</span>
                        </span>
                    </div>
                </div>
            </nav>

            {error && (
                <div className="bg-red-100 border-l-4 border-red-500 text-red-700 p-4 rounded mt-4 flex items-center">
                    <Icon name="exclamation-circle" className="size-5 mr-2" />
                    {error}
                    <button
                        className="ml-auto size-5 rounded-full hover:bg-red-200 flex items-center justify-center"
                        onClick={() => setError(null)}
                    >
                        <Icon name="x-mark" className="size-4" />
                    </button>
                </div>
            )}

            {/* 通知メッセージ */}
            {notification && (
                <div
                    className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg shadow-lg flex items-center gap-2 animate-fade-in ${
                        notification.type === "success"
                            ? "bg-green-500 text-white"
                            : "bg-blue-500 text-white"
                    }`}
                >
                    {notification.type === "success" ? (
                        <Icon name="check-circle" className="size-5" />
                    ) : (
                        <Icon name="information-circle" className="size-5" />
                    )}
                    <span>{notification.message}</span>
                    <button
                        className="ml-2 hover:bg-white/20 rounded-full p-1"
                        onClick={() => setNotification(null)}
                    >
                        <Icon name="x-mark" className="size-4" />
                    </button>
                </div>
            )}

            {/* モバイル/タブレット表示時: 画像を先に表示 */}
            <div className="lg:hidden">
                <div className="mt-2">
                    {loading && !currentScreenshot ? (
                        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[600px]">
                            {/* ヘッダー部分のスケルトン */}
                            <div className="min-h-[80px] mb-4">
                                <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 flex items-center gap-2">
                                    <Icon name="clock" className="size-4" />
                                    発生日時
                                </span>
                                <br />
                                <span
                                    className="inline-block w-[200px] h-5 bg-gray-200 dark:bg-gray-700 rounded animate-pulse-skeleton"
                                />
                            </div>
                            {/* 画像部分のスケルトン */}
                            <div
                                className="min-h-[400px] bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center animate-pulse-skeleton"
                            >
                                <div className="text-center">
                                    <Icon name="arrow-path" className="size-12 text-blue-500" spin />
                                    <p className="text-gray-600 dark:text-gray-400 mt-4">
                                        スクリーンショットを読み込み中...
                                    </p>
                                </div>
                            </div>
                        </div>
                    ) : !currentScreenshot && signalFilteredScreenshots.length === 0 && !loading ? (
                        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[600px]">
                            <div
                                className="flex justify-center items-center min-h-[500px]"
                            >
                                <div className="text-center">
                                    <Icon name="camera" className="size-12 text-gray-400" />
                                    <p className="text-gray-600 dark:text-gray-400 mt-3">スクリーンショットがありません</p>
                                    <p className="text-sm text-gray-500">
                                        地震データが記録されるとここに表示されます
                                    </p>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <ImageViewer
                            currentImage={currentScreenshot}
                            allImages={displayImages}
                            onNavigate={handleNavigate}
                        />
                    )}
                </div>
            </div>

            {/* デスクトップ表示時: 従来のレイアウト */}
            <div className="hidden lg:flex lg:flex-wrap mt-4 gap-4">
                <div
                    className="w-full lg:w-1/3 min-w-[350px] max-w-[400px] space-y-4"
                >
                    <DateSelector
                        years={years}
                        months={months}
                        days={days}
                        selectedYear={selectedYear}
                        selectedMonth={selectedMonth}
                        selectedDay={selectedDay}
                        onYearChange={handleYearChange}
                        onMonthChange={handleMonthChange}
                        onDayChange={handleDayChange}
                        loading={loading}
                    />

                    <FileList
                        allImages={displayImages}
                        currentImage={currentScreenshot}
                        onImageSelect={handleNavigate}
                        loading={loading}
                        shouldScrollToCurrentImage={shouldScrollToCurrentImage}
                        isFiltering={isFiltering}
                    />

                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5">
                        <h2 className="text-lg font-semibold flex items-center gap-2">
                            <Icon name="globe" className="size-5" />
                            地震フィルタ
                            {isFiltering && (
                                <Icon name="arrow-path" className="size-4 text-blue-500" spin />
                            )}
                        </h2>
                        <div className="mb-4 mt-4">
                            <label className="flex items-center cursor-pointer">
                                <input
                                    type="checkbox"
                                    checked={earthquakeOnly}
                                    onChange={(e) => handleEarthquakeFilterChange(e.target.checked)}
                                    className="mr-2 w-4 h-4"
                                    disabled={isFiltering}
                                />
                                震度あり地震のみ表示
                            </label>
                            <p className="mt-1 text-sm text-gray-500">
                                気象庁発表の震度3以上の地震時刻前後のデータのみ表示
                            </p>
                        </div>
                    </div>

                    <SignalFilter
                        statistics={statistics}
                        minMaxSignalThreshold={minMaxSignalThreshold}
                        onThresholdChange={handleSignalThresholdChange}
                        loading={loading && !statistics}
                        isFiltering={isFiltering}
                    />

                    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[120px]">
                        <h2 className="text-lg font-semibold flex items-center gap-2">
                            <Icon name="chart-bar" className="size-5" />
                            統計情報
                        </h2>
                        <div className="mt-4">
                            {loading && !statistics ? (
                                <>
                                    <p>
                                        全スクリーンショット数:{" "}
                                        <span
                                            className="inline-block w-[60px] h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse-skeleton"
                                        />
                                    </p>
                                    <p>
                                        フィルタ後:{" "}
                                        <span
                                            className="inline-block w-[60px] h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse-skeleton"
                                        />
                                    </p>
                                </>
                            ) : (
                                <>
                                    <p>
                                        全スクリーンショット数:{" "}
                                        <strong>{statistics?.absolute_total.toLocaleString() || "0"}</strong> 件
                                    </p>
                                    <p>
                                        フィルタ後:{" "}
                                        <strong>{signalFilteredScreenshots.length.toLocaleString()}</strong>{" "}
                                        件
                                    </p>
                                </>
                            )}
                        </div>
                    </div>
                </div>

                <div className="flex-1">
                    {loading && !currentScreenshot ? (
                        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[600px]">
                            {/* ヘッダー部分のスケルトン */}
                            <div className="flex items-center justify-between min-h-[50px]">
                                <div className="flex items-center">
                                    <div>
                                        <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 flex items-center gap-2">
                                            <Icon name="clock" className="size-4" />
                                            発生日時
                                        </span>
                                        <span
                                            className="inline-block w-[200px] h-5 bg-gray-200 dark:bg-gray-700 rounded animate-pulse-skeleton"
                                        />
                                    </div>
                                </div>
                                <div className="flex items-center">
                                    <span
                                        className="inline-block w-[250px] h-7 bg-gray-200 dark:bg-gray-700 rounded animate-pulse-skeleton"
                                    />
                                </div>
                            </div>
                            {/* 画像部分のスケルトン */}
                            <div
                                className="min-h-[400px] bg-gray-200 dark:bg-gray-700 rounded flex items-center justify-center animate-pulse-skeleton mt-4"
                            >
                                <div className="text-center">
                                    <Icon name="arrow-path" className="size-12 text-blue-500" spin />
                                    <p className="text-gray-600 dark:text-gray-400 mt-4">
                                        スクリーンショットを読み込み中...
                                    </p>
                                </div>
                            </div>
                            {/* ナビゲーション部分のスケルトン */}
                            <div
                                className="flex justify-center items-center gap-4 mt-4"
                            >
                                <span
                                    className="px-4 py-2 rounded bg-blue-500 text-white opacity-50 flex items-center gap-2"
                                >
                                    <Icon name="chevron-left" className="size-5" />
                                    <span>前へ</span>
                                </span>
                                <span className="inline-flex items-center px-3 py-1 text-sm rounded bg-gray-100 dark:bg-gray-700">- / -</span>
                                <span
                                    className="px-4 py-2 rounded bg-blue-500 text-white opacity-50 flex items-center gap-2"
                                >
                                    <span>次へ</span>
                                    <Icon name="chevron-right" className="size-5" />
                                </span>
                            </div>
                        </div>
                    ) : !currentScreenshot && signalFilteredScreenshots.length === 0 && !loading ? (
                        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[600px]">
                            <div
                                className="flex justify-center items-center min-h-[500px]"
                            >
                                <div className="text-center">
                                    <Icon name="camera" className="size-12 text-gray-400" />
                                    <p className="text-gray-600 dark:text-gray-400 mt-3">スクリーンショットがありません</p>
                                    <p className="text-sm text-gray-500">
                                        地震データが記録されるとここに表示されます
                                    </p>
                                </div>
                            </div>
                        </div>
                    ) : (
                        <ImageViewer
                            currentImage={currentScreenshot}
                            allImages={displayImages}
                            onNavigate={handleNavigate}
                        />
                    )}
                </div>
            </div>

            {/* モバイル/タブレット表示時: DateSelectorとFileListを画像の下に配置 */}
            <div className="lg:hidden mt-4 space-y-4">
                <DateSelector
                    years={years}
                    months={months}
                    days={days}
                    selectedYear={selectedYear}
                    selectedMonth={selectedMonth}
                    selectedDay={selectedDay}
                    onYearChange={handleYearChange}
                    onMonthChange={handleMonthChange}
                    onDayChange={handleDayChange}
                    loading={loading}
                />

                <FileList
                    allImages={displayImages}
                    currentImage={currentScreenshot}
                    onImageSelect={handleNavigate}
                    loading={loading}
                    shouldScrollToCurrentImage={shouldScrollToCurrentImage}
                    isFiltering={isFiltering}
                />

                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Icon name="globe" className="size-5" />
                        地震フィルタ
                        {isFiltering && (
                            <Icon name="arrow-path" className="size-4 text-blue-500" spin />
                        )}
                    </h2>
                    <div className="mb-4 mt-4">
                        <label className="flex items-center cursor-pointer">
                            <input
                                type="checkbox"
                                checked={earthquakeOnly}
                                onChange={(e) => handleEarthquakeFilterChange(e.target.checked)}
                                className="mr-2 w-4 h-4"
                                disabled={isFiltering}
                            />
                            震度あり地震のみ表示
                        </label>
                        <p className="mt-1 text-sm text-gray-500">
                            気象庁発表の震度3以上の地震時刻前後のデータのみ表示
                            {statistics?.earthquake_count !== undefined && (
                                <>
                                    <br />
                                    （記録済み: {statistics.earthquake_count}件）
                                </>
                            )}
                        </p>
                    </div>
                </div>

                <SignalFilter
                    statistics={statistics}
                    minMaxSignalThreshold={minMaxSignalThreshold}
                    onThresholdChange={handleSignalThresholdChange}
                    loading={loading && !statistics}
                    isFiltering={isFiltering}
                />

                <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[120px]">
                    <h2 className="text-lg font-semibold flex items-center gap-2">
                        <Icon name="chart-bar" className="size-5" />
                        統計情報
                    </h2>
                    <div className="mt-4">
                        {loading && !statistics ? (
                            <>
                                <p>
                                    全スクリーンショット数:{" "}
                                    <span
                                        className="inline-block w-[60px] h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse-skeleton"
                                    />
                                </p>
                                <p>
                                    フィルタ後:{" "}
                                    <span
                                        className="inline-block w-[60px] h-4 bg-gray-200 dark:bg-gray-700 rounded animate-pulse-skeleton"
                                    />
                                </p>
                            </>
                        ) : (
                            <>
                                <p>
                                    全スクリーンショット数:{" "}
                                    <strong>{statistics?.absolute_total.toLocaleString() || "0"}</strong> 件
                                </p>
                                <p>
                                    フィルタ後:{" "}
                                    <strong>{signalFilteredScreenshots.length.toLocaleString()}</strong> 件
                                </p>
                            </>
                        )}
                    </div>
                </div>
            </div>

            <Footer />
        </div>
    );
};

export default App;
