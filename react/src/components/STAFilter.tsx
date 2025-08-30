import React, { useState, useEffect } from 'react';
import type { StatisticsResponse } from '../types';

interface STAFilterProps {
  statistics: StatisticsResponse;
  minStaThreshold?: number;
  onThresholdChange: (threshold: number | undefined) => void;
}

const STAFilter: React.FC<STAFilterProps> = ({ statistics, minStaThreshold, onThresholdChange }) => {
  const [inputValue, setInputValue] = useState('');
  
  // Calculate reasonable step (use 1 for integer steps)
  const step = 1;
  const minValue = Math.floor(statistics.min_sta || 0);
  const maxValue = Math.ceil(statistics.max_sta || 100000);

  useEffect(() => {
    // Initialize with minimum STA value if not set
    if (minStaThreshold === undefined && statistics.min_sta !== undefined) {
      const initialValue = Math.floor(statistics.min_sta);
      setInputValue(initialValue.toString());
      onThresholdChange(initialValue);
    } else if (minStaThreshold !== undefined) {
      setInputValue(Math.floor(minStaThreshold).toString());
    }
  }, [statistics.min_sta]); // Only run when statistics.min_sta changes

  useEffect(() => {
    if (minStaThreshold !== undefined) {
      setInputValue(Math.floor(minStaThreshold).toString());
    }
  }, [minStaThreshold]);


  const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    const intValue = parseInt(value, 10);
    setInputValue(intValue.toString());
    onThresholdChange(intValue);
  };

  if (statistics.with_sta === 0) {
    return (
      <div className="box" style={{ minHeight: '120px' }}>
        <h2 className="title is-5">
          <span className="icon">
            <i className="fas fa-filter"></i>
          </span>
          STAフィルタ
        </h2>
        <div className="content">
          <p className="has-text-grey">STA値を持つ画像がありません</p>
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
        STAフィルタ
      </h2>
      
      <div className="field">
        <label className="label is-small">最小STA値</label>
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

export default STAFilter;