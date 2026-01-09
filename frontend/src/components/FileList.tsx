import React, { useEffect, useRef, memo, useCallback } from 'react';
import type { Screenshot } from '../types';
import { formatScreenshotDateTime } from '../utils/dateTime';
import { TIMEOUTS } from '../utils/constants';
import { Icon } from './Icon';

interface FileListProps {
  allImages: Screenshot[];
  currentImage: Screenshot | null;
  onImageSelect: (screenshot: Screenshot) => void;
  loading?: boolean;
  /** ユーザーが明示的に画像を選択した時のみtrue（フィルタ変更時はfalse） */
  shouldScrollToCurrentImage?: boolean;
  /** フィルタ適用中フラグ */
  isFiltering?: boolean;
}

const FileList: React.FC<FileListProps> = memo(({
  allImages,
  currentImage,
  onImageSelect,
  loading = false,
  shouldScrollToCurrentImage = false,
  isFiltering = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const currentItemRef = useRef<HTMLDivElement>(null);
  const hasInitialScrolled = useRef(false);

  // スクロール関数を定義
  const scrollToCurrentItem = useCallback((immediate = false) => {
    if (!currentImage || !containerRef.current) return;

    const timer = setTimeout(() => {
      const container = containerRef.current;
      if (!container) return;

      // 現在の画像のインデックスを取得
      const currentIndex = allImages.findIndex(img => img.filename === currentImage.filename);
      if (currentIndex === -1) return;

      // 実際のDOM要素から高さを取得
      const firstItem = container.querySelector('.file-list-item') as HTMLElement;
      const itemHeight = firstItem ? firstItem.offsetHeight : 60;

      const targetScrollTop = currentIndex * itemHeight;

      // コンテナの中央に来るように調整
      const containerHeight = container.clientHeight;
      const centeredScrollTop = targetScrollTop - (containerHeight / 2) + (itemHeight / 2);

      container.scrollTo({
        top: Math.max(0, centeredScrollTop),
        behavior: immediate ? 'auto' : 'smooth'
      });
    }, immediate ? 0 : TIMEOUTS.PRELOAD_DELAY);

    return () => clearTimeout(timer);
  }, [allImages, currentImage]);

  // ユーザーが明示的に画像を選択した時のみスクロール
  useEffect(() => {
    if (shouldScrollToCurrentImage && currentImage && allImages.length > 0) {
      scrollToCurrentItem();
    }
  }, [shouldScrollToCurrentImage, currentImage, allImages.length, scrollToCurrentItem]);

  // 初回レンダリング時の自動スクロール（1回のみ）
  useEffect(() => {
    if (!hasInitialScrolled.current && currentImage && allImages.length > 0) {
      hasInitialScrolled.current = true;
      // 初回は即座にスクロール（アニメーションなし）
      const timer = setTimeout(() => {
        scrollToCurrentItem(true);
      }, TIMEOUTS.SCROLL_DELAY);

      return () => clearTimeout(timer);
    }
  }, [currentImage, allImages.length, scrollToCurrentItem]);

  const formatFileDateTime = (screenshot: Screenshot) => {
    const dateTime = formatScreenshotDateTime(screenshot);
    return {
      formatted: dateTime.compact,
      relative: dateTime.relative
    };
  };

  const getEventTypeIconName = (prefix: string): "globe" | "exclamation-triangle" | "camera" => {
    switch (prefix.toUpperCase()) {
      case 'SHAKE':
        return 'globe';
      case 'ALERT':
      case 'WARNING':
        return 'exclamation-triangle';
      default:
        return 'camera';
    }
  };

  // ローディング中の表示
  if (loading && allImages.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Icon name="list-bullet" className="size-5" />
          ファイル一覧
        </h2>
        <div
          className="h-[400px] border border-gray-300 dark:border-gray-600 rounded flex items-center justify-center mt-4"
        >
          <div className="text-center">
            <Icon name="arrow-path" className="size-8 text-blue-500" spin />
            <p className="text-gray-600 dark:text-gray-400 mt-3 flex items-center justify-center gap-2">
              <Icon name="list-bullet" className="size-5" />
              ファイル一覧を読み込み中...
            </p>
          </div>
        </div>
        <div className="text-center text-gray-500 mt-2 text-xs flex items-center justify-center gap-1">
          <Icon name="chart-bar" className="size-4" />
          読み込み中...
        </div>
      </div>
    );
  }

  if (allImages.length === 0) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5">
        <h2 className="text-lg font-semibold flex items-center gap-2">
          <Icon name="list-bullet" className="size-5" />
          ファイル一覧
        </h2>
        <div
          className="h-[400px] border border-gray-300 dark:border-gray-600 rounded flex items-center justify-center mt-4"
        >
          <div className="text-center text-gray-500">
            <p>ファイルがありません</p>
          </div>
        </div>
        <div className="text-center text-gray-500 mt-2 text-xs flex items-center justify-center gap-1">
          <Icon name="chart-bar" className="size-4" />
          0 件のファイル
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5">
      <h2 className="text-lg font-semibold flex items-center gap-2">
        <Icon name="list-bullet" className="size-5" />
        ファイル一覧
        {isFiltering && (
          <Icon name="arrow-path" className="size-4 text-blue-500" spin />
        )}
      </h2>
      <div className="relative mt-4">
        {/* フィルタ適用中のオーバーレイ */}
        {isFiltering && (
          <div
            className="absolute inset-0 bg-white/70 dark:bg-gray-800/70 z-10 flex items-center justify-center rounded"
          >
            <div className="text-center">
              <Icon name="arrow-path" className="size-6 text-blue-500" spin />
              <p className="text-sm text-gray-500 mt-2">フィルタ適用中...</p>
            </div>
          </div>
        )}
        <div
          ref={containerRef}
          className={`file-list-container h-[400px] overflow-y-auto border border-gray-300 dark:border-gray-600 rounded custom-scrollbar transition-opacity duration-200 ${isFiltering ? 'opacity-50' : 'opacity-100'}`}
        >
        {allImages.map((image, index) => {
          const isCurrentImage = currentImage?.filename === image.filename;
          const dateTime = formatFileDateTime(image);

          return (
            <div
              key={image.filename}
              ref={(el) => {
                if (isCurrentImage) {
                  currentItemRef.current = el;
                }
              }}
              className={`file-list-item p-2 border-b border-gray-100 dark:border-gray-700 cursor-pointer transition-all duration-200 ${
                isCurrentImage
                  ? 'bg-blue-500 text-white'
                  : 'hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
              onClick={() => onImageSelect(image)}
            >
              <div className="flex items-center">
                <span className="mr-2">
                  <Icon name={getEventTypeIconName(image.prefix)} className="size-4" />
                </span>
                <div className="flex-1">
                  <div className="flex justify-between items-center">
                    <div>
                      <span className="font-semibold text-sm">
                        {dateTime.formatted}
                      </span>
                      <span
                        className={`text-xs ml-1 ${
                          isCurrentImage ? 'text-white/80' : 'text-gray-500'
                        }`}
                      >
                        ({dateTime.relative})
                      </span>
                    </div>
                    <span
                      className={`inline-flex items-center px-1.5 py-0.5 text-xs rounded ${
                        isCurrentImage
                          ? 'bg-white/20 text-white'
                          : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                      }`}
                    >
                      #{index + 1}
                    </span>
                  </div>
                  <div className={`text-xs mt-1 ${isCurrentImage ? 'text-white/80' : 'text-gray-500'}`}>
                    {image.filename}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
        </div>
      </div>
      <div className="text-center text-gray-500 mt-2 text-xs flex items-center justify-center gap-1">
        <Icon name="chart-bar" className="size-4" />
        {allImages.length.toLocaleString()} 件のファイル
      </div>
    </div>
  );
});

export default FileList;
