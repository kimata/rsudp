import axios from "axios";
import type {
    Screenshot,
    ScreenshotListResponse,
    YearsResponse,
    MonthsResponse,
    DaysResponse,
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
    getYears: async (): Promise<number[]> => {
        const response = await api.get<YearsResponse>("/years/");
        return response.data.years;
    },

    getMonths: async (year: number): Promise<number[]> => {
        const response = await api.get<MonthsResponse>(`/${year}/months/`);
        return response.data.months;
    },

    getDays: async (year: number, month: number): Promise<number[]> => {
        const response = await api.get<DaysResponse>(`/${year}/${month}/days/`);
        return response.data.days;
    },

    getScreenshotsByDate: async (year: number, month: number, day: number): Promise<Screenshot[]> => {
        const response = await api.get<ScreenshotListResponse>(`/${year}/${month}/${day}/`);
        return response.data.screenshots;
    },

    getAllScreenshots: async (): Promise<Screenshot[]> => {
        const response = await api.get<ScreenshotListResponse>("/");
        return response.data.screenshots;
    },

    getLatest: async (): Promise<Screenshot> => {
        const response = await api.get<Screenshot>("/latest/");
        return response.data;
    },

    getImageUrl: (filename: string): string => {
        return `${API_BASE_URL}/image/${filename}`;
    },
};
