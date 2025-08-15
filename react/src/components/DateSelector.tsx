import React from 'react';
import type { Screenshot } from '../types';

interface DateSelectorProps {
  years: number[];
  months: number[];
  days: number[];
  selectedYear: number | null;
  selectedMonth: number | null;
  selectedDay: number | null;
  onYearChange: (year: number | null) => void;
  onMonthChange: (month: number | null) => void;
  onDayChange: (day: number | null) => void;
  loading: boolean;
  currentScreenshot: Screenshot | null;
  allImages: Screenshot[];
  onNavigate: (screenshot: Screenshot) => void;
}

const DateSelector: React.FC<DateSelectorProps> = ({
  years,
  months,
  days,
  selectedYear,
  selectedMonth,
  selectedDay,
  onYearChange,
  onMonthChange,
  onDayChange,
  loading,
  currentScreenshot,
  allImages,
  onNavigate,
}) => {
  const monthNames = [
    '', '1月', '2月', '3月', '4月', '5月', '6月',
    '7月', '8月', '9月', '10月', '11月', '12月'
  ];

  const currentIndex = currentScreenshot
    ? allImages.findIndex(img => img.filename === currentScreenshot.filename)
    : -1;

  const handlePrevious = () => {
    if (currentIndex > 0) {
      onNavigate(allImages[currentIndex - 1]);
    }
  };

  const handleNext = () => {
    if (currentIndex < allImages.length - 1) {
      onNavigate(allImages[currentIndex + 1]);
    }
  };

  return (
    <>
      {/* ナビゲーション */}
      <div className="box">
        <h2 className="title is-5">🎮 ナビゲーション</h2>
        <div className="field is-grouped is-grouped-centered">
          <p className="control">
            <button
              className="button is-info"
              onClick={handlePrevious}
              disabled={currentIndex <= 0 || loading}
            >
              <span className="icon">
                <i className="fas fa-chevron-left"></i>
              </span>
              <span>前へ</span>
            </button>
          </p>
          <p className="control">
            <span className="tag is-light">
              {(currentIndex + 1).toLocaleString()} / {allImages.length.toLocaleString()}
            </span>
          </p>
          <p className="control">
            <button
              className="button is-info"
              onClick={handleNext}
              disabled={currentIndex >= allImages.length - 1 || loading}
            >
              <span>次へ</span>
              <span className="icon">
                <i className="fas fa-chevron-right"></i>
              </span>
            </button>
          </p>
        </div>
      </div>

      {/* 日付フィルタ */}
      <div className="box">
        <h2 className="title is-5">📅 日付フィルタ</h2>

      {/* Year Selector */}
      <div className="field">
        <label className="label">年</label>
        <div className="buttons">
          <button
            className={`button is-small ${!selectedYear ? 'is-primary' : ''}`}
            onClick={() => onYearChange(null)}
            disabled={loading}
          >
            全て
          </button>
          {years.map(year => (
            <button
              key={year}
              className={`button is-small ${selectedYear === year ? 'is-primary' : ''}`}
              onClick={() => onYearChange(year)}
              disabled={loading}
            >
              {year}
            </button>
          ))}
        </div>
      </div>

      {/* Month Selector */}
      {selectedYear && months.length > 0 && (
        <div className="field">
          <label className="label">月</label>
          <div className="buttons">
            <button
              className={`button is-small ${!selectedMonth ? 'is-primary' : ''}`}
              onClick={() => onMonthChange(null)}
              disabled={loading}
            >
              全て
            </button>
            {months.map(month => (
              <button
                key={month}
                className={`button is-small ${selectedMonth === month ? 'is-primary' : ''}`}
                onClick={() => onMonthChange(month)}
                disabled={loading}
              >
                {monthNames[month]}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Day Selector */}
      {selectedYear && selectedMonth && days.length > 0 && (
        <div className="field">
          <label className="label">日</label>
          <div className="buttons are-small">
            <button
              className={`button is-small ${!selectedDay ? 'is-primary' : ''}`}
              onClick={() => onDayChange(null)}
              disabled={loading}
            >
              全て
            </button>
            {days.map(day => (
              <button
                key={day}
                className={`button is-small ${selectedDay === day ? 'is-primary' : ''}`}
                onClick={() => onDayChange(day)}
                disabled={loading}
              >
                {day}
              </button>
            ))}
          </div>
        </div>
      )}
      </div>
    </>
  );
};

export default DateSelector;
