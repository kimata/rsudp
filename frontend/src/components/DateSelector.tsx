import React from 'react';
import { Icon } from './Icon';

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

  const buttonBaseClass = "px-2 py-1 text-sm rounded font-medium transition-colors disabled:opacity-50";
  const buttonActiveClass = "bg-teal-500 text-white hover:bg-teal-600";
  const buttonInactiveClass = "bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-600";

  return (
    <>
      {/* 日付フィルタ */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[180px]">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Icon name="calendar" className="size-5" />
          日付フィルタ
        </h2>

      {/* Year Selector */}
      <div className="mb-4 mt-4">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">年</label>
        {loading && years.length === 0 ? (
          <div className="flex flex-wrap gap-2">
            <span
              className={`${buttonBaseClass} ${buttonInactiveClass} min-w-[60px] animate-pulse`}
            >
              読込中
            </span>
          </div>
        ) : years.length > 5 ? (
          <div className="relative">
            <select
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
        ) : (
          <div className="flex flex-wrap gap-2">
            <button
              className={`${buttonBaseClass} ${!selectedYear ? buttonActiveClass : buttonInactiveClass}`}
              onClick={() => onYearChange(null)}
              disabled={loading}
            >
              全て
            </button>
            {years.map(year => (
              <button
                key={year}
                className={`${buttonBaseClass} ${selectedYear === year ? buttonActiveClass : buttonInactiveClass}`}
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
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">月</label>
          {months.length > 6 ? (
            <div className="relative">
              <select
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
          ) : (
            <div className="flex flex-wrap gap-2">
              <button
                className={`${buttonBaseClass} ${!selectedMonth ? buttonActiveClass : buttonInactiveClass}`}
                onClick={() => onMonthChange(null)}
                disabled={loading}
              >
                全て
              </button>
              {months.map(month => (
                <button
                  key={month}
                  className={`${buttonBaseClass} ${selectedMonth === month ? buttonActiveClass : buttonInactiveClass}`}
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
        <div className="mb-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">日</label>
          {days.length > 10 ? (
            <div className="relative">
              <select
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100"
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
          ) : (
            <div className="flex flex-wrap gap-2">
              <button
                className={`${buttonBaseClass} ${!selectedDay ? buttonActiveClass : buttonInactiveClass}`}
                onClick={() => onDayChange(null)}
                disabled={loading}
              >
                全て
              </button>
              {days.map(day => (
                <button
                  key={day}
                  className={`${buttonBaseClass} ${selectedDay === day ? buttonActiveClass : buttonInactiveClass}`}
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
