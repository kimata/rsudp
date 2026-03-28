import { useState, useEffect } from 'react';
import { version as reactVersion } from 'react';
import { useApi } from '../hooks/useApi';
import type { SysInfo } from '../types';
import { dayjs } from '../utils/dateTime';
import { TIMEOUTS } from '../utils/constants';
import { GitHubIcon } from './Icon';

function Footer() {
    const [updateTime, setUpdateTime] = useState(dayjs().format('YYYY年MM月DD日 HH:mm:ss'));
    const buildDate = dayjs(import.meta.env.VITE_BUILD_DATE || new Date().toISOString());
    const { data: sysInfo } = useApi<SysInfo>('/rsudp/api/sysinfo', { interval: TIMEOUTS.SYSTEM_INFO_POLL });

    useEffect(() => {
        // 定期的に更新時刻を更新
        const interval = setInterval(() => {
            setUpdateTime(dayjs().format('YYYY年MM月DD日 HH:mm:ss'));
        }, TIMEOUTS.TIME_UPDATE);

        return () => clearInterval(interval);
    }, []);

    const getImageBuildDate = () => {
        if (!sysInfo?.image_build_date) return 'Unknown';
        const buildDate = dayjs(sysInfo.image_build_date);
        return `${buildDate.format('YYYY年MM月DD日 HH:mm:ss')} [${buildDate.fromNow()}]`;
    };

    return (
        <footer className="mt-8 border-t border-gray-200 dark:border-slate-700 pt-4 pb-2 px-2" data-testid="footer">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 text-xs text-gray-400 dark:text-gray-500">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
                    <span>更新: {updateTime}</span>
                    <span className="hidden sm:inline text-gray-300 dark:text-gray-600">|</span>
                    <span>イメージ: {getImageBuildDate()}</span>
                    <span className="hidden sm:inline text-gray-300 dark:text-gray-600">|</span>
                    <span>React {reactVersion} ({buildDate.format('YYYY/MM/DD')})</span>
                </div>
                <a
                    href="https://github.com/kimata/rsudp"
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                >
                    <GitHubIcon className="size-5 inline-block" />
                </a>
            </div>
        </footer>
    );
}

export default Footer;
