import React, { useState, useEffect, useCallback, memo } from 'react';
import type { StatisticsResponse } from '../types';

interface SignalFilterProps {
  statistics: StatisticsResponse | null;
  minMaxSignalThreshold?: number;
  onThresholdChange: (threshold: number | undefined) => void;
  loading?: boolean;
  isFiltering?: boolean;
}

const SignalFilter: React.FC<SignalFilterProps> = memo(({ statistics, minMaxSignalThreshold, onThresholdChange, loading = false, isFiltering = false }) => {
  const [inputValue, setInputValue] = useState('');
  const [isDragging, setIsDragging] = useState(false);

  // Calculate reasonable step (use 1 for integer steps)
  const step = 1;
  const minValue = Math.floor(statistics?.min_signal || 0);
  const maxValue = Math.ceil(statistics?.max_signal || 100000);

  useEffect(() => {
    // Initialize with minimum signal value if not set
    if (statistics && minMaxSignalThreshold === undefined && statistics.min_signal !== undefined) {
      const initialValue = Math.floor(statistics.min_signal);
      setInputValue(initialValue.toString());
      onThresholdChange(initialValue);
    } else if (minMaxSignalThreshold !== undefined) {
      setInputValue(Math.floor(minMaxSignalThreshold).toString());
    }
  }, [statistics?.min_signal]); // Only run when statistics.min_signal changes

  useEffect(() => {
    if (minMaxSignalThreshold !== undefined && !isDragging) {
      setInputValue(Math.floor(minMaxSignalThreshold).toString());
    }
  }, [minMaxSignalThreshold, isDragging]);

  // ドラッグ中は表示のみ更新（APIは呼ばない）
  const handleSliderChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    const intValue = parseInt(value, 10);
    setInputValue(intValue.toString());
  }, []);

  // ドラッグ開始
  const handleSliderStart = useCallback(() => {
    setIsDragging(true);
  }, []);

  // ドラッグ終了時にのみAPIを呼ぶ
  const handleSliderEnd = useCallback(() => {
    setIsDragging(false);
    const intValue = parseInt(inputValue, 10);
    if (!isNaN(intValue)) {
      onThresholdChange(intValue);
    }
  }, [inputValue, onThresholdChange]);

  // スケルトン表示（ローディング中または統計データがない場合）
  if (loading || !statistics) {
    return (
      <div className="box" style={{ minHeight: '150px' }}>
        <h2 className="title is-5">
          <span className="icon" style={{ marginRight: '0.5rem' }}>
            <i className="fas fa-filter"></i>
          </span>
          最大振幅フィルタ
        </h2>
        <div className="field">
          <label className="label is-small">最大振幅最小値</label>
          <div className="control">
            <div
              className="skeleton-box"
              style={{
                height: '32px',
                backgroundColor: '#f5f5f5',
                borderRadius: '4px',
                animation: 'pulse 1.5s ease-in-out infinite'
              }}
            />
          </div>
        </div>
        <div className="field">
          <div className="control">
            <div
              className="skeleton-box"
              style={{
                height: '20px',
                backgroundColor: '#f5f5f5',
                borderRadius: '4px',
                animation: 'pulse 1.5s ease-in-out infinite'
              }}
            />
          </div>
          <p className="help" style={{ color: '#dbdbdb' }}>読み込み中...</p>
        </div>
      </div>
    );
  }

  if (statistics.with_signal === 0) {
    return (
      <div className="box" style={{ minHeight: '150px' }}>
        <h2 className="title is-5">
          <span className="icon">
            <i className="fas fa-filter"></i>
          </span>
          最大振幅フィルタ
        </h2>
        <div className="content">
          <p className="has-text-grey">信号値を持つ画像がありません</p>
        </div>
      </div>
    );
  }

  return (
    <div className="box" style={{ minHeight: '150px' }}>
      <h2 className="title is-5">
        <span className="icon" style={{ marginRight: '0.5rem' }}>
          <i className="fas fa-filter"></i>
        </span>
        最大振幅フィルタ
        {isFiltering && (
          <span className="icon is-small has-text-info" style={{ marginLeft: '0.5rem' }}>
            <i className="fas fa-spinner fa-pulse"></i>
          </span>
        )}
      </h2>

      <div className="field">
        <label className="label is-small">最大振幅最小値</label>
        <div className="control">
          <input
            className="input is-small has-text-right"
            type="text"
            value={inputValue ? parseInt(inputValue, 10).toLocaleString() : ''}
            readOnly
            placeholder="例: 10,000"
            style={{ textAlign: 'right' }}
          />
        </div>
      </div>

      <div className="field">
        <div className="control">
          <input
            className="slider is-fullwidth is-small is-info"
            style={{ width: '100%' }}
            type="range"
            value={inputValue || minValue}
            onChange={handleSliderChange}
            onMouseDown={handleSliderStart}
            onMouseUp={handleSliderEnd}
            onTouchStart={handleSliderStart}
            onTouchEnd={handleSliderEnd}
            min={minValue}
            max={maxValue}
            step={step}
            disabled={isFiltering}
          />
        </div>
        <p className="help">
          範囲: {minValue.toLocaleString()} - {maxValue.toLocaleString()}
        </p>
      </div>
    </div>
  );
});

export default SignalFilter;
