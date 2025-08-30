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

  const { navigateNext, navigatePrevious } = useScreenshotNavigation(
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

  // 隣接する画像を事前読み込み
  useEffect(() => {
    if (!currentImage || allImages.length === 0) return;

    const currentIndex = allImages.findIndex(img => img.filename === currentImage.filename);
    const imagesToPreload: string[] = [];

    // 前後の画像を事前読み込み対象に追加
    if (currentIndex > 0) {
      imagesToPreload.push(allImages[currentIndex - 1].filename);
    }
    if (currentIndex < allImages.length - 1) {
      imagesToPreload.push(allImages[currentIndex + 1].filename);
    }

    // 事前読み込み実行
    imagesToPreload.forEach(async (filename) => {
      if (!preloadedImages.has(filename)) {
        try {
          const img = await preloadImage(filename);
          setPreloadedImages(prev => new Map(prev).set(filename, img));
        } catch (error) {
          console.warn('Failed to preload image:', filename, error);
        }
      }
    });
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
      if (deltaX > 0) {
        // 左スワイプ → 次の画像
        setIsTransitioning(true);
        navigateNext();
      } else if (deltaX < 0) {
        // 右スワイプ → 前の画像
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
    if (e.key === 'ArrowLeft') {
      setIsTransitioning(true);
      navigatePrevious();
    } else if (e.key === 'ArrowRight') {
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
    <div className="box" onKeyDown={handleKeyDown} tabIndex={0}>
      <div className="level is-mobile">
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
                <br className="is-hidden-desktop" />
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
        {currentImage.sta && (
          <div className="level-right">
            <div className="level-item">
              <div className="has-text-right">
                <br className="is-hidden-desktop" />
                <span className="icon" style={{ marginRight: '0.25rem', verticalAlign: 'baseline' }}>
                  <i className="fas fa-chart-bar"></i>
                </span>
                <span className="tag is-info" style={{ marginLeft: '0.25rem' }}>
                  STA: {Math.round(currentImage.sta).toLocaleString()}
                </span>
                {currentImage.sta_lta_ratio && (
                  <span className="tag is-warning" style={{ marginLeft: '0.25rem' }}>
                    比率: {currentImage.sta_lta_ratio.toFixed(3)}
                  </span>
                )}
              </div>
            </div>
          </div>
        )}
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

      <div className="content is-small has-text-centered" style={{ marginTop: '1rem' }}>
        <p className="is-hidden-touch">🎹 矢印キー←→でナビゲーション / Fキーで全画面表示</p>
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
