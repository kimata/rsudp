export interface Earthquake {
    id: number;
    event_id: string;
    detected_at: string;
    latitude: number;
    longitude: number;
    magnitude: number;
    depth: number;
    epicenter_name: string;
    max_intensity?: string;
}

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
    earthquake?: Earthquake;
}

export interface ScreenshotListResponse {
    screenshots: Screenshot[];
    total: number;
}

export interface StatisticsResponse {
    total: number;
    absolute_total: number;
    min_signal?: number;
    max_signal?: number;
    avg_signal?: number;
    with_signal: number;
    earthquake_count?: number;
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
