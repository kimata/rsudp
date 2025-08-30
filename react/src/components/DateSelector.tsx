import React from 'react';

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
}) => {
  const monthNames = [
    '', '1月', '2月', '3月', '4月', '5月', '6月',
    '7月', '8月', '9月', '10月', '11月', '12月'
  ];

  return (
    <>
      {/* 日付フィルタ */}
      <div className="box">
        <h2 className="title is-5">
          <span className="icon" style={{ marginRight: '0.5rem' }}>
            <i className="fas fa-calendar-alt"></i>
          </span>
          日付フィルタ
        </h2>

      {/* Year Selector */}
      <div className="field">
        <label className="label">年</label>
        {years.length > 5 ? (
          <div className="control">
            <div className="select is-fullwidth">
              <select
                value={selectedYear || ''}
                onChange={(e) => onYearChange(e.target.value ? Number(e.target.value) : null)}
                disabled={loading}
              >
                <option value="">全ての年</option>
                {years.map(year => (
                  <option key={year} value={year}>
                    {year}年
                  </option>
                ))}
              </select>
            </div>
          </div>
        ) : (
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
        )}
      </div>

      {/* Month Selector */}
      {selectedYear && months.length > 0 && (
        <div className="field">
          <label className="label">月</label>
          {months.length > 6 ? (
            <div className="control">
              <div className="select is-fullwidth">
                <select
                  value={selectedMonth || ''}
                  onChange={(e) => onMonthChange(e.target.value ? Number(e.target.value) : null)}
                  disabled={loading}
                >
                  <option value="">全ての月</option>
                  {months.map(month => (
                    <option key={month} value={month}>
                      {monthNames[month]}
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ) : (
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
          )}
        </div>
      )}

      {/* Day Selector */}
      {selectedYear && selectedMonth && days.length > 0 && (
        <div className="field">
          <label className="label">日</label>
          {days.length > 10 ? (
            <div className="control">
              <div className="select is-fullwidth">
                <select
                  value={selectedDay || ''}
                  onChange={(e) => onDayChange(e.target.value ? Number(e.target.value) : null)}
                  disabled={loading}
                >
                  <option value="">全ての日</option>
                  {days.map(day => (
                    <option key={day} value={day}>
                      {day}日
                    </option>
                  ))}
                </select>
              </div>
            </div>
          ) : (
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
          )}
        </div>
      )}
      </div>
    </>
  );
};

export default DateSelector;
