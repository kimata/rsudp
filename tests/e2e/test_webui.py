# ruff: noqa: S101,D213,D403
"""
WebUI E2E テスト.

Playwright を使用して WebUI の E2E テストを実行します。
"""

import logging
import pathlib

import pytest
from playwright.sync_api import expect

# プロジェクトルートの reports/evidence/ に保存
EVIDENCE_DIR = pathlib.Path(__file__).parent.parent.parent / "reports" / "evidence"

RSUDP_URL_TMPL = "http://{host}:{port}/rsudp"


def rsudp_url(host, port, path=""):
    """rsudp ページの URL を生成."""
    base = RSUDP_URL_TMPL.format(host=host, port=port)
    if path:
        return f"{base}/{path}"
    return base


@pytest.mark.e2e
class TestWebuiE2E:
    """WebUI E2E テスト."""

    def test_page_loads(self, page, host, port):
        """メインページ表示の E2E テスト.

        1. rsudp ページにアクセス
        2. ページが正常にロードされることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # コンソールログをキャプチャ
        console_errors = []
        page.on(
            "console",
            lambda message: (
                console_errors.append(message.text) if message.type == "error" else logging.info(message.text)
            ),
        )

        # rsudp ページにアクセス
        page.goto(rsudp_url(host, port), wait_until="domcontentloaded")

        # ページタイトルを確認
        expect(page).to_have_title("RSUDP Viewer")

        # スクリーンショットを保存
        screenshot_path = EVIDENCE_DIR / "e2e_rsudp_page.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)

    def test_api_screenshot_list(self, page, host, port):
        """スクリーンショット一覧 API のテスト."""
        response = page.request.get(f"http://{host}:{port}/rsudp/api/screenshot/")

        assert response.ok
        data = response.json()
        assert "screenshots" in data
        assert "total" in data

    def test_api_screenshot_statistics(self, page, host, port):
        """統計情報 API のテスト."""
        response = page.request.get(f"http://{host}:{port}/rsudp/api/screenshot/statistics/")

        assert response.ok
        data = response.json()
        assert "total" in data

    def test_api_screenshot_years(self, page, host, port):
        """年一覧 API のテスト."""
        response = page.request.get(f"http://{host}:{port}/rsudp/api/screenshot/years/")

        assert response.ok
        data = response.json()
        assert "years" in data

    def test_api_earthquake_list(self, page, host, port):
        """地震一覧 API のテスト."""
        response = page.request.get(f"http://{host}:{port}/rsudp/api/earthquake/list/")

        assert response.ok
        data = response.json()
        assert "earthquakes" in data

    def test_api_screenshot_scan(self, page, host, port):
        """スキャン API のテスト."""
        response = page.request.post(f"http://{host}:{port}/rsudp/api/screenshot/scan/")

        assert response.ok
        data = response.json()
        assert "status" in data

    def test_api_earthquake_filter(self, page, host, port):
        """地震フィルタ付きスクリーンショット API のテスト."""
        response = page.request.get(f"http://{host}:{port}/rsudp/api/screenshot/?earthquake_only=true")

        assert response.ok
        data = response.json()
        assert "screenshots" in data
        assert "total" in data

    def test_api_min_max_signal_filter(self, page, host, port):
        """最小信号値フィルタ付きスクリーンショット API のテスト."""
        response = page.request.get(f"http://{host}:{port}/rsudp/api/screenshot/?min_max_signal=1000")

        assert response.ok
        data = response.json()
        assert "screenshots" in data

    def test_page_no_js_errors(self, page, host, port):
        """JavaScript エラーがないことを確認.

        1. rsudp ページにアクセス
        2. JavaScript エラーがないことを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        js_errors = []
        page.on("pageerror", lambda error: js_errors.append(str(error)))

        page.goto(rsudp_url(host, port), wait_until="domcontentloaded")

        # ページのロード完了を待機
        page.wait_for_load_state("load")

        # JavaScript エラーがないこと
        assert len(js_errors) == 0, f"JavaScript エラーが発生しました: {js_errors}"
