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