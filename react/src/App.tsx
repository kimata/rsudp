import React, { useState, useEffect } from 'react';
import type { Screenshot } from './types';
import { screenshotApi } from './api';
import DateSelector from './components/DateSelector';
import ImageViewer from './components/ImageViewer';
import FileList from './components/FileList';
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

  // Load years on mount
  useEffect(() => {
    loadInitialData();
  }, []);

  // Load months when year changes
  useEffect(() => {
    if (selectedYear) {
      loadMonths(selectedYear);
    } else {
      setMonths([]);
      setSelectedMonth(null);
    }
  }, [selectedYear]);

  // Load days when month changes
  useEffect(() => {
    if (selectedYear && selectedMonth) {
      loadDays(selectedYear, selectedMonth);
    } else {
      setDays([]);
      setSelectedDay(null);
    }
  }, [selectedYear, selectedMonth]);

  // Filter screenshots when date selection changes
  useEffect(() => {
    filterScreenshots();
  }, [selectedYear, selectedMonth, selectedDay, allScreenshots]);

  const loadInitialData = async () => {
    setLoading(true);
    setError(null);
    try {
      console.log('Loading initial data from API...');
      // Load all screenshots and years
      const [screenshotsData, yearsData] = await Promise.all([
        screenshotApi.getAllScreenshots(),
        screenshotApi.getYears()
      ]);
      
      console.log('API Response - Screenshots:', screenshotsData.length, 'Years:', yearsData);
      setAllScreenshots(screenshotsData);
      setYears(yearsData);
      
      // Set the latest screenshot as current
      if (screenshotsData.length > 0) {
        setCurrentScreenshot(screenshotsData[0]);
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
      const monthsData = await screenshotApi.getMonths(year);
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
      const daysData = await screenshotApi.getDays(year, month);
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

  return (
    <div className="container is-fluid" style={{ padding: '1rem' }}>
      <nav className="navbar is-dark" role="navigation">
        <div className="navbar-brand">
          <div className="navbar-item">
            <h1 className="title is-4 has-text-white">
              <span style={{ marginLeft: '0.5rem', marginRight: '0.5rem' }}>📸</span>
              RSUDP スクリーンショットビューア
            </h1>
          </div>
        </div>
        <div className="navbar-end">
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
      </nav>

      {error && (
        <div className="notification is-danger" style={{ marginTop: '1rem' }}>
          <button className="delete" onClick={() => setError(null)}></button>
          ❌ {error}
        </div>
      )}

      <div className="columns is-desktop" style={{ marginTop: '1rem' }}>
        <div className="column is-4-desktop is-12-tablet">
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
            currentScreenshot={currentScreenshot}
            allImages={filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots}
            onNavigate={handleNavigate}
          />
          
          <div className="box">
            <h2 className="title is-5">📊 統計情報</h2>
            <div className="content">
              <p>全スクリーンショット数: <strong>{allScreenshots.length.toLocaleString()}</strong></p>
              <p>フィルタ後: <strong>{filteredScreenshots.length.toLocaleString()}</strong></p>
            </div>
          </div>

          <FileList
            allImages={filteredScreenshots.length > 0 ? filteredScreenshots : allScreenshots}
            currentImage={currentScreenshot}
            onImageSelect={handleNavigate}
          />
        </div>

        <div className="column is-8-desktop is-12-tablet">
          {loading && !currentScreenshot ? (
            <div className="box has-text-centered">
              <span className="icon is-large">
                <i className="fas fa-spinner fa-pulse fa-3x"></i>
              </span>
              <p className="subtitle" style={{ marginTop: '1rem' }}>⏳ スクリーンショットを読み込み中...</p>
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
    </div>
  );
};

export default App;