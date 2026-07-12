import { useEffect, useMemo, useState } from "react";
import {
    Chart as ChartJS,
    CategoryScale,
    LinearScale,
    BarElement,
    PointElement,
    LineElement,
    Tooltip,
    Legend,
    Title,
    type ChartOptions,
} from "chart.js";
import { Bar, Line, Scatter } from "react-chartjs-2";
import type {
    DailyDetectionResponse,
    DistributionResponse,
    AssociationResponse,
    SensitivityResponse,
} from "../types";
import { statisticsApi } from "../api";
import { dayjs } from "../utils/dateTime";
import { Icon } from "./Icon";

ChartJS.register(
    CategoryScale,
    LinearScale,
    BarElement,
    PointElement,
    LineElement,
    Tooltip,
    Legend,
    Title,
);

// アプリのアクセントカラー（app.css と整合）
const COLORS = {
    blue: "#2563eb",
    blueSoft: "rgba(37, 99, 235, 0.6)",
    amber: "#f59e0b",
    amberSoft: "rgba(245, 158, 11, 0.65)",
    emerald: "#10b981",
    teal: "#14b8a6",
};

// prefers-color-scheme を監視してダーク/ライトを判定
function useIsDark(): boolean {
    const [isDark, setIsDark] = useState(
        () => typeof window !== "undefined" && window.matchMedia("(prefers-color-scheme: dark)").matches,
    );
    useEffect(() => {
        const mq = window.matchMedia("(prefers-color-scheme: dark)");
        const handler = (e: MediaQueryListEvent) => setIsDark(e.matches);
        mq.addEventListener("change", handler);
        return () => mq.removeEventListener("change", handler);
    }, []);
    return isDark;
}

// 軸・凡例・ツールチップの共通テーマ
function useChartTheme(isDark: boolean) {
    return useMemo(() => {
        const text = isDark ? "#cbd5e1" : "#475569";
        const grid = isDark ? "rgba(148, 163, 184, 0.15)" : "rgba(100, 116, 139, 0.15)";
        return { text, grid };
    }, [isDark]);
}

// 非同期データ取得の共通フック
function useAsync<T>(fetcher: () => Promise<T>, deps: unknown[] = []) {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        let cancelled = false;
        setLoading(true);
        setError(null);
        fetcher()
            .then((result) => {
                if (!cancelled) setData(result);
            })
            .catch((err: unknown) => {
                if (!cancelled) {
                    setError(err instanceof Error ? err.message : "データの取得に失敗しました");
                }
            })
            .finally(() => {
                if (!cancelled) setLoading(false);
            });
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, deps);

    return { data, loading, error };
}

// カードの共通枠（ローディング/エラー/空データの状態表示を内包）
interface StatCardProps {
    title: string;
    icon: "chart-bar" | "globe" | "funnel" | "calendar";
    accentClass: string;
    iconBgClass: string;
    loading: boolean;
    error: string | null;
    isEmpty: boolean;
    children: React.ReactNode;
    description?: string;
}

function StatCard({
    title,
    icon,
    accentClass,
    iconBgClass,
    loading,
    error,
    isEmpty,
    children,
    description,
}: StatCardProps) {
    return (
        <div className={`bg-white dark:bg-slate-800 rounded-lg shadow-md border-l-4 ${accentClass} p-5`}>
            <h2 className="text-lg font-semibold flex items-center gap-2">
                <span
                    className={`inline-flex items-center justify-center size-8 rounded-full ${iconBgClass}`}
                >
                    <Icon name={icon} className="size-4" />
                </span>
                {title}
            </h2>
            {description && <p className="mt-1 text-sm text-gray-500">{description}</p>}
            <div className="mt-4 h-72 relative">
                {loading ? (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="text-center">
                            <Icon name="arrow-path" className="size-8 text-blue-600" spin />
                            <p className="text-gray-500 mt-2 text-sm">読み込み中...</p>
                        </div>
                    </div>
                ) : error ? (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <div className="text-center">
                            <Icon name="exclamation-triangle" className="size-8 text-red-500" />
                            <p className="text-gray-500 mt-2 text-sm">読み込みに失敗しました</p>
                            <p className="text-xs text-gray-400 mt-1">{error}</p>
                        </div>
                    </div>
                ) : isEmpty ? (
                    <div className="absolute inset-0 flex items-center justify-center">
                        <p className="text-gray-500 text-sm">データがありません</p>
                    </div>
                ) : (
                    children
                )}
            </div>
        </div>
    );
}

