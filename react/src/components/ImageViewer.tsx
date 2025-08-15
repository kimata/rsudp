import React, { useState } from 'react';
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

  const handleImageLoad = () => {
    setImageLoading(false);
    setImageError(false);
  };

  const handleImageError = () => {
    setImageLoading(false);
    setImageError(true);
  };

  // Reset loading state when current image changes
  React.useEffect(() => {
    if (currentImage) {
      setImageLoading(true);
      setImageError(false);
    }
  }, [currentImage]);

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowLeft') {
      const currentIndex = currentImage
        ? allImages.findIndex(img => img.filename === currentImage.filename)
        : -1;
      if (currentIndex > 0) {
        onNavigate(allImages[currentIndex - 1]);
      }
    } else if (e.key === 'ArrowRight') {
      const currentIndex = currentImage
        ? allImages.findIndex(img => img.filename === currentImage.filename)
        : -1;
      if (currentIndex < allImages.length - 1) {
        onNavigate(allImages[currentIndex + 1]);
      }
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

      <div className="image-container" style={{ position: 'relative', marginBottom: '1rem', minHeight: '400px' }}>
        {imageLoading && (
          <div className="has-text-centered" style={{ padding: '2rem' }}>
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

        {imageError && !imageLoading && (
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

        {!imageError && (
          <figure className="image" style={{ display: imageLoading ? 'none' : 'block' }}>
            <img
              src={screenshotApi.getImageUrl(currentImage.filename)}
              alt={currentImage.filename}
              style={{ maxWidth: '100%', height: 'auto' }}
              onLoad={handleImageLoad}
              onError={handleImageError}
            />
          </figure>
        )}
      </div>

      <div className="content is-small has-text-centered" style={{ marginTop: '1rem' }}>
        <p>🎹 矢印キー←→でナビゲーションができます</p>
      </div>
    </div>
  );
};

export default ImageViewer;
