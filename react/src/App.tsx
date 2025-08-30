import React, { useState, useEffect, useCallback } from 'react';
import type { Screenshot, StatisticsResponse } from './types';
import { screenshotApi } from './api';
import DateSelector from './components/DateSelector';
import ImageViewer from './components/ImageViewer';
import FileList from './components/FileList';
import Footer from './components/Footer';
import STAFilter from './components/STAFilter';
import 'bulma/css/bulma.min.css';

const App: React.FC = () => {
  const [years, setYears] = useState<number[]>([]);
  const [months, setMonths] = useState<number[]>([]);
  const [days, setDays] = useState<number[]>([]);

  const [selectedYear, setSelectedYear] = useState<number | null>(null);
  const [selectedMonth, setSelectedMonth] = useState<number | null>(null);
  const [selectedDay, setSelectedDay] = useState<number | null>(null);

  const [allScreenshots, setAllScreenshots] = useState<Screenshot[]>([]);
  const [filteredScreenshots, setFilteredScreenshots] = useState<Screenshot[]>([]);
  const [currentScreenshot, setCurrentScreenshot] = useState<Screenshot | null>(null);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [minStaThreshold, setMinStaThreshold] = useState<number | undefined>(undefined);
  const [statistics, setStatistics] = useState<StatisticsResponse | null>(null);
  const [isInitialLoad, setIsInitialLoad] = useState(true);

  // Load years on mount
  useEffect(() => {
    loadInitialData();
  }, []);

  // Reload data when STA threshold changes (with debounce)
  useEffect(() => {
    if (statistics && !isInitialLoad) { // Only reload if we've already loaded initial data and not initial load
      // Debounce API calls to prevent too many requests
      const timeoutId = setTimeout(() => {
        loadDataWithFilter();
      }, 500); // Wait 500ms after last change
      
      return () => clearTimeout(timeoutId);
    }
  }, [minStaThreshold]);

  // Load months when year changes
  useEffect(() => {
    if (selectedYear) {
      loadMonths(selectedYear);
    } else {
      setMonths([]);
      setSelectedMonth(null);
    }
  }, [selectedYear, minStaThreshold]);

  // Load days when month changes
  useEffect(() => {
    if (selectedYear && selectedMonth) {
      loadDays(selectedYear, selectedMonth);
    } else {
      setDays([]);
      setSelectedDay(null);
    }
  }, [selectedYear, selectedMonth, minStaThreshold]);

  // Filter screenshots when date selection changes
  useEffect(() => {
    filterScreenshots();
  }, [selectedYear, selectedMonth, selectedDay, allScreenshots]);

  const loadInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Loading initial data from API...');
      // Load statistics first
      const stats = await screenshotApi.getStatistics();
      setStatistics(stats);

      // Set initial minimum STA threshold to the actual minimum value
      const initialMinSta = stats.min_sta !== undefined ? Math.floor(stats.min_sta) : undefined;
      if (initialMinSta !== undefined) {
        setMinStaThreshold(initialMinSta);
      }

      // Load all screenshots and years with initial threshold
      const [screenshotsData, yearsData] = await Promise.all([
        screenshotApi.getAllScreenshots(initialMinSta),
        screenshotApi.getYears(initialMinSta)
      ]);

      console.log('API Response - Screenshots:', screenshotsData.length, 'Years:', yearsData);
      setAllScreenshots(screenshotsData);
      setYears(yearsData);

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
  };

  const loadDataWithFilter = async () => {
    setLoading(true);
    setError(null);
    try {
      // Load all screenshots and years with filter
      const [screenshotsData, yearsData] = await Promise.all([
        screenshotApi.getAllScreenshots(minStaThreshold),
        screenshotApi.getYears(minStaThreshold)
      ]);

      setAllScreenshots(screenshotsData);
      setYears(yearsData);

      // Reset selections if they're no longer valid
      if (selectedYear && !yearsData.includes(selectedYear)) {
        setSelectedYear(null);
        setSelectedMonth(null);
        setSelectedDay(null);
      }

      // Set the latest screenshot as current
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
    }
  };

  const loadMonths = async (year: number) => {
    setLoading(true);
    try {
      const monthsData = await screenshotApi.getMonths(year, minStaThreshold);
      setMonths(monthsData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const loadDays = async (year: number, month: number) => {
    setLoading(true);
    try {
      const daysData = await screenshotApi.getDays(year, month, minStaThreshold);
      setDays(daysData);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const filterScreenshots = () => {
    let filtered = [...allScreenshots];

    if (selectedYear) {
      filtered = filtered.filter(s => s.year === selectedYear);
    }
    if (selectedMonth) {
      filtered = filtered.filter(s => s.month === selectedMonth);
    }
    if (selectedDay) {
      filtered = filtered.filter(s => s.day === selectedDay);
    }

    setFilteredScreenshots(filtered);

    // Update current screenshot if it's not in filtered list
    if (filtered.length > 0 && (!currentScreenshot || !filtered.includes(currentScreenshot))) {
      setCurrentScreenshot(filtered[0]);
    } else if (filtered.length === 0) {
      setCurrentScreenshot(null);
    }
  };

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
    setCurrentScreenshot(screenshot);
  };

  const handleRefresh = () => {
    loadInitialData();
  };

  // グローバルなナビゲーション機能
  const navigateToNext = useCallback(() => {
    const availableImages = filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots;
    if (availableImages.length === 0) return;

    if (!currentScreenshot) {
      // 画像が選択されていない場合は最初の画像を選択
      setCurrentScreenshot(availableImages[0]);
      return;
    }

    const currentIndex = availableImages.findIndex(img => img.filename === currentScreenshot.filename);
    if (currentIndex < availableImages.length - 1) {
      setCurrentScreenshot(availableImages[currentIndex + 1]);
    }
  }, [currentScreenshot, filteredScreenshots, allScreenshots]);

  const navigateToPrevious = useCallback(() => {
    const availableImages = filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots;
    if (availableImages.length === 0) return;

    if (!currentScreenshot) {
      // 画像が選択されていない場合は最初の画像を選択
      setCurrentScreenshot(availableImages[0]);
      return;
    }

    const currentIndex = availableImages.findIndex(img => img.filename === currentScreenshot.filename);
    if (currentIndex > 0) {
      setCurrentScreenshot(availableImages[currentIndex - 1]);
    }
  }, [currentScreenshot, filteredScreenshots, allScreenshots]);

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
    <div className="container is-fluid" style={{ padding: '0.5rem' }}>
      <nav className="navbar is-dark" role="navigation">
        <div className="navbar-brand">
          <div className="navbar-item">
            <h1 className="title is-4 has-text-white">
              <span className="icon" style={{ marginLeft: '0.5rem', marginRight: '0.5rem' }}>
                <i className="fas fa-camera"></i>
              </span>
              <span className="is-hidden-mobile">RSUDP スクリーンショットビューア</span>
              <span className="is-hidden-tablet">
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
              disabled={loading}
            >
              <span className="icon">
                <i className="fas fa-sync"></i>
              </span>
              <span>更新</span>
            </button>
          </div>
        </div>

        {/* モバイル/タブレット表示時 */}
        <div className="navbar-end is-hidden-desktop">
          <div className="navbar-item">
            <button
              className="button is-light is-small"
              onClick={handleRefresh}
              disabled={loading}
            >
              <span className="icon">
                <i className="fas fa-sync"></i>
              </span>
              <span>更新</span>
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

      {/* モバイル表示時: 画像を先に表示 */}
      <div className="is-hidden-tablet">
        <div style={{ marginTop: '0.5rem' }}>
          {loading && !currentScreenshot ? (
            <div className="box has-text-centered" style={{ minHeight: '400px' }}>
              <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '300px' }}>
                <div>
                  <span className="icon is-large">
                    <i className="fas fa-spinner fa-pulse fa-3x"></i>
                  </span>
                  <p className="subtitle" style={{ marginTop: '1rem' }}>
                    <span className="icon" style={{ marginRight: '0.5rem' }}>
                      <i className="fas fa-hourglass-half"></i>
                    </span>
                    スクリーンショットを読み込み中...
                  </p>
                </div>
              </div>
            </div>
          ) : !currentScreenshot && allScreenshots.length === 0 && !loading ? (
            <div className="box has-text-centered" style={{ minHeight: '400px' }}>
              <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '300px' }}>
                <div>
                  <span className="icon is-large has-text-grey">
                    <i className="fas fa-camera fa-3x"></i>
                  </span>
                  <p className="subtitle mt-3">
                    <span className="icon" style={{ marginRight: '0.5rem' }}>
                      <i className="fas fa-camera"></i>
                    </span>
                    スクリーンショットがありません
                  </p>
                  <p className="is-size-7 has-text-grey">地震データが記録されるとここに表示されます</p>
                </div>
              </div>
            </div>
          ) : (
            <ImageViewer
              currentImage={currentScreenshot}
              allImages={filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots}
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
            allImages={filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots}
            currentImage={currentScreenshot}
            onImageSelect={handleNavigate}
            loading={loading}
          />

          {statistics && (
            <STAFilter
              statistics={statistics}
              minStaThreshold={minStaThreshold}
              onThresholdChange={setMinStaThreshold}
            />
          )}

          <div className="box" style={{ minHeight: '120px' }}>
            <h2 className="title is-5">
            <span className="icon" style={{ marginRight: '0.5rem' }}>
              <i className="fas fa-chart-bar"></i>
            </span>
            統計情報
          </h2>
            <div className="content">
              <p>全スクリーンショット数: <strong>{statistics?.total.toLocaleString() || '0'}</strong> 件</p>
              <p>フィルタ後: <strong>{allScreenshots.length.toLocaleString()}</strong> 件</p>
            </div>
          </div>
        </div>

        <div className="column is-8-desktop is-12-tablet">
          {loading && !currentScreenshot ? (
            <div className="box has-text-centered" style={{ minHeight: '400px' }}>
              <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '300px' }}>
                <div>
                  <span className="icon is-large">
                    <i className="fas fa-spinner fa-pulse fa-3x"></i>
                  </span>
                  <p className="subtitle" style={{ marginTop: '1rem' }}>
                    <span className="icon" style={{ marginRight: '0.5rem' }}>
                      <i className="fas fa-hourglass-half"></i>
                    </span>
                    スクリーンショットを読み込み中...
                  </p>
                </div>
              </div>
            </div>
          ) : !currentScreenshot && allScreenshots.length === 0 && !loading ? (
            <div className="box has-text-centered" style={{ minHeight: '400px' }}>
              <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '300px' }}>
                <div>
                  <span className="icon is-large has-text-grey">
                    <i className="fas fa-camera fa-3x"></i>
                  </span>
                  <p className="subtitle mt-3">
                    <span className="icon" style={{ marginRight: '0.5rem' }}>
                      <i className="fas fa-camera"></i>
                    </span>
                    スクリーンショットがありません
                  </p>
                  <p className="is-size-7 has-text-grey">地震データが記録されるとここに表示されます</p>
                </div>
              </div>
            </div>
          ) : (
            <ImageViewer
              currentImage={currentScreenshot}
              allImages={filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots}
              onNavigate={handleNavigate}
            />
          )}
        </div>
      </div>

      {/* モバイル表示時: DateSelectorとFileListを画像の下に配置 */}
      <div className="is-hidden-tablet" style={{ marginTop: '1rem' }}>
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
          allImages={filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots}
          currentImage={currentScreenshot}
          onImageSelect={handleNavigate}
          loading={loading}
        />

        {statistics && (
          <STAFilter
            statistics={statistics}
            minStaThreshold={minStaThreshold}
            onThresholdChange={setMinStaThreshold}
          />
        )}

        <div className="box" style={{ minHeight: '120px' }}>
          <h2 className="title is-5">
            <span className="icon" style={{ marginRight: '0.5rem' }}>
              <i className="fas fa-chart-bar"></i>
            </span>
            統計情報
          </h2>
          <div className="content">
            <p>全スクリーンショット数: <strong>{statistics?.total.toLocaleString() || '0'}</strong> 件</p>
            <p>フィルタ後: <strong>{allScreenshots.length.toLocaleString()}</strong> 件</p>
          </div>
        </div>
      </div>

      <Footer />
    </div>
  );
};

export default App;
