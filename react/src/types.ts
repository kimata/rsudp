export interface Screenshot {
    filename: string;
    prefix: string;
    year: number;
    month: number;
    day: number;
    hour: number;
    minute: number;
    second: number;
    timestamp: string;
    sta?: number;
    lta?: number;
    sta_lta_ratio?: number;
    max_count: number;
    metadata?: string;
}

export interface ScreenshotListResponse {
    screenshots: Screenshot[];
    total: number;
}

export interface YearsResponse {
    years: number[];
}

export interface MonthsResponse {
    months: number[];
}

export interface DaysResponse {
    days: number[];
}

export interface StatisticsResponse {
    total: number;
    min_signal?: number;
    max_signal?: number;
    avg_signal?: number;
    with_signal: number;
}

export interface SysInfo {
    date: string;
    timezone: string;
    image_build_date: string;
    uptime: string;
    load_average: string;
    cpu_usage: number;
    memory_usage_percent: number;
    memory_free_mb: number;
    disk_usage_percent: number;
    disk_free_mb: number;
    process_count: number;
    cpu_temperature?: number;
}
