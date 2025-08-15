import React, { useState, useEffect, useRef } from 'react';
import dayjs from 'dayjs';
import 'dayjs/locale/ja';
import relativeTime from 'dayjs/plugin/relativeTime';
import utc from 'dayjs/plugin/utc';
import timezone from 'dayjs/plugin/timezone';
import type { Screenshot } from '../types';
import { screenshotApi } from '../api';

// dayjsの設定
dayjs.extend(relativeTime);
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.locale('ja');

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
  const [imageLoading, setImageLoading] = useState(true);
  const [imageError, setImageError] = useState(false);
  const [preloadedImages, setPreloadedImages] = useState<Map<string, HTMLImageElement>>(new Map());
  const [isTransitioning, setIsTransitioning] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const currentImageRef = useRef<HTMLImageElement>(null);
  const imageContainerRef = useRef<HTMLDivElement>(null);
  const touchStartX = useRef<number>(0);
  const touchStartY = useRef<number>(0);

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
  }, [currentImage, allImages, preloadedImages]);

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
        // 未読み込みの場合は読み込み状態に（初期表示時は transitioningを使わない）
        setImageLoading(true);
        setImageError(false);
        // setIsTransitioning(false); は現在の値を保持
      }
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
    if (Math.abs(deltaX) > 50 && Math.abs(deltaX) > deltaY) {
      const currentIndex = allImages.findIndex(img => img.filename === currentImage.filename);

      if (deltaX > 0 && currentIndex < allImages.length - 1) {
        // 左スワイプ → 次の画像
        setIsTransitioning(true);
        onNavigate(allImages[currentIndex + 1]);
      } else if (deltaX < 0 && currentIndex > 0) {
        // 右スワイプ → 前の画像
        setIsTransitioning(true);
        onNavigate(allImages[currentIndex - 1]);
      }
    }
  };

  // 全画面表示の切り替え
  const toggleFullscreen = () => {
    if (!document.fullscreenElement) {
      if (imageContainerRef.current?.requestFullscreen) {
        imageContainerRef.current.requestFullscreen();
        setIsFullscreen(true);
      }
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  // 全画面状態の監視
  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(!!document.fullscreenElement);
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      const currentIndex = currentImage
        ? allImages.findIndex(img => img.filename === currentImage.filename)
        : -1;
      if (currentIndex > 0) {
        setIsTransitioning(true);
        onNavigate(allImages[currentIndex - 1]);
      }
    } else if (e.key === 'ArrowRight') {
      const currentIndex = currentImage
        ? allImages.findIndex(img => img.filename === currentImage.filename)
        : -1;
      if (currentIndex < allImages.length - 1) {
        setIsTransitioning(true);
        onNavigate(allImages[currentIndex + 1]);
      }
    } else if (e.key === 'Escape' && isFullscreen) {
      document.exitFullscreen();
    } else if (e.key === 'f' || e.key === 'F') {
      toggleFullscreen();
    }
  };

  // ナビゲーションボタンのハンドラー
  const handlePrevious = () => {
    const currentIndex = currentImage
      ? allImages.findIndex(img => img.filename === currentImage.filename)
      : -1;
    if (currentIndex > 0) {
      setIsTransitioning(true);
      onNavigate(allImages[currentIndex - 1]);
    }
  };

  const handleNext = () => {
    const currentIndex = currentImage
      ? allImages.findIndex(img => img.filename === currentImage.filename)
      : -1;
    if (currentIndex < allImages.length - 1) {
      setIsTransitioning(true);
      onNavigate(allImages[currentIndex + 1]);
    }
  };

  if (!currentImage) {
    return (
      <div className="box has-text-centered">
        <p className="subtitle">🖼️ 画像が選択されていません</p>
      </div>
    );
  }

  const formatDateTime = (screenshot: Screenshot) => {
    const utcDate = dayjs.utc(screenshot.timestamp);
    const localDate = utcDate.local();
    const now = dayjs();
    const relativeTimeStr = localDate.from(now);

    // 2005年2月1日 01時02分34秒 の形式
    const formatted = localDate.format('YYYY年M月D日 HH時mm分ss秒');

    return {
      formatted,
      relative: relativeTimeStr
    };
  };

  const dateTime = formatDateTime(currentImage);

  return (
    <div className="box" onKeyDown={handleKeyDown} tabIndex={0}>
      <div className="level is-mobile">
        <div className="level-left">
          <div className="level-item">
            <div>
              <div>
                <span className="heading">🕰️ 発生日時</span>
                <br className="is-hidden-desktop" />
                <span className="title is-6" style={{ marginLeft: '0.25rem' }}>
                  {dateTime.formatted}
                </span>
                <br className="is-hidden-tablet" />
                <span className="subtitle is-7 has-text-grey" style={{ marginLeft: '0.25rem' }}>
                  ({dateTime.relative})
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div
        ref={imageContainerRef}
        className="image-container"
        style={{
          position: 'relative',
          marginBottom: '1rem',
          minHeight: '400px',
          backgroundColor: isFullscreen ? '#000' : 'transparent'
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
                <p className="subtitle mt-3">⏳ 画像を読み込み中...</p>
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
                <p className="subtitle mt-3">❌ 画像の読み込みに失敗しました</p>
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
            cursor: 'pointer',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            height: isFullscreen ? '100vh' : 'auto',
            overflow: isFullscreen ? 'auto' : 'visible'
          }}
          onClick={toggleFullscreen}
        >
          <img
            ref={currentImageRef}
            src={screenshotApi.getImageUrl(currentImage.filename)}
            alt={currentImage.filename}
            style={{
              maxWidth: isFullscreen ? '95%' : '100%',
              maxHeight: isFullscreen ? '95vh' : 'auto',
              width: 'auto',
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

      {/* モバイル向けナビゲーションボタン */}
      <div className="is-hidden-desktop" style={{ marginTop: '1rem', marginBottom: '1rem' }}>
        <div className="buttons is-centered">
          <button
            className="button is-primary"
            onClick={handlePrevious}
            disabled={allImages.findIndex(img => img.filename === currentImage.filename) === 0}
          >
            <span className="icon">
              <i className="fas fa-chevron-left"></i>
            </span>
            <span>前へ</span>
          </button>
          <button
            className="button is-primary"
            onClick={handleNext}
            disabled={allImages.findIndex(img => img.filename === currentImage.filename) === allImages.length - 1}
          >
            <span>次へ</span>
            <span className="icon">
              <i className="fas fa-chevron-right"></i>
            </span>
          </button>
        </div>
      </div>

      <div className="content is-small has-text-centered" style={{ marginTop: '1rem' }}>
        <p className="is-hidden-touch">🎹 矢印キー←→でナビゲーション / Fキーで全画面表示</p>
        <p className="is-hidden-desktop">📱 左右スワイプでナビゲーション / タップで全画面表示</p>
      </div>
    </div>
  );
};

export default ImageViewer;
