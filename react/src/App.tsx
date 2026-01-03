import React, { useState, useEffect, useCallback, useMemo } from 'react';
import type { Screenshot, StatisticsResponse } from './types';
import { screenshotApi } from './api';
import DateSelector from './components/DateSelector';
import ImageViewer from './components/ImageViewer';
import FileList from './components/FileList';
import Footer from './components/Footer';
import SignalFilter from './components/SignalFilter';
import 'bulma/css/bulma.min.css';

const App: React.FC = () => {
  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  // allScreenshots: 地震フィルタ適用後の全データ（振幅フィルタ前）
  const [allScreenshots, setAllScreenshots] = useState<Screenshot[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<Screenshot | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [minMaxSignalThreshold, setMinMaxSignalThreshold] = useState<number | undefined>(undefined);
  const [statistics, setStatistics] = useState<StatisticsResponse | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);
  const [earthquakeOnly, setEarthquakeOnly] = useState(true);
  const [shouldScrollToCurrentImage, setShouldScrollToCurrentImage] = useState(false);
  const [isFiltering, setIsFiltering] = useState(false); // フィルタ適用中フラグ
  const [isRefreshing, setIsRefreshing] = useState(false); // 更新ボタン押下中フラグ

  // クライアント側で振幅フィルタを適用（APIリクエスト不要）
  const signalFilteredScreenshots = useMemo(() => {
    if (minMaxSignalThreshold === undefined) {
      return allScreenshots;
    }
    return allScreenshots.filter(s => s.max_count >= minMaxSignalThreshold);
  }, [allScreenshots, minMaxSignalThreshold]);

  // クライアント側で年リストを計算
  const years = useMemo(() => {
    const yearSet = new Set(signalFilteredScreenshots.map(s => s.year));
    return Array.from(yearSet).sort((a, b) => b - a);
  }, [signalFilteredScreenshots]);

  // クライアント側で月リストを計算
  const months = useMemo(() => {
    if (!selectedYear) return [];
    const monthSet = new Set(
      signalFilteredScreenshots
        .filter(s => s.year === selectedYear)
        .map(s => s.month)
    );
    return Array.from(monthSet).sort((a, b) => b - a);
  }, [signalFilteredScreenshots, selectedYear]);

  // クライアント側で日リストを計算
  const days = useMemo(() => {
    if (!selectedYear || !selectedMonth) return [];
    const daySet = new Set(
      signalFilteredScreenshots
        .filter(s => s.year === selectedYear && s.month === selectedMonth)
        .map(s => s.day)
    );
    return Array.from(daySet).sort((a, b) => b - a);
  }, [signalFilteredScreenshots, selectedYear, selectedMonth]);

  // 日付フィルタ適用後のスクリーンショット
  const filteredScreenshots = useMemo(() => {
    let filtered = signalFilteredScreenshots;
    if (selectedYear) {
      filtered = filtered.filter(s => s.year === selectedYear);
    }
    if (selectedMonth) {
      filtered = filtered.filter(s => s.month === selectedMonth);
    }
    if (selectedDay) {
      filtered = filtered.filter(s => s.day === selectedDay);
    }
    return filtered;
  }, [signalFilteredScreenshots, selectedYear, selectedMonth, selectedDay]);

  // データ読み込み関数（useCallbackでメモ化）
  const loadInitialData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Loading initial data from API...');
      // Load statistics and screenshots in parallel
      const [stats, screenshotsData] = await Promise.all([
        screenshotApi.getStatistics(earthquakeOnly),
        screenshotApi.getAllScreenshots(undefined, earthquakeOnly),
      ]);

      setStatistics(stats);
      setAllScreenshots(screenshotsData);

      // Set initial minimum maximum signal threshold to the actual minimum value
      const initialMinMaxSignal = stats.min_signal !== undefined ? Math.floor(stats.min_signal) : undefined;
      if (initialMinMaxSignal !== undefined) {
        setMinMaxSignalThreshold(initialMinMaxSignal);
      }

      console.log('API Response - Screenshots:', screenshotsData.length);

      // Set the latest screenshot as current
      if (screenshotsData.length > 0) {
        setCurrentScreenshot(screenshotsData[0]);
      }

      setIsInitialLoad(false);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to load screenshots: ${errorMessage}`);
      console.error('API Error:', err);
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
        setMinMaxSignalThreshold(prev => (prev === undefined || prev < newMin) ? newMin : prev);
      }

      // Set the latest screenshot as current (フィルタ変更時はスクロールしない)
      if (screenshotsData.length > 0) {
        setCurrentScreenshot(screenshotsData[0]);
      } else {
        setCurrentScreenshot(null);
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to load screenshots: ${errorMessage}`);
      console.error('API Error:', err);
    } finally {
      setLoading(false);
      setIsFiltering(false);
    }
  }, [earthquakeOnly]);

  // Load data on mount
  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  // 地震フィルタ変更時はAPIからデータ再取得（初回ロード後のみ）
  useEffect(() => {
    if (!isInitialLoad) {
      loadDataWithFilter();
    }
  }, [earthquakeOnly, loadDataWithFilter, isInitialLoad]);

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
  useEffect(() => {
    setCurrentScreenshot(prev => {
      if (filteredScreenshots.length > 0) {
        if (!prev || !filteredScreenshots.find(s => s.filename === prev.filename)) {
          return filteredScreenshots[0];
        }
      } else if (signalFilteredScreenshots.length > 0) {
        if (!prev || !signalFilteredScreenshots.find(s => s.filename === prev.filename)) {
          return signalFilteredScreenshots[0];
        }
      }
      return prev;
    });
  }, [filteredScreenshots, signalFilteredScreenshots]);

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

  const handleNavigate = (screenshot: Screenshot) => {
    setShouldScrollToCurrentImage(true);
    setCurrentScreenshot(screenshot);
    // スクロール後にフラグをリセット
    setTimeout(() => setShouldScrollToCurrentImage(false), 100);
  };

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      // まずサーバー側で新規ファイルをスキャン
      try {
        await screenshotApi.scanScreenshots();
      } catch (err) {
        console.error('Scan error:', err);
        // スキャンが失敗してもデータ読み込みは続行
      }
      // データを再読み込み
      await loadInitialData();
    } finally {
      setIsRefreshing(false);
    }
  }, [loadInitialData]);

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

    const currentIndex = displayImages.findIndex(img => img.filename === currentScreenshot.filename);
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

    const currentIndex = displayImages.findIndex(img => img.filename === currentScreenshot.filename);
    if (currentIndex > 0) {
      setCurrentScreenshot(displayImages[currentIndex - 1]);
    }
  }, [currentScreenshot, displayImages]);

  // グローバルキーボードイベントハンドラー
  const handleGlobalKeyDown = useCallback((event: KeyboardEvent) => {
    // フォーカスが入力フィールドにある場合はスキップ
    if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement) {
      return;
    }

    if (event.key === 'ArrowLeft') {
      event.preventDefault();
      navigateToPrevious();
    } else if (event.key === 'ArrowRight') {
      event.preventDefault();
      navigateToNext();
    }
  }, [navigateToPrevious, navigateToNext]);

  // グローバルキーボードイベントの登録
  useEffect(() => {
    document.addEventListener('keydown', handleGlobalKeyDown);
    return () => {
      document.removeEventListener('keydown', handleGlobalKeyDown);
    };
  }, [handleGlobalKeyDown]);

  return (
    <div className="container is-fluid" style={{ padding: '0.5rem', width: '100%', maxWidth: '100%' }}>
      <nav className="navbar is-dark" role="navigation" style={{ width: '100%' }}>
        <div className="navbar-brand">
          <div className="navbar-item">
            <h1 className="title is-4 has-text-white">
              <span className="icon" style={{ marginLeft: '0.5rem', marginRight: '0.5rem' }}>
                <i className="fas fa-camera"></i>
              </span>
              <span className="is-hidden-touch">RSUDP スクリーンショットビューア</span>
              <span className="is-hidden-desktop">
                RSUDP<br />
                <span style={{ fontSize: '0.9em' }}>スクリーンショットビューア</span>
              </span>
            </h1>
          </div>
        </div>

        {/* デスクトップ表示時 */}
        <div className="navbar-end is-hidden-touch">
          <div className="navbar-item">
            <button
              className="button is-light"
              onClick={handleRefresh}
              disabled={loading || isRefreshing}
            >
              <span className="icon">
                <i className={isRefreshing ? "fas fa-sync fa-spin" : "fas fa-sync"}></i>
              </span>
              <span>{isRefreshing ? "更新中..." : "更新"}</span>
            </button>
          </div>
        </div>

        {/* モバイル/タブレット表示時 */}
        <div className="navbar-end is-hidden-desktop">
          <div className="navbar-item">
            <button
              className="button is-light is-small"
              onClick={handleRefresh}
              disabled={loading || isRefreshing}
            >
              <span className="icon">
                <i className={isRefreshing ? "fas fa-sync fa-spin" : "fas fa-sync"}></i>
              </span>
              <span>{isRefreshing ? "更新中..." : "更新"}</span>
            </button>
          </div>
        </div>
      </nav>

      {error && (
        <div className="notification is-danger" style={{ marginTop: '1rem' }}>
          <button className="delete" onClick={() => setError(null)}></button>
          <span className="icon" style={{ marginRight: '0.5rem' }}>
            <i className="fas fa-exclamation-circle"></i>
          </span>
          {error}
        </div>
      )}

      {/* モバイル/タブレット表示時: 画像を先に表示 */}
      <div className="is-hidden-desktop">
        <div style={{ marginTop: '0.5rem' }}>
          {loading && !currentScreenshot ? (
            <div className="box" style={{ minHeight: '600px' }}>
              {/* ヘッダー部分のスケルトン */}
              <div style={{ minHeight: '80px', marginBottom: '1rem' }}>
                <span className="heading">
                  <span className="icon" style={{ marginRight: '0.5rem' }}>
                    <i className="fas fa-clock"></i>
                  </span>
                  発生日時
                </span>
                <br />
                <span
                  style={{
                    display: 'inline-block',
                    width: '200px',
                    height: '1.2em',
                    backgroundColor: '#f5f5f5',
                    borderRadius: '4px',
                    animation: 'pulse 1.5s ease-in-out infinite'
                  }}
                />
              </div>
              {/* 画像部分のスケルトン */}
              <div
                style={{
                  minHeight: '400px',
                  backgroundColor: '#f5f5f5',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  animation: 'pulse 1.5s ease-in-out infinite'
                }}
              >
                <div className="has-text-centered">
                  <span className="icon is-large">
                    <i className="fas fa-spinner fa-pulse fa-3x"></i>
                  </span>
                  <p className="subtitle" style={{ marginTop: '1rem' }}>
                    スクリーンショットを読み込み中...
                  </p>
                </div>
              </div>
            </div>
          ) : !currentScreenshot && signalFilteredScreenshots.length === 0 && !loading ? (
            <div className="box" style={{ minHeight: '600px' }}>
              <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '500px' }}>
                <div className="has-text-centered">
                  <span className="icon is-large has-text-grey">
                    <i className="fas fa-camera fa-3x"></i>
                  </span>
                  <p className="subtitle mt-3">
                    スクリーンショットがありません
                  </p>
                  <p className="is-size-7 has-text-grey">地震データが記録されるとここに表示されます</p>
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
      <div className="columns is-desktop is-hidden-touch" style={{ marginTop: '1rem' }}>
        <div className="column is-4-desktop is-12-tablet" style={{ minWidth: '350px', maxWidth: '400px' }}>
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

          <div className="box">
            <h2 className="title is-5">
              <span className="icon" style={{ marginRight: '0.5rem' }}>
                <i className="fas fa-globe"></i>
              </span>
              地震フィルタ
              {isFiltering && (
                <span className="icon is-small has-text-info" style={{ marginLeft: '0.5rem' }}>
                  <i className="fas fa-spinner fa-pulse"></i>
                </span>
              )}
            </h2>
            <div className="field">
              <label className="checkbox">
                <input
                  type="checkbox"
                  checked={earthquakeOnly}
                  onChange={(e) => setEarthquakeOnly(e.target.checked)}
                  style={{ marginRight: '0.5rem' }}
                  disabled={isFiltering}
                />
                震度あり地震のみ表示
              </label>
              <p className="help">
                気象庁発表の震度3以上の地震時刻前後のデータのみ表示
                {statistics?.earthquake_count !== undefined && (
                  <><br />（記録済み: {statistics.earthquake_count}件）</>
                )}
              </p>
            </div>
          </div>

          <SignalFilter
            statistics={statistics}
            minMaxSignalThreshold={minMaxSignalThreshold}
            onThresholdChange={setMinMaxSignalThreshold}
            loading={loading && !statistics}
            isFiltering={isFiltering}
          />

          <div className="box" style={{ minHeight: '120px' }}>
            <h2 className="title is-5">
              <span className="icon" style={{ marginRight: '0.5rem' }}>
                <i className="fas fa-chart-bar"></i>
              </span>
              統計情報
            </h2>
            <div className="content">
              {loading && !statistics ? (
                <>
                  <p>
                    全スクリーンショット数:{' '}
                    <span
                      style={{
                        display: 'inline-block',
                        width: '60px',
                        height: '1em',
                        backgroundColor: '#f5f5f5',
                        borderRadius: '4px',
                        animation: 'pulse 1.5s ease-in-out infinite'
                      }}
                    />
                  </p>
                  <p>
                    フィルタ後:{' '}
                    <span
                      style={{
                        display: 'inline-block',
                        width: '60px',
                        height: '1em',
                        backgroundColor: '#f5f5f5',
                        borderRadius: '4px',
                        animation: 'pulse 1.5s ease-in-out infinite'
                      }}
                    />
                  </p>
                </>
              ) : (
                <>
                  <p>全スクリーンショット数: <strong>{statistics?.total.toLocaleString() || '0'}</strong> 件</p>
                  <p>フィルタ後: <strong>{signalFilteredScreenshots.length.toLocaleString()}</strong> 件</p>
                </>
              )}
            </div>
          </div>
        </div>

        <div className="column is-8-desktop is-12-tablet">
          {loading && !currentScreenshot ? (
            <div className="box" style={{ minHeight: '600px' }}>
              {/* ヘッダー部分のスケルトン */}
              <div className="level is-mobile" style={{ minHeight: '50px' }}>
                <div className="level-left">
                  <div className="level-item">
                    <div>
                      <span className="heading">
                        <span className="icon" style={{ marginRight: '0.5rem' }}>
                          <i className="fas fa-clock"></i>
                        </span>
                        発生日時
                      </span>
                      <span
                        style={{
                          display: 'inline-block',
                          width: '200px',
                          height: '1.2em',
                          backgroundColor: '#f5f5f5',
                          borderRadius: '4px',
                          animation: 'pulse 1.5s ease-in-out infinite'
                        }}
                      />
                    </div>
                  </div>
                </div>
                <div className="level-right">
                  <div className="level-item">
                    <span
                      style={{
                        display: 'inline-block',
                        width: '250px',
                        height: '28px',
                        backgroundColor: '#f5f5f5',
                        borderRadius: '4px',
                        animation: 'pulse 1.5s ease-in-out infinite'
                      }}
                    />
                  </div>
                </div>
              </div>
              {/* 画像部分のスケルトン */}
              <div
                style={{
                  minHeight: '400px',
                  backgroundColor: '#f5f5f5',
                  borderRadius: '4px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  animation: 'pulse 1.5s ease-in-out infinite'
                }}
              >
                <div className="has-text-centered">
                  <span className="icon is-large">
                    <i className="fas fa-spinner fa-pulse fa-3x"></i>
                  </span>
                  <p className="subtitle" style={{ marginTop: '1rem' }}>
                    スクリーンショットを読み込み中...
                  </p>
                </div>
              </div>
              {/* ナビゲーション部分のスケルトン */}
              <div className="field is-grouped is-grouped-centered" style={{ marginTop: '1rem' }}>
                <p className="control">
                  <span className="button is-info" style={{ opacity: 0.5 }} aria-disabled="true">
                    <span className="icon"><i className="fas fa-chevron-left"></i></span>
                    <span>前へ</span>
                  </span>
                </p>
                <p className="control">
                  <span className="tag is-light">- / -</span>
                </p>
                <p className="control">
                  <span className="button is-info" style={{ opacity: 0.5 }} aria-disabled="true">
                    <span>次へ</span>
                    <span className="icon"><i className="fas fa-chevron-right"></i></span>
                  </span>
                </p>
              </div>
            </div>
          ) : !currentScreenshot && signalFilteredScreenshots.length === 0 && !loading ? (
            <div className="box" style={{ minHeight: '600px' }}>
              <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '500px' }}>
                <div className="has-text-centered">
                  <span className="icon is-large has-text-grey">
                    <i className="fas fa-camera fa-3x"></i>
                  </span>
                  <p className="subtitle mt-3">
                    スクリーンショットがありません
                  </p>
                  <p className="is-size-7 has-text-grey">地震データが記録されるとここに表示されます</p>
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
      <div className="is-hidden-desktop" style={{ marginTop: '1rem' }}>
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

        <div className="box">
          <h2 className="title is-5">
            <span className="icon" style={{ marginRight: '0.5rem' }}>
              <i className="fas fa-globe"></i>
            </span>
            地震フィルタ
            {isFiltering && (
              <span className="icon is-small has-text-info" style={{ marginLeft: '0.5rem' }}>
                <i className="fas fa-spinner fa-pulse"></i>
              </span>
            )}
          </h2>
          <div className="field">
            <label className="checkbox">
              <input
                type="checkbox"
                checked={earthquakeOnly}
                onChange={(e) => setEarthquakeOnly(e.target.checked)}
                style={{ marginRight: '0.5rem' }}
                disabled={isFiltering}
              />
              震度あり地震のみ表示
            </label>
            <p className="help">
              気象庁発表の震度3以上の地震時刻前後のデータのみ表示
              {statistics?.earthquake_count !== undefined && (
                <><br />（記録済み: {statistics.earthquake_count}件）</>
              )}
            </p>
          </div>
        </div>

        <SignalFilter
          statistics={statistics}
          minMaxSignalThreshold={minMaxSignalThreshold}
          onThresholdChange={setMinMaxSignalThreshold}
          loading={loading && !statistics}
          isFiltering={isFiltering}
        />

        <div className="box" style={{ minHeight: '120px' }}>
          <h2 className="title is-5">
            <span className="icon" style={{ marginRight: '0.5rem' }}>
              <i className="fas fa-chart-bar"></i>
            </span>
            統計情報
          </h2>
          <div className="content">
            {loading && !statistics ? (
              <>
                <p>
                  全スクリーンショット数:{' '}
                  <span
                    style={{
                      display: 'inline-block',
                      width: '60px',
                      height: '1em',
                      backgroundColor: '#f5f5f5',
                      borderRadius: '4px',
                      animation: 'pulse 1.5s ease-in-out infinite'
                    }}
                  />
                </p>
                <p>
                  フィルタ後:{' '}
                  <span
                    style={{
                      display: 'inline-block',
                      width: '60px',
                      height: '1em',
                      backgroundColor: '#f5f5f5',
                      borderRadius: '4px',
                      animation: 'pulse 1.5s ease-in-out infinite'
                    }}
                  />
                </p>
              </>
            ) : (
              <>
                <p>全スクリーンショット数: <strong>{statistics?.total.toLocaleString() || '0'}</strong> 件</p>
                <p>フィルタ後: <strong>{signalFilteredScreenshots.length.toLocaleString()}</strong> 件</p>
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
