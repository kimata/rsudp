export interface Earthquake {
    id: number;
    event_id: string;
    // ISO 8601 (UTC)。表示時は JST に変換する
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
    // ISO 8601 (UTC)。日付分類・表示は utils/dateTime.ts で JST に変換する
    timestamp: string;
    // バックエンドは「キーあり + null」を返すため number | null で表現する
    sta: number | null;
    lta: number | null;
    sta_lta_ratio: number | null;
    max_count: number | null;
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
    // バックエンドは「キーあり + null」を返すため number | null で表現する
    min_signal: number | null;
    max_signal: number | null;
    avg_signal: number | null;
    with_signal: number;
    earthquake_count?: number;
}

// --- 統計タブ用の型定義 ---

export interface DailyDetection {
    date: string;
    count: number;
}

export interface DailyDetectionResponse {
    data: DailyDetection[];
}

export interface DistributionBin {
    label: string;
    min: number;
    max: number;
    count: number;
}

export interface DistributionResponse {
    bins: DistributionBin[];
}

export interface AssociationPoint {
    date: string;
    total: number;
    matched: number;
}

export interface AssociationResponse {
    data: AssociationPoint[];
}

export interface SensitivityPoint {
    event_id: string;
    epicenter_name: string;
    distance_km: number;
    magnitude: number;
    depth: number;
    max_count: number;
    detected_at: string;
}

export interface StationLocation {
    latitude: number;
    longitude: number;
}

export interface SensitivityResponse {
    station: StationLocation | null;
    points: SensitivityPoint[];
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