// 1. 日別検出数（棒グラフ）
function DailyChart() {
    const isDark = useIsDark();
    const theme = useChartTheme(isDark);
    const { data, loading, error } = useAsync<DailyDetectionResponse>(() => statisticsApi.getDaily(90));

    const points = useMemo(() => data?.data ?? [], [data]);
    const chartData = useMemo(
        () => ({
            labels: points.map((d) => dayjs(d.date).format("M/D")),
            datasets: [
                {
                    label: "検出数",
                    data: points.map((d) => d.count),
                    backgroundColor: COLORS.blueSoft,
                    borderColor: COLORS.blue,
                    borderWidth: 1,
                    borderRadius: 3,
                },
            ],
        }),
        [points],
    );

    const options: ChartOptions<"bar"> = useMemo(
        () => ({
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => `${items[0].label}`,
                        label: (item) => `検出数: ${item.parsed.y} 件`,
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: theme.text, maxRotation: 0, autoSkipPadding: 12 },
                    grid: { display: false },
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: theme.text, precision: 0 },
                    grid: { color: theme.grid },
                    title: { display: true, text: "件数", color: theme.text },
                },
            },
        }),
        [theme],
    );

    return (
        <StatCard
            title="日別検出数"
            icon="calendar"
            accentClass="border-l-blue-500"
            iconBgClass="bg-blue-100 dark:bg-blue-900/40 text-blue-600 dark:text-blue-400"
            loading={loading}
            error={error}
            isEmpty={points.length === 0}
            description="直近 90 日間のスクリーンショット検出数"
        >
            <Bar data={chartData} options={options} />
        </StatCard>
    );
}

// 2. MaxCount 分布（ヒストグラム）
function DistributionChart() {
    const isDark = useIsDark();
    const theme = useChartTheme(isDark);
    const { data, loading, error } = useAsync<DistributionResponse>(() =>
        statisticsApi.getDistribution(),
    );

    const bins = useMemo(() => data?.bins ?? [], [data]);
    const chartData = useMemo(
        () => ({
            labels: bins.map((b) => b.label),
            datasets: [
                {
                    label: "件数",
                    data: bins.map((b) => b.count),
                    backgroundColor: COLORS.amberSoft,
                    borderColor: COLORS.amber,
                    borderWidth: 1,
                    borderRadius: 3,
                },
            ],
        }),
        [bins],
    );

    const options: ChartOptions<"bar"> = useMemo(
        () => ({
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => `最大振幅: ${items[0].label}`,
                        label: (item) => `件数: ${item.parsed.y} 件`,
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: theme.text, maxRotation: 0, autoSkipPadding: 8 },
                    grid: { display: false },
                    title: { display: true, text: "最大振幅 (MaxCount)", color: theme.text },
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: theme.text, precision: 0 },
                    grid: { color: theme.grid },
                    title: { display: true, text: "件数", color: theme.text },
                },
            },
        }),
        [theme],
    );

    return (
        <StatCard
            title="MaxCount 分布"
            icon="chart-bar"
            accentClass="border-l-amber-500"
            iconBgClass="bg-amber-100 dark:bg-amber-900/40 text-amber-600 dark:text-amber-400"
            loading={loading}
            error={error}
            isEmpty={bins.length === 0}
            description="スクリーンショットの最大振幅の分布"
        >
            <Bar data={chartData} options={options} />
        </StatCard>
    );
}

// 3. JMA 照合率の推移（折れ線）
function AssociationChart() {
    const isDark = useIsDark();
    const theme = useChartTheme(isDark);
    const { data, loading, error } = useAsync<AssociationResponse>(() =>
        statisticsApi.getAssociation(90),
    );

    const points = useMemo(() => data?.data ?? [], [data]);
    const chartData = useMemo(
        () => ({
            labels: points.map((d) => dayjs(d.date).format("M/D")),
            datasets: [
                {
                    label: "照合率",
                    data: points.map((d) => (d.total > 0 ? (d.matched / d.total) * 100 : 0)),
                    borderColor: COLORS.emerald,
                    backgroundColor: "rgba(16, 185, 129, 0.15)",
                    fill: true,
                    tension: 0.3,
                    pointRadius: 2,
                    pointHoverRadius: 5,
                    borderWidth: 2,
                },
            ],
        }),
        [points],
    );

    const options: ChartOptions<"line"> = useMemo(
        () => ({
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        title: (items) => `${items[0].label}`,
                        label: (item) => {
                            const p = points[item.dataIndex];
                            const rate = (item.parsed.y ?? 0).toFixed(1);
                            return `照合率: ${rate}%（${p.matched} / ${p.total} 件）`;
                        },
                    },
                },
            },
            scales: {
                x: {
                    ticks: { color: theme.text, maxRotation: 0, autoSkipPadding: 12 },
                    grid: { display: false },
                },
                y: {
                    beginAtZero: true,
                    max: 100,
                    ticks: { color: theme.text, callback: (v) => `${v}%` },
                    grid: { color: theme.grid },
                    title: { display: true, text: "照合率", color: theme.text },
                },
            },
        }),
        [theme, points],
    );

    return (
        <StatCard
            title="JMA 照合率の推移"
            icon="globe"
            accentClass="border-l-emerald-500"
            iconBgClass="bg-emerald-100 dark:bg-emerald-900/40 text-emerald-600 dark:text-emerald-400"
            loading={loading}
            error={error}
            isEmpty={points.length === 0}
            description="直近 90 日間の気象庁地震情報との照合率（照合数 / 総数）"
        >
            <Line data={chartData} options={options} />
        </StatCard>
    );
}

