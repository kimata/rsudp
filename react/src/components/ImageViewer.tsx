import React, { useState, useEffect, useRef } from 'react';
import type { Screenshot } from '../types';
import { screenshotApi } from '../api';
import { formatScreenshotDateTime } from '../utils/dateTime';
import { useScreenshotNavigation } from '../hooks/useScreenshotNavigation';
import { UI_CONSTANTS } from '../utils/constants';

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
  }, [currentImage, allImages]); // preloadedImagesを依存配列から削除

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
      <div className="box has-text-centered">
        <p className="subtitle">
          <span className="icon" style={{ marginRight: '0.5rem' }}>
            <i className="fas fa-image"></i>
          </span>
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
        style={{
          position: 'fixed',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          width: '100vw',
          height: '100vh',
          backgroundColor: '#000',
          zIndex: 9999,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          cursor: 'pointer'
        }}
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
          style={{
            maxWidth: '95%',
            maxHeight: '95vh',
            width: 'auto',
            height: 'auto',
            objectFit: 'contain',
            cursor: 'zoom-out'
          }}
          onClick={(e) => {
            e.stopPropagation();
            setIsFullscreen(false);
          }}
        />
      </div>
    );
  }

  return (
    <div className="box" onKeyDown={handleKeyDown} tabIndex={0} style={{ minHeight: '600px' }}>
      {/* デスクトップ表示 */}
      <div className="level is-mobile is-hidden-touch" style={{ minHeight: '50px', flexWrap: 'wrap', gap: '0.5rem' }}>
        <div className="level-left">
          <div className="level-item">
            <div>
              <div>
                <span className="heading">
                  <span className="icon" style={{ marginRight: '0.5rem' }}>
                    <i className="fas fa-clock"></i>
                  </span>
                  発生日時
                </span>
                <span className="title is-6" style={{ marginLeft: '0.25rem' }}>
                  {dateTime.formatted}
                </span>
                <span className="subtitle is-7 has-text-grey" style={{ marginLeft: '0.5rem' }}>
                  ({dateTime.relative})
                </span>
              </div>
            </div>
          </div>
        </div>
        <div className="level-right" style={{ flexShrink: 1, minWidth: 0 }}>
          <div className="level-item" style={{ flexShrink: 1, minWidth: 0 }}>
            <div
              className="has-text-right"
              style={{
                minHeight: '28px'
              }}
            >
              {currentImage.sta ? (
                <div
                  style={{
                    display: 'flex',
                    flexWrap: 'wrap',
                    justifyContent: 'flex-end',
                    alignItems: 'center',
                    gap: '0.25rem'
                  }}
                >
                  <span className="icon" style={{ verticalAlign: 'baseline' }}>
                    <i className="fas fa-chart-bar"></i>
                  </span>
                  <span className="tag is-info">
                    最大振幅: {Math.round(currentImage.max_count).toLocaleString()}
                  </span>
                  <span className="tag is-success">
                    STA: {Math.round(currentImage.sta).toLocaleString()}
                  </span>
                  {currentImage.sta_lta_ratio && (
                    <span className="tag is-warning">
                      比率: {currentImage.sta_lta_ratio.toFixed(3)}
                    </span>
                  )}
                </div>
              ) : (
                <span className="has-text-grey-light is-size-7">信号データなし</span>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* モバイル表示 */}
      <div className="is-hidden-desktop" style={{ minHeight: '80px' }}>
        <div style={{ marginBottom: '1rem' }}>
          <span className="heading">
            <span className="icon" style={{ marginRight: '0.5rem' }}>
              <i className="fas fa-clock"></i>
            </span>
            発生日時
          </span>
          <br />
          <span className="title is-6" style={{ marginTop: '0.25rem' }}>
            {dateTime.formatted}
          </span>
          <span className="subtitle is-7 has-text-grey" style={{ marginLeft: '0.5rem' }}>
            ({dateTime.relative})
          </span>
        </div>

        <div style={{ marginBottom: '1rem', minHeight: '28px' }}>
          <div
            style={{
              display: 'flex',
              flexWrap: 'wrap',
              alignItems: 'center',
              gap: '0.5rem'
            }}
          >
            {currentImage.sta ? (
              <>
                <span className="icon" style={{ verticalAlign: 'baseline' }}>
                  <i className="fas fa-chart-bar"></i>
                </span>
                <span className="tag is-info">
                  最大振幅: {Math.round(currentImage.max_count).toLocaleString()}
                </span>
                <span className="tag is-success">
                  STA: {Math.round(currentImage.sta).toLocaleString()}
                </span>
                {currentImage.sta_lta_ratio && (
                  <span className="tag is-warning">
                    比率: {currentImage.sta_lta_ratio.toFixed(3)}
                  </span>
                )}
              </>
            ) : (
              <span className="has-text-grey-light is-size-7">信号データなし</span>
            )}
          </div>
        </div>
      </div>

      <div
        className="image-container"
        style={{
          position: 'relative',
          marginBottom: '1rem',
          minHeight: UI_CONSTANTS.CONTAINER_HEIGHT,
          width: '100%'
        }}
        onTouchStart={handleTouchStart}
        onTouchEnd={handleTouchEnd}
      >
        {(imageLoading || isTransitioning) && (
          <div
            className="has-text-centered"
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              zIndex: 2,
              backgroundColor: 'rgba(255, 255, 255, 0.9)',
              padding: '2rem'
            }}
          >
            <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '300px' }}>
              <div>
                <span className="icon is-large">
                  <i className="fas fa-spinner fa-pulse fa-3x"></i>
                </span>
                <p className="subtitle mt-3">
                  <span className="icon">
                    <i className="fas fa-hourglass-half"></i>
                  </span>
                  画像を読み込み中...
                </p>
              </div>
            </div>
          </div>
        )}

        {imageError && !imageLoading && !isTransitioning && (
          <div className="has-text-centered" style={{ padding: '2rem' }}>
            <div className="is-flex is-justify-content-center is-align-items-center" style={{ minHeight: '300px' }}>
              <div>
                <span className="icon is-large has-text-danger">
                  <i className="fas fa-exclamation-triangle fa-3x"></i>
                </span>
                <p className="subtitle mt-3">
                  <span className="icon" style={{ marginRight: '0.5rem' }}>
                    <i className="fas fa-exclamation-triangle"></i>
                  </span>
                  画像の読み込みに失敗しました
                </p>
                <p className="is-size-7 has-text-grey">ファイル: {currentImage.filename}</p>
                <button
                  className="button is-small is-primary mt-2"
                  onClick={() => {
                    setImageLoading(true);
                    setImageError(false);
                    setIsTransitioning(true);
                  }}
                >
                  <span className="icon">
                    <i className="fas fa-redo"></i>
                  </span>
                  <span>再試行</span>
                </button>
              </div>
            </div>
          </div>
        )}

        <figure
          className="image"
          style={{
            opacity: (imageLoading || isTransitioning) ? 0.3 : 1,
            transition: 'opacity 0.2s ease-in-out',
            minHeight: '300px',
            cursor: 'zoom-in',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: 'auto',
            overflow: 'visible',
            width: '100%'
          }}
          onClick={(e) => toggleFullscreen(e)}
        >
          <img
            ref={currentImageRef}
            src={screenshotApi.getImageUrl(currentImage.filename)}
            alt={currentImage.filename.replace(/\.[^.]*$/, '')}
            style={{
              maxWidth: '100%',
              height: 'auto',
              display: 'block',
              margin: '0 auto',
              objectFit: 'contain',
              touchAction: 'manipulation'
            }}
            onLoad={handleImageLoad}
            onError={handleImageError}
          />
        </figure>
      </div>

      {/* デスクトップ用ナビゲーションボタン */}
      <div className="is-hidden-touch" style={{ marginTop: '1rem', marginBottom: '1rem' }}>
        <div className="field is-grouped is-grouped-centered" style={{ alignItems: 'center' }}>
          <p className="control">
            <button
              className="button is-info"
              onClick={navigatePrevious}
              disabled={!canNavigatePrevious}
            >
              <span className="icon">
                <i className="fas fa-chevron-left"></i>
              </span>
              <span>前へ</span>
            </button>
          </p>
          <p className="control" style={{ display: 'flex', alignItems: 'center' }}>
            <span className="tag is-light" style={{ display: 'inline-flex', alignItems: 'center', height: '2.25em' }}>
              {(currentIndex + 1).toLocaleString()} / {totalCount.toLocaleString()}
            </span>
          </p>
          <p className="control">
            <button
              className="button is-info"
              onClick={navigateNext}
              disabled={!canNavigateNext}
            >
              <span>次へ</span>
              <span className="icon">
                <i className="fas fa-chevron-right"></i>
              </span>
            </button>
          </p>
        </div>
      </div>

      <div className="content is-small has-text-centered" style={{ marginTop: '1rem' }}>
        <p className="is-hidden-touch">
          <span className="icon" style={{ marginRight: '0.5rem' }}>
            <i className="fas fa-keyboard"></i>
          </span>
          矢印キー←→でナビゲーション / Fキーで全画面表示
        </p>
        <p className="is-hidden-desktop">
          <span className="icon" style={{ marginRight: '0.5rem' }}>
            <i className="fas fa-mobile-alt"></i>
          </span>
          左右スワイプでナビゲーション / タップで全画面表示
        </p>
      </div>
    </div>
  );
};

export default ImageViewer;
