import React, { useEffect, useRef } from 'react';
import type { Screenshot } from '../types';
import { formatScreenshotDateTime } from '../utils/dateTime';
import { TIMEOUTS } from '../utils/constants';

interface FileListProps {
  allImages: Screenshot[];
  currentImage: Screenshot | null;
  onImageSelect: (screenshot: Screenshot) => void;
  loading?: boolean;
}

const FileList: React.FC<FileListProps> = ({
  allImages,
  currentImage,
  onImageSelect,
  loading = false,
}) => {
  const containerRef = useRef<HTMLDivElement>(null);
  const currentItemRef = useRef<HTMLDivElement>(null);

  // スクロール関数を定義
  const scrollToCurrentItem = (immediate = false) => {
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

      console.log('Scrolling to index:', currentIndex, 'filename:', currentImage.filename, 'itemHeight:', itemHeight, 'scrollTop:', centeredScrollTop);

      container.scrollTo({
        top: Math.max(0, centeredScrollTop),
        behavior: immediate ? 'auto' : 'smooth'
      });
    }, immediate ? 0 : TIMEOUTS.PRELOAD_DELAY);

    return () => clearTimeout(timer);
  };

  // 現在の画像が変更されたときにスクロール
  useEffect(() => {
    if (currentImage && allImages.length > 0) {
      scrollToCurrentItem();
    }
  }, [currentImage?.filename]);

  // 初回レンダリング時の自動スクロール
  useEffect(() => {
    if (currentImage && allImages.length > 0) {
      // 初回は即座にスクロール（アニメーションなし）
      const timer = setTimeout(() => {
        scrollToCurrentItem(true);
      }, TIMEOUTS.SCROLL_DELAY); // より長い遅延で確実にレンダリング完了を待つ

      return () => clearTimeout(timer);
    }
  }, [allImages.length]); // allImagesが設定された時

  const formatFileDateTime = (screenshot: Screenshot) => {
    const dateTime = formatScreenshotDateTime(screenshot);
    return {
      formatted: dateTime.compact,
      relative: dateTime.relative
    };
  };

  const getEventTypeIcon = (prefix: string) => {
    switch (prefix.toUpperCase()) {
      case 'SHAKE':
        return '🌍';
      case 'ALERT':
        return '🚨';
      case 'WARNING':
        return '⚠️';
      default:
        return '📷';
    }
  };

  // ローディング中の表示
  if (loading && allImages.length === 0) {
    return (
      <div className="box">
        <h2 className="title is-5">📄 ファイル一覧</h2>
        <div
          style={{
            height: '400px',
            border: '1px solid #dbdbdb',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <div className="has-text-centered">
            <span className="icon is-large">
              <i className="fas fa-spinner fa-pulse fa-2x"></i>
            </span>
            <p className="subtitle mt-3">📄 ファイル一覧を読み込み中...</p>
          </div>
        </div>
        <div className="has-text-centered has-text-grey" style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
          📊 読み込み中...
        </div>
      </div>
    );
  }

  if (allImages.length === 0) {
    return (
      <div className="box">
        <h2 className="title is-5">📄 ファイル一覧</h2>
        <div
          style={{
            height: '400px',
            border: '1px solid #dbdbdb',
            borderRadius: '4px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center'
          }}
        >
          <div className="has-text-centered has-text-grey">
            <p>ファイルがありません</p>
          </div>
        </div>
        <div className="has-text-centered has-text-grey" style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
          📊 0 件のファイル
        </div>
      </div>
    );
  }

  return (
    <div className="box">
      <h2 className="title is-5">📄 ファイル一覧</h2>
      <div
        ref={containerRef}
        className="file-list-container"
        style={{
          height: '400px',
          overflowY: 'auto',
          border: '1px solid #dbdbdb',
          borderRadius: '4px'
        }}
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
              className={`file-list-item ${isCurrentImage ? 'is-active' : ''}`}
              onClick={() => onImageSelect(image)}
              style={{
                padding: '0.5rem',
                borderBottom: '1px solid #f5f5f5',
                cursor: 'pointer',
                backgroundColor: isCurrentImage ? '#3273dc' : 'transparent',
                color: isCurrentImage ? 'white' : 'inherit',
                transition: 'all 0.2s ease',
              }}
              onMouseEnter={(e) => {
                if (!isCurrentImage) {
                  e.currentTarget.style.backgroundColor = '#f5f5f5';
                }
              }}
              onMouseLeave={(e) => {
                if (!isCurrentImage) {
                  e.currentTarget.style.backgroundColor = 'transparent';
                }
              }}
            >
              <div className="is-flex is-align-items-center">
                <span className="icon is-small" style={{ marginRight: '0.5rem' }}>
                  {getEventTypeIcon(image.prefix)}
                </span>
                <div className="is-flex-grow-1">
                  <div className="is-flex is-justify-content-space-between is-align-items-center">
                    <div>
                      <span className="has-text-weight-semibold" style={{ fontSize: '0.85rem' }}>
                        {dateTime.formatted}
                      </span>
                      <span
                        style={{
                          fontSize: '0.7rem',
                          opacity: 0.7,
                          marginLeft: '0.25rem',
                          color: isCurrentImage ? 'rgba(255,255,255,0.8)' : '#666'
                        }}
                      >
                        ({dateTime.relative})
                      </span>
                    </div>
                    <span
                      className="tag is-small"
                      style={{
                        backgroundColor: isCurrentImage ? 'rgba(255,255,255,0.2)' : '#e8e8e8',
                        color: isCurrentImage ? 'white' : 'inherit'
                      }}
                    >
                      #{index + 1}
                    </span>
                  </div>
                  <div style={{ fontSize: '0.75rem', opacity: 0.8, marginTop: '0.25rem' }}>
                    {image.filename}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <div className="has-text-centered has-text-grey" style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
        📊 {allImages.length.toLocaleString()} 件のファイル
      </div>
    </div>
  );
};

export default FileList;