// マグニチュードを点の大きさに対応させる
const magnitudeToRadius = (m: number): number => Math.max(3, Math.min(16, m * 2));

// 4. 検出感度: 震央距離 × MaxCount（散布図）
function SensitivityChart() {
    const isDark = useIsDark();
    const theme = useChartTheme(isDark);
    const { data, loading, error } = useAsync<SensitivityResponse>(() =>
        statisticsApi.getSensitivity(),
    );

    const points = useMemo(() => data?.points ?? [], [data]);
    const stationMissing = data != null && data.station === null;

    const chartData = useMemo(
        () => ({
            datasets: [
                {
                    label: "地震",
                    data: points.map((p) => ({
                        x: p.distance_km,
                        y: p.max_count,
                        // ツールチップ用にメタ情報を保持
                        _meta: p,
                    })),
                    backgroundColor: COLORS.blueSoft,
                    borderColor: COLORS.blue,
                    borderWidth: 1,
                    pointRadius: points.map((p) => magnitudeToRadius(p.magnitude)),
                    pointHoverRadius: points.map((p) => magnitudeToRadius(p.magnitude) + 2),
                },
            ],
        }),
        [points],
    );

    const options: ChartOptions<"scatter"> = useMemo(
        () => ({
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (item) => {
                            const p = points[item.dataIndex];
                            if (!p) return "";
                            return [
                                `${p.epicenter_name}`,
                                `M${p.magnitude} / 震央距離 ${p.distance_km.toFixed(1)} km`,
                                `最大振幅: ${Math.round(p.max_count).toLocaleString()}`,
                            ];
                        },
                    },
                },
            },
            scales: {
                x: {
                    type: "linear",
                    beginAtZero: true,
                    ticks: { color: theme.text },
                    grid: { color: theme.grid },
                    title: { display: true, text: "震央距離 (km)", color: theme.text },
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: theme.text },
                    grid: { color: theme.grid },
                    title: { display: true, text: "最大振幅 (MaxCount)", color: theme.text },
                },
            },
        }),
        [theme, points],
    );

    // station が未設定の場合は案内を表示（チャートは出さない）
    if (stationMissing) {
        return (
            <StatCard
                title="検出感度: 震央距離 × MaxCount"
                icon="funnel"
                accentClass="border-l-teal-500"
                iconBgClass="bg-teal-100 dark:bg-teal-900/40 text-teal-600 dark:text-teal-400"
                loading={false}
                error={null}
                isEmpty={false}
                description="点の大きさはマグニチュードに対応"
            >
                <div className="absolute inset-0 flex items-center justify-center">
                    <div className="text-center px-4">
                        <Icon name="exclamation-circle" className="size-8 text-amber-500" />
                        <p className="text-gray-500 mt-2 text-sm">
                            観測局の座標（config の station）が未設定です
                        </p>
                    </div>
                </div>
            </StatCard>
        );
    }

    return (
        <StatCard
            title="検出感度: 震央距離 × MaxCount"
            icon="funnel"
            accentClass="border-l-teal-500"
            iconBgClass="bg-teal-100 dark:bg-teal-900/40 text-teal-600 dark:text-teal-400"
            loading={loading}
            error={error}
            isEmpty={points.length === 0}
            description="点の大きさはマグニチュードに対応"
        >
            <Scatter data={chartData} options={options} />
        </StatCard>
    );
}

function StatisticsPage() {
    return (
        <div className="mt-4 grid grid-cols-1 lg:grid-cols-2 gap-4">
            <DailyChart />
            <DistributionChart />
            <AssociationChart />
            <SensitivityChart />
        </div>
    );
}

export default StatisticsPage;
