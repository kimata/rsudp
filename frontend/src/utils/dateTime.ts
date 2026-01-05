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

export const formatDateTime = (timestamp: string) => {
    const utcDate = dayjs.utc(timestamp);
    const localDate = utcDate.local();
    const now = dayjs();

    return {
        formatted: localDate.format("YYYY年M月D日 HH時mm分ss秒"),
        compact: localDate.format("MM/DD HH:mm:ss"),
        relative: localDate.from(now),
    };
};

export const formatScreenshotDateTime = (screenshot: Screenshot) => {
    return formatDateTime(screenshot.timestamp);
};

export { dayjs };
