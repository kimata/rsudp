import axios from "axios";
import type {
    Screenshot,
    ScreenshotListResponse,
    YearsResponse,
    MonthsResponse,
    DaysResponse,
    StatisticsResponse,
} from "./types";
import { TIMEOUTS } from "./utils/constants";

// ホスト名を含まない相対パス（React アプリは /rsudp でホストされている）
const API_BASE_URL = "/rsudp/api/screenshot";

console.log("API Base URL:", API_BASE_URL);

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: TIMEOUTS.API_REQUEST,
});

// デバッグ用のリクエストインターセプター
api.interceptors.request.use((config) => {
    console.log("Final request URL:", (config.baseURL || "") + (config.url || ""));
    return config;
});

export const screenshotApi = {
    getYears: async (minMaxSignal?: number): Promise<number[]> => {
        const params = minMaxSignal !== undefined ? { min_max_signal: minMaxSignal } : {};
        const response = await api.get<YearsResponse>("/years/", { params });
        return response.data.years;
    },

    getMonths: async (year: number, minMaxSignal?: number): Promise<number[]> => {
        const params = minMaxSignal !== undefined ? { min_max_signal: minMaxSignal } : {};
        const response = await api.get<MonthsResponse>(`/${year}/months/`, { params });
        return response.data.months;
    },

    getDays: async (year: number, month: number, minMaxSignal?: number): Promise<number[]> => {
        const params = minMaxSignal !== undefined ? { min_max_signal: minMaxSignal } : {};
        const response = await api.get<DaysResponse>(`/${year}/${month}/days/`, { params });
        return response.data.days;
    },

    getScreenshotsByDate: async (
        year: number,
        month: number,
        day: number,
        minMaxSignal?: number,
    ): Promise<Screenshot[]> => {
        const params = minMaxSignal !== undefined ? { min_max_signal: minMaxSignal } : {};
        const response = await api.get<ScreenshotListResponse>(`/${year}/${month}/${day}/`, { params });
        return response.data.screenshots;
    },

    getAllScreenshots: async (minMaxSignal?: number, earthquakeOnly?: boolean): Promise<Screenshot[]> => {
        const params: Record<string, string | number | boolean> = {};
        if (minMaxSignal !== undefined) {
            params.min_max_signal = minMaxSignal;
        }
        if (earthquakeOnly) {
            params.earthquake_only = "true";
        }
        const response = await api.get<ScreenshotListResponse>("/", { params });
        return response.data.screenshots;
    },

    getLatest: async (minMaxSignal?: number): Promise<Screenshot> => {
        const params = minMaxSignal !== undefined ? { min_max_signal: minMaxSignal } : {};
        const response = await api.get<Screenshot>("/latest/", { params });
        return response.data;
    },

    getStatistics: async (): Promise<StatisticsResponse> => {
        const response = await api.get<StatisticsResponse>("/statistics/");
        return response.data;
    },

    getImageUrl: (filename: string): string => {
        return `${API_BASE_URL}/image/${filename}`;
    },

    crawlEarthquakes: async (): Promise<{ success: boolean; new_earthquakes: number }> => {
        const response = await axios.post<{ success: boolean; new_earthquakes: number }>(
            "/rsudp/api/earthquake/crawl/",
        );
        return response.data;
    },
};
