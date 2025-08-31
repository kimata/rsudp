import React, { useState, useEffect } from 'react';
import type { StatisticsResponse } from '../types';

interface SignalFilterProps {
  statistics: StatisticsResponse;
  minMaxSignalThreshold?: number;
  onThresholdChange: (threshold: number | undefined) => void;
}

const SignalFilter: React.FC<SignalFilterProps> = ({ statistics, minMaxSignalThreshold, onThresholdChange }) => {
  const [inputValue, setInputValue] = useState('');
  
  // Calculate reasonable step (use 1 for integer steps)
  const step = 1;
  const minValue = Math.floor(statistics.min_signal || 0);
  const maxValue = Math.ceil(statistics.max_signal || 100000);

  useEffect(() => {
    // Initialize with minimum signal value if not set
    if (minMaxSignalThreshold === undefined && statistics.min_signal !== undefined) {
      const initialValue = Math.floor(statistics.min_signal);
      setInputValue(initialValue.toString());
      onThresholdChange(initialValue);
    } else if (minMaxSignalThreshold !== undefined) {
      setInputValue(Math.floor(minMaxSignalThreshold).toString());
    }
  }, [statistics.min_signal]); // Only run when statistics.min_signal changes

  useEffect(() => {
    if (minMaxSignalThreshold !== undefined) {
      setInputValue(Math.floor(minMaxSignalThreshold).toString());
    }
  }, [minMaxSignalThreshold]);


  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    const intValue = parseInt(value, 10);
    setInputValue(intValue.toString());
    onThresholdChange(intValue);
  };

  if (statistics.with_signal === 0) {
    return (
      <div className="box" style={{ minHeight: '120px' }}>
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
            min={minValue}
            max={maxValue}
            step={step}
          />
        </div>
        <p className="help">
          範囲: {minValue.toLocaleString()} - {maxValue.toLocaleString()}
        </p>
      </div>
    </div>
  );
};

export default SignalFilter;