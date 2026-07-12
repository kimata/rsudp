import dayjs from "dayjs";
import "dayjs/locale/ja";
import relativeTime from "dayjs/plugin/relativeTime";
import utc from "dayjs/plugin/utc";
import timezone from "dayjs/plugin/timezone";
import localizedFormat from "dayjs/plugin/localizedFormat";
import type { Screenshot } from "../types";

// Configure dayjs once
dayjs.extend(relativeTime);
dayjs.extend(utc);
dayjs.extend(timezone);
dayjs.extend(localizedFormat);
dayjs.locale("ja");

// スクリーンショットの timestamp は UTC。表示・日付分類はすべて JST に統一する。
const JST = "Asia/Tokyo";

export const formatDateTime = (timestamp: string) => {
    const jstDate = dayjs.utc(timestamp).tz(JST);
    const now = dayjs();

    return {
        formatted: jstDate.format("YYYY年M月D日 HH時mm分ss秒"),
        compact: jstDate.format("MM/DD HH:mm:ss"),
        relative: jstDate.from(now),
    };
};

export const formatScreenshotDateTime = (screenshot: Screenshot) => {
    return formatDateTime(screenshot.timestamp);
};

/**
 * 地震発生時刻（ISO 8601、UTC）を JST の短い表示文字列に変換する。
 * ブラウザのローカルタイムゾーンに依存させず、常に JST で表示する。
 */
export const formatEarthquakeDateTime = (timestamp: string): string => {
    return dayjs.utc(timestamp).tz(JST).format("M/D HH:mm");
};

/**
 * UTC の timestamp から JST の年月日を導出する。
 * ファイル名由来の UTC year/month/day では JST 0:00〜8:59 が前日にずれるため、
 * 日付分類・フィルタはこの JST 基準の値を用いる。
 */
export const getJstDateParts = (timestamp: string): { year: number; month: number; day: number } => {
    const jst = dayjs.utc(timestamp).tz(JST);
    return { year: jst.year(), month: jst.month() + 1, day: jst.date() };
};

export { dayjs };
