import React, { useEffect, memo, useCallback, useMemo } from 'react';
import { List, useListRef } from 'react-window';
import type { RowComponentProps, ListImperativeAPI } from 'react-window';
import type { Screenshot } from '../types';
import { formatScreenshotDateTime } from '../utils/dateTime';
import { Icon } from './Icon';

// アイテムの高さ（ピクセル）
const ITEM_HEIGHT = 60;
// リストの高さ（ピクセル）
const LIST_HEIGHT = 400;

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

// 行コンポーネントに渡す追加 props の型
interface RowData {
  items: Screenshot[];
  currentFilename: string | null;
  onSelect: (screenshot: Screenshot) => void;
  formattedDates: Map<string, { formatted: string; relative: string }>;
}

// アイコン名を取得する関数
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

// メモ化された内部コンポーネント用の props 型
interface FileListItemContentProps {
  image: Screenshot;
  index: number;
  style: React.CSSProperties;
  isCurrentImage: boolean;
  dateTime: { formatted: string; relative: string };
  onSelect: (screenshot: Screenshot) => void;
}

// メモ化された内部コンポーネント（選択状態が変わらなければ再レンダリングしない）
const FileListItemContent = memo(
  ({ image, index, style, isCurrentImage, dateTime, onSelect }: FileListItemContentProps) => {
    const handleClick = useCallback(() => {
      onSelect(image);
    }, [onSelect, image]);

    return (
      <div
        style={style}
        className={`file-list-item p-2 border-b border-gray-100 dark:border-gray-700 cursor-pointer transition-colors duration-200 ${
          isCurrentImage
            ? 'bg-blue-500 text-white'
            : 'hover:bg-gray-100 dark:hover:bg-gray-700'
        }`}
        onClick={handleClick}
      >
        <div className="flex items-center h-full">
          <span className="mr-2">
            <Icon name={getEventTypeIconName(image.prefix)} className="size-4" />
          </span>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-center">
              <div className="truncate">
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
                className={`inline-flex items-center px-1.5 py-0.5 text-xs rounded flex-shrink-0 ml-2 ${
                  isCurrentImage
                    ? 'bg-white/20 text-white'
                    : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                }`}
              >
                #{index + 1}
              </span>
            </div>
            <div className={`text-xs mt-1 truncate ${isCurrentImage ? 'text-white/80' : 'text-gray-500'}`}>
              {image.filename}
            </div>
          </div>
        </div>
      </div>
    );
  },
  // カスタム比較関数：選択状態が変わらなければ再レンダリングしない
  (prevProps, nextProps) => {
    return (
      prevProps.index === nextProps.index &&
      prevProps.isCurrentImage === nextProps.isCurrentImage &&
      prevProps.image.filename === nextProps.image.filename &&
      prevProps.dateTime.formatted === nextProps.dateTime.formatted &&
      prevProps.style === nextProps.style
    );
  }
);

FileListItemContent.displayName = 'FileListItemContent';

// react-window 用のラッパーコンポーネント
const FileListItem = ({ index, style, items, currentFilename, onSelect, formattedDates }: RowComponentProps<RowData>) => {
  const image = items[index];
  const isCurrentImage = currentFilename === image.filename;
  const dateTime = formattedDates.get(image.filename) || { formatted: '', relative: '' };

  return (
    <FileListItemContent
      image={image}
      index={index}
      style={style}
      isCurrentImage={isCurrentImage}
      dateTime={dateTime}
      onSelect={onSelect}
    />
  );
};

const FileList: React.FC<FileListProps> = memo(({
  allImages,
  currentImage,
  onImageSelect,
  loading = false,
  shouldScrollToCurrentImage = false,
  isFiltering = false,
}) => {
  const listRef = useListRef(null);
  const hasInitialScrolledRef = React.useRef(false);

  // 日時フォーマットを事前計算してキャッシュ
  const formattedDates = useMemo(() => {
    const cache = new Map<string, { formatted: string; relative: string }>();
    for (const screenshot of allImages) {
      const dateTime = formatScreenshotDateTime(screenshot);
      cache.set(screenshot.filename, {
        formatted: dateTime.compact,
        relative: dateTime.relative,
      });
    }
    return cache;
  }, [allImages]);

  // スクロール関数
  const scrollToCurrentItem = useCallback((listApi: ListImperativeAPI | null) => {
    if (!currentImage || !listApi) return;

    const currentIndex = allImages.findIndex(img => img.filename === currentImage.filename);
    if (currentIndex === -1) return;

    // react-window v2 の scrollToRow を使用
    listApi.scrollToRow({ index: currentIndex, align: 'center' });
  }, [allImages, currentImage]);

  // ユーザーが明示的に画像を選択した時のみスクロール
  useEffect(() => {
    if (shouldScrollToCurrentImage && currentImage && allImages.length > 0) {
      scrollToCurrentItem(listRef.current);
    }
  }, [shouldScrollToCurrentImage, currentImage, allImages.length, scrollToCurrentItem, listRef]);

  // 初回レンダリング時の自動スクロール（1回のみ）
  useEffect(() => {
    if (!hasInitialScrolledRef.current && currentImage && allImages.length > 0) {
      hasInitialScrolledRef.current = true;
      // 少し遅延させてリストがレンダリングされてからスクロール
      const timer = setTimeout(() => {
        scrollToCurrentItem(listRef.current);
      }, 50);

      return () => clearTimeout(timer);
    }
  }, [currentImage, allImages.length, scrollToCurrentItem, listRef]);

  // リストに渡すアイテムデータ
  const rowProps: RowData = useMemo(() => ({
    items: allImages,
    currentFilename: currentImage?.filename || null,
    onSelect: onImageSelect,
    formattedDates,
  }), [allImages, currentImage?.filename, onImageSelect, formattedDates]);

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
          className={`border border-gray-300 dark:border-gray-600 rounded transition-opacity duration-200 ${isFiltering ? 'opacity-50' : 'opacity-100'}`}
        >
          <List
            listRef={listRef}
            rowComponent={FileListItem}
            rowCount={allImages.length}
            rowHeight={ITEM_HEIGHT}
            rowProps={rowProps}
            className="file-list-container custom-scrollbar"
            overscanCount={5}
            style={{ height: LIST_HEIGHT }}
          />
        </div>
      </div>
      <div className="text-center text-gray-500 mt-2 text-xs flex items-center justify-center gap-1">
        <Icon name="chart-bar" className="size-4" />
        {allImages.length.toLocaleString()} 件のファイル
      </div>
    </div>
  );
});

FileList.displayName = 'FileList';

export default FileList;
