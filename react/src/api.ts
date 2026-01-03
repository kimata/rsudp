import axios from "axios";
import type { Screenshot, ScreenshotListResponse, StatisticsResponse } from "./types";
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

    getStatistics: async (earthquakeOnly?: boolean): Promise<StatisticsResponse> => {
        const params: Record<string, string> = {};
        if (earthquakeOnly) {
            params.earthquake_only = "true";
        }
        const response = await api.get<StatisticsResponse>("/statistics/", { params });
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
