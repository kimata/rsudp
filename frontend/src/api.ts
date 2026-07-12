import axios from "axios";
import type {
    Screenshot,
    ScreenshotListResponse,
    StatisticsResponse,
    DailyDetectionResponse,
    DistributionResponse,
    AssociationResponse,
    SensitivityResponse,
} from "./types";
import { TIMEOUTS } from "./utils/constants";

// ホスト名を含まない相対パス（React アプリは /rsudp でホストされている）
const API_BASE_URL = "/rsudp/api/screenshot";
const STATISTICS_BASE_URL = "/rsudp/api/statistics";

const api = axios.create({
    baseURL: API_BASE_URL,
    timeout: TIMEOUTS.API_REQUEST,
});

const statsApi = axios.create({
    baseURL: STATISTICS_BASE_URL,
    timeout: TIMEOUTS.API_REQUEST,
});

export const screenshotApi = {
    getAllScreenshots: async (
        minMaxSignal?: number,
        earthquakeOnly?: boolean,
        minMagnitude?: number
    ): Promise<Screenshot[]> => {
        const params: Record<string, string | number | boolean> = {};
        if (minMaxSignal !== undefined) {
            params.min_max_signal = minMaxSignal;
        }
        if (earthquakeOnly) {
            params.earthquake_only = "true";
        }
        if (minMagnitude !== undefined) {
            params.min_magnitude = minMagnitude;
        }
        const response = await api.get<ScreenshotListResponse>("/", { params });
        return response.data.screenshots;
    },

    getLatest: async (minMaxSignal?: number): Promise<Screenshot> => {
        const params = minMaxSignal !== undefined ? { min_max_signal: minMaxSignal } : {};
        const response = await api.get<Screenshot>("/latest/", { params });
        return response.data;
    },

    getStatistics: async (earthquakeOnly?: boolean, minMagnitude?: number): Promise<StatisticsResponse> => {
        const params: Record<string, string | number> = {};
        if (earthquakeOnly) {
            params.earthquake_only = "true";
        }
        if (minMagnitude !== undefined) {
            params.min_magnitude = minMagnitude;
        }
        const response = await api.get<StatisticsResponse>("/statistics/", { params });
        return response.data;
    },

    getImageUrl: (filename: string): string => {
        return `${API_BASE_URL}/image/${filename}`;
    },

    crawlEarthquakes: async (): Promise<{ success: boolean; new_earthquakes: number }> => {
        const response = await axios.post<{ success: boolean; new_earthquakes: number }>(
            "/rsudp/api/earthquake/crawl/"
        );
        return response.data;
    },

    scanScreenshots: async (
        full: boolean = false
    ): Promise<{ success: boolean; new_files?: number; skipped: boolean; scan_type?: string }> => {
        const response = await api.post<{
            success: boolean;
            new_files?: number;
            skipped: boolean;
            scan_type?: string;
        }>("/scan/", { full });
        return response.data;
    },
};

export const statisticsApi = {
    // 日別検出数
    getDaily: async (days: number = 90): Promise<DailyDetectionResponse> => {
        const response = await statsApi.get<DailyDetectionResponse>("/daily", { params: { days } });
        return response.data;
    },

    // MaxCount 分布
    getDistribution: async (): Promise<DistributionResponse> => {
        const response = await statsApi.get<DistributionResponse>("/distribution");
        return response.data;
    },

    // JMA 照合率の推移
    getAssociation: async (days: number = 90): Promise<AssociationResponse> => {
        const response = await statsApi.get<AssociationResponse>("/association", { params: { days } });
        return response.data;
    },

    // 検出感度: 震央距離 × MaxCount
    getSensitivity: async (): Promise<SensitivityResponse> => {
        const response = await statsApi.get<SensitivityResponse>("/sensitivity");
        return response.data;
    },
};
