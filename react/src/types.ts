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
