import React, { useState, useEffect, useRef } from 'react';
import type { Screenshot } from '../types';
import { screenshotApi } from '../api';
import { formatScreenshotDateTime } from '../utils/dateTime';
import { useScreenshotNavigation } from '../hooks/useScreenshotNavigation';
import { UI_CONSTANTS } from '../utils/constants';
import { Icon } from './Icon';

interface ImageViewerProps {
  currentImage: Screenshot | null;
  allImages: Screenshot[];
  onNavigate: (screenshot: Screenshot) => void;
}

const ImageViewer: React.FC<ImageViewerProps> = ({
  currentImage,
  allImages,
  onNavigate,
}) => {
  const [imageLoading, setImageLoading] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [preloadedImages, setPreloadedImages] = useState<Map<string, HTMLImageElement>>(new Map());
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const currentImageRef = useRef<HTMLImageElement>(null);
  const touchStartX = useRef<number>(0);
  const touchStartY = useRef<number>(0);

  const {
    currentIndex,
    navigateNext,
    navigatePrevious,
    canNavigateNext,
    canNavigatePrevious,
    totalCount
  } = useScreenshotNavigation(
    currentImage,
    allImages,
    onNavigate
  );

  // 画像の事前読み込み
  const preloadImage = (filename: string): Promise<HTMLImageElement> => {
    return new Promise((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = reject;
      img.src = screenshotApi.getImageUrl(filename);
    });
  };

  // 隣接する画像を事前読み込み（前後5枚）
  useEffect(() => {
    if (!currentImage || allImages.length === 0) return;

    const currentIndex = allImages.findIndex(img => img.filename === currentImage.filename);
    const imagesToPreload: string[] = [];
    const preloadRange = 5; // 前後5枚を先読み

    // 前の画像を事前読み込み対象に追加（最大5枚）
    for (let i = 1; i <= preloadRange; i++) {
      const prevIndex = currentIndex - i;
      if (prevIndex >= 0) {
        imagesToPreload.push(allImages[prevIndex].filename);
      }
    }

    // 後の画像を事前読み込み対象に追加（最大5枚）
    for (let i = 1; i <= preloadRange; i++) {
      const nextIndex = currentIndex + i;
      if (nextIndex < allImages.length) {
        imagesToPreload.push(allImages[nextIndex].filename);
      }
    }

    // 事前読み込み実行（近い画像から優先的に読み込み）
    imagesToPreload.forEach(async (filename, index) => {
      if (!preloadedImages.has(filename)) {
        // 近い画像ほど優先度を高くするため、短い遅延を設定
        const delay = Math.floor(index / 2) * 25; // 0ms, 0ms, 25ms, 25ms, 50ms, 50ms, 75ms...

        setTimeout(async () => {
          try {
            const img = await preloadImage(filename);
            setPreloadedImages(prev => new Map(prev).set(filename, img));
          } catch (error) {
            console.warn('Failed to preload image:', filename, error);
          }
        }, delay);
      }
    });

    // 古いキャッシュをクリーンアップ（メモリ管理）
    const maxCacheSize = 20; // 最大20枚までキャッシュ
    if (preloadedImages.size > maxCacheSize) {
      const keepIndices = new Set<number>();

      // 現在の画像の前後10枚のインデックスを保持
      for (let i = -10; i <= 10; i++) {
        const idx = currentIndex + i;
        if (idx >= 0 && idx < allImages.length) {
          keepIndices.add(idx);
        }
      }

      // 保持対象外の画像をキャッシュから削除
      setPreloadedImages(prev => {
        const newCache = new Map(prev);
        for (const [filename] of newCache) {
          const idx = allImages.findIndex(img => img.filename === filename);
          if (!keepIndices.has(idx)) {
            newCache.delete(filename);
          }
        }
        return newCache;
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preloadedImagesを依存配列に含めると無限ループになる
  }, [currentImage, allImages]);

  const handleImageLoad = () => {
    setImageLoading(false);
    setImageError(false);
    setIsTransitioning(false);
  };

  const handleImageError = () => {
    setImageLoading(false);
    setImageError(true);
    setIsTransitioning(false);
  };

  // 現在の画像が変更された時の処理
  useEffect(() => {
    if (currentImage) {
      // 事前読み込み済みの場合は即座に表示
      if (preloadedImages.has(currentImage.filename)) {
        setImageLoading(false);
        setImageError(false);
        setIsTransitioning(false);
      } else {
        // 未読み込みの場合は読み込み状態に
        setImageLoading(true);
        setImageError(false);
        setIsTransitioning(false);
      }
    } else {
      // currentImageがnullの場合はローディング状態をリセット
      setImageLoading(false);
      setImageError(false);
      setIsTransitioning(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- preloadedImagesの変更では再実行不要
  }, [currentImage]);

  // 画像要素がマウントされた後、キャッシュ済みの画像の場合はすぐに表示
  useEffect(() => {
    if (currentImageRef.current && currentImageRef.current.complete && currentImage) {
      // 画像が既に読み込まれている（キャッシュされている）場合
      handleImageLoad();
    }
  }, [currentImage]);

  // タッチ操作のハンドラー
  const handleTouchStart = (e: React.TouchEvent) => {
    touchStartX.current = e.touches[0].clientX;
    touchStartY.current = e.touches[0].clientY;
  };

  const handleTouchEnd = (e: React.TouchEvent) => {
    if (!currentImage) return;

    const touchEndX = e.changedTouches[0].clientX;
    const touchEndY = e.changedTouches[0].clientY;
    const deltaX = touchStartX.current - touchEndX;
    const deltaY = Math.abs(touchStartY.current - touchEndY);

    // 横方向のスワイプが縦方向より大きい場合のみ処理
    if (Math.abs(deltaX) > UI_CONSTANTS.SWIPE_THRESHOLD && Math.abs(deltaX) > deltaY) {
      if (deltaX > 0 && canNavigateNext) {
        // 左スワイプ → 次の画像（次の画像が存在する場合のみ）
        setIsTransitioning(true);
        navigateNext();
      } else if (deltaX < 0 && canNavigatePrevious) {
        // 右スワイプ → 前の画像（前の画像が存在する場合のみ）
        setIsTransitioning(true);
        navigatePrevious();
      }
    }
  };

  // 全画面表示の切り替え（シンプルな実装に変更）
  const toggleFullscreen = (e?: React.MouseEvent) => {
    e?.stopPropagation();
    setIsFullscreen(!isFullscreen);
  };

  // ESCキーで全画面解除
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isFullscreen) {
        setIsFullscreen(false);
      }
    };

    if (isFullscreen) {
      document.addEventListener('keydown', handleEsc);
      return () => document.removeEventListener('keydown', handleEsc);
    }
  }, [isFullscreen]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft' && canNavigatePrevious) {
      setIsTransitioning(true);
      navigatePrevious();
    } else if (e.key === 'ArrowRight' && canNavigateNext) {
      setIsTransitioning(true);
      navigateNext();
    } else if (e.key === 'Escape' && isFullscreen) {
      setIsFullscreen(false);
    } else if (e.key === 'f' || e.key === 'F') {
      toggleFullscreen();
    }
  };


  if (!currentImage) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 text-center">
        <p className="text-gray-600 dark:text-gray-400 flex items-center justify-center gap-2">
          <Icon name="photo" className="size-5" />
          画像が選択されていません
        </p>
      </div>
    );
  }

  const dateTime = formatScreenshotDateTime(currentImage);

  // 全画面表示時は別の構造で表示
  if (isFullscreen) {
    return (
      <div
        className="fixed inset-0 w-screen h-screen bg-black z-[9999] flex items-center justify-center cursor-pointer"
        onKeyDown={handleKeyDown}
        onClick={(e) => {
          // 背景クリックで全画面解除
          if (e.target === e.currentTarget) {
            setIsFullscreen(false);
          }
        }}
        tabIndex={0}
      >
        <img
          src={screenshotApi.getImageUrl(currentImage.filename)}
          alt={currentImage.filename.replace(/\.[^.]*$/, '')}
          className="max-w-[95%] max-h-[95vh] w-auto h-auto object-contain cursor-zoom-out"
          onClick={(e) => {
            e.stopPropagation();
            setIsFullscreen(false);
          }}
        />
      </div>
    );
  }

  // Format earthquake datetime
  const formatEarthquakeDateTime = (isoString: string): string => {
    const date = new Date(isoString);
    const month = date.getMonth() + 1;
    const day = date.getDate();
    const hours = date.getHours().toString().padStart(2, '0');
    const minutes = date.getMinutes().toString().padStart(2, '0');
    return `${month}/${day} ${hours}:${minutes}`;
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md p-5 min-h-[600px]" onKeyDown={handleKeyDown} tabIndex={0}>
      {/* デスクトップ表示 */}
      <div className="hidden lg:flex items-center justify-between min-h-[50px] flex-wrap gap-2 mb-2">
        <div className="flex items-center">
          <div>
            <div>
              <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 flex items-center gap-2">
                <Icon name="clock" className="size-4" />
                発生日時
              </span>
              <span className="text-base font-semibold ml-1">
                {dateTime.formatted}
              </span>
              <span className="text-xs text-gray-500 ml-2">
                ({dateTime.relative})
              </span>
              {currentImage.earthquake && (
                <span
                  className="inline-flex items-center px-2 py-1 text-sm rounded bg-indigo-100 dark:bg-indigo-900 text-indigo-800 dark:text-indigo-200 ml-3 whitespace-nowrap"
                >
                  <Icon name="globe" className="size-4 mr-1" />
                  近傍で発生した地震: {formatEarthquakeDateTime(currentImage.earthquake.detected_at)} {currentImage.earthquake.epicenter_name} M{currentImage.earthquake.magnitude}
                </span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center flex-shrink min-w-0">
          <div
            className="text-right min-h-[28px]"
          >
            {currentImage.sta ? (
              <div
                className="flex flex-wrap justify-end items-center gap-1"
              >
                <Icon name="chart-bar" className="size-5" />
                <span className="inline-flex items-center px-2 py-1 text-sm rounded bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">
                  最大振幅: {Math.round(currentImage.max_count).toLocaleString()}
                </span>
                <span className="inline-flex items-center px-2 py-1 text-sm rounded bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">
                  STA: {Math.round(currentImage.sta).toLocaleString()}
                </span>
                {currentImage.sta_lta_ratio && (
                  <span className="inline-flex items-center px-2 py-1 text-sm rounded bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200">
                    比率: {currentImage.sta_lta_ratio.toFixed(3)}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-gray-400 text-sm">信号データなし</span>
            )}
          </div>
        </div>
      </div>

      {/* モバイル表示 */}
      <div className="lg:hidden min-h-[80px]">
        <div className="mb-4">
          <span className="text-xs font-semibold uppercase tracking-wide text-gray-500 flex items-center gap-2">
            <Icon name="clock" className="size-4" />
            発生日時
          </span>
          <br />
          <span className="text-base font-semibold mt-1">
            {dateTime.formatted}
          </span>
          <span className="text-xs text-gray-500 ml-2">
            ({dateTime.relative})
          </span>
          {currentImage.earthquake && (
            <div className="mt-2">
              <span
                className="inline-flex items-center px-2 py-1 text-sm rounded bg-indigo-100 dark:bg-indigo-900 text-indigo-800 dark:text-indigo-200 whitespace-nowrap"
              >
                <Icon name="globe" className="size-4 mr-1" />
                近傍で発生した地震: {formatEarthquakeDateTime(currentImage.earthquake.detected_at)} {currentImage.earthquake.epicenter_name} M{currentImage.earthquake.magnitude}
              </span>
            </div>
          )}
        </div>

        <div className="mb-4 min-h-[28px]">
          <div
            className="flex flex-wrap items-center gap-2"
          >
            {currentImage.sta ? (
              <>
                <Icon name="chart-bar" className="size-5" />
                <span className="inline-flex items-center px-2 py-1 text-sm rounded bg-blue-100 dark:bg-blue-900 text-blue-800 dark:text-blue-200">
                  最大振幅: {Math.round(currentImage.max_count).toLocaleString()}
                </span>
                <span className="inline-flex items-center px-2 py-1 text-sm rounded bg-green-100 dark:bg-green-900 text-green-800 dark:text-green-200">
                  STA: {Math.round(currentImage.sta).toLocaleString()}
                </span>
                {currentImage.sta_lta_ratio && (
                  <span className="inline-flex items-center px-2 py-1 text-sm rounded bg-yellow-100 dark:bg-yellow-900 text-yellow-800 dark:text-yellow-200">
                    比率: {currentImage.sta_lta_ratio.toFixed(3)}
                  </span>
                )}
              </>
            ) : (
              <span className="text-gray-400 text-sm">信号データなし</span>
            )}
          </div>
        </div>
      </div>

      <div
        className="image-container relative mb-4 w-full"
        style={{ minHeight: UI_CONSTANTS.CONTAINER_HEIGHT }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {(imageLoading || isTransitioning) && (
          <div
            className="absolute inset-0 z-10 bg-white/90 dark:bg-gray-800/90 p-8 text-center"
          >
            <div className="flex justify-center items-center min-h-[300px]">
              <div>
                <Icon name="arrow-path" className="size-12 text-blue-500" spin />
                <p className="text-gray-600 dark:text-gray-400 mt-3 flex items-center justify-center gap-2">
                  <Icon name="clock" className="size-5" />
                  画像を読み込み中...
                </p>
              </div>
            </div>
          </div>
        )}

        {imageError && !imageLoading && !isTransitioning && (
          <div className="text-center p-8">
            <div className="flex justify-center items-center min-h-[300px]">
              <div>
                <Icon name="exclamation-triangle" className="size-12 text-red-500" />
                <p className="text-gray-600 dark:text-gray-400 mt-3 flex items-center justify-center gap-2">
                  <Icon name="exclamation-triangle" className="size-5" />
                  画像の読み込みに失敗しました
                </p>
                <p className="text-sm text-gray-500 mt-1">ファイル: {currentImage.filename}</p>
                <button
                  className="mt-2 px-4 py-2 text-sm rounded bg-teal-500 text-white hover:bg-teal-600 transition-colors flex items-center gap-2 mx-auto"
                  onClick={() => {
                    setImageLoading(true);
                    setImageError(false);
                    setIsTransitioning(true);
                  }}
                >
                  <Icon name="arrow-path" className="size-4" />
                  <span>再試行</span>
                </button>
              </div>
            </div>
          </div>
        )}

        <figure
          className={`min-h-[300px] cursor-zoom-in flex items-center justify-center h-auto overflow-visible w-full transition-opacity duration-200 ${
            (imageLoading || isTransitioning) ? 'opacity-30' : 'opacity-100'
          }`}
          onClick={(e) => toggleFullscreen(e)}
        >
          <img
            ref={currentImageRef}
            src={screenshotApi.getImageUrl(currentImage.filename)}
            alt={currentImage.filename.replace(/\.[^.]*$/, '')}
            className="max-w-full h-auto block mx-auto object-contain"
            style={{ touchAction: 'manipulation' }}
            onLoad={handleImageLoad}
            onError={handleImageError}
          />
        </figure>
      </div>

      {/* デスクトップ用ナビゲーションボタン */}
      <div className="hidden lg:block mt-4 mb-4">
        <div className="flex justify-center items-center gap-4">
          <button
            className="px-4 py-2 rounded bg-blue-500 text-white hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            onClick={navigatePrevious}
            disabled={!canNavigatePrevious}
          >
            <Icon name="chevron-left" className="size-5" />
            <span>前へ</span>
          </button>
          <span className="inline-flex items-center px-3 py-1 text-sm rounded bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 h-9">
            {(currentIndex + 1).toLocaleString()} / {totalCount.toLocaleString()}
          </span>
          <button
            className="px-4 py-2 rounded bg-blue-500 text-white hover:bg-blue-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
            onClick={navigateNext}
            disabled={!canNavigateNext}
          >
            <span>次へ</span>
            <Icon name="chevron-right" className="size-5" />
          </button>
        </div>
      </div>

      <div className="text-sm text-center text-gray-500 mt-4">
        <p className="hidden lg:flex items-center justify-center gap-2">
          <Icon name="command-line" className="size-4" />
          矢印キー←→でナビゲーション / Fキーで全画面表示
        </p>
        <p className="lg:hidden flex items-center justify-center gap-2">
          <Icon name="device-phone-mobile" className="size-4" />
          左右スワイプでナビゲーション / タップで全画面表示
        </p>
      </div>
    </div>
  );
};

export default ImageViewer;
