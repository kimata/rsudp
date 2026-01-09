import React, { useState, useEffect, useCallback, memo } from 'react';
import type { StatisticsResponse } from '../types';
import { Icon } from './Icon';

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

  // 1000 単位でステップ
  const step = 1000;
  // min/max も 1000 単位に丸める（min は切り捨て、max は切り上げ）
  const minValue = Math.floor((statistics?.min_signal || 0) / 1000) * 1000;
  const maxValue = Math.ceil((statistics?.max_signal || 100000) / 1000) * 1000;

  // 統計情報が読み込まれた時に閾値を初期化（1000 単位に丸める）
  useEffect(() => {
    if (statistics?.min_signal !== undefined && minMaxSignalThreshold === undefined) {
      const initialValue = Math.floor(statistics.min_signal / 1000) * 1000;
      setInputValue(initialValue.toString());
      onThresholdChange(initialValue);
    }
  }, [statistics?.min_signal, minMaxSignalThreshold, onThresholdChange]);

  // 閾値が外部から変更された時にinputValueを同期（1000 単位に丸める）
  useEffect(() => {
    if (minMaxSignalThreshold !== undefined && !isDragging) {
      const roundedValue = Math.floor(minMaxSignalThreshold / 1000) * 1000;
      setInputValue(roundedValue.toString());
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
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[150px]">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Icon name="funnel" className="size-5" />
          最大振幅フィルタ
        </h2>
        <div className="mb-4 mt-4">
          <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">最大振幅最小値</label>
          <div className="relative">
            <div
              className="animate-pulse-skeleton h-8 bg-gray-200 dark:bg-gray-700 rounded"
            />
          </div>
        </div>
        <div className="mb-4">
          <div className="relative">
            <div
              className="animate-pulse-skeleton h-5 bg-gray-200 dark:bg-gray-700 rounded"
            />
          </div>
          <p className="mt-1 text-sm text-gray-400">読み込み中...</p>
        </div>
      </div>
    );
  }

  if (statistics.with_signal === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[150px]">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Icon name="funnel" className="size-5" />
          最大振幅フィルタ
        </h2>
        <div className="mt-4">
          <p className="text-gray-500">信号値を持つ画像がありません</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[150px]">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        <Icon name="funnel" className="size-5" />
        最大振幅フィルタ
        {isFiltering && (
          <Icon name="arrow-path" className="size-4 text-blue-500" spin />
        )}
      </h2>

      <div className="mb-4 mt-4">
        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">最大振幅最小値</label>
        <div className="relative">
          <input
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-right"
            type="text"
            value={inputValue ? parseInt(inputValue, 10).toLocaleString() : ''}
            readOnly
            placeholder="例: 10,000"
          />
        </div>
      </div>

      <div className="mb-4">
        <div className="relative">
          <input
            className="w-full"
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
        <p className="mt-1 text-sm text-gray-500">
          範囲: {minValue.toLocaleString()} - {maxValue.toLocaleString()}
        </p>
      </div>
    </div>
  );
});

export default SignalFilter;
