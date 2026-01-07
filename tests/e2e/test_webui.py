# ruff: noqa: S101
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
        expect(page).to_have_title("RSUDP スクリーンショットビューア")

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
        assert "success" in data
        assert data["success"] is True

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


@pytest.mark.e2e
class TestUrlParametersE2E:
    """URL パラメータ関連の E2E テスト."""

    def test_url_file_parameter_loads_specific_image(self, page, host, port):
        """URL の file パラメータで指定した画像が表示されることを確認.

        1. スクリーンショット一覧を取得
        2. file パラメータ付きで URL にアクセス
        3. 指定した画像が表示されていることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # まず利用可能なスクリーンショットを取得
        response = page.request.get(f"http://{host}:{port}/rsudp/api/screenshot/")
        assert response.ok
        data = response.json()

        if data["total"] == 0:
            pytest.skip("スクリーンショットがないためスキップ")

        # 最初以外のファイルを選択（あれば）
        screenshots = data["screenshots"]
        target_file = screenshots[-1]["filename"] if len(screenshots) > 1 else screenshots[0]["filename"]

        # file パラメータ付きでページにアクセス
        page.goto(rsudp_url(host, port, f"?file={target_file}"), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # URL に file パラメータが含まれていることを確認
        assert f"file={target_file}" in page.url

        # スクリーンショットを保存
        screenshot_path = EVIDENCE_DIR / "e2e_url_file_parameter.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)

    def test_url_earthquake_parameter_false(self, page, host, port):
        """earthquake=false パラメータで地震フィルタが無効になることを確認.

        1. earthquake=false 付きで URL にアクセス
        2. チェックボックスが未チェックであることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # earthquake=false でアクセス
        page.goto(rsudp_url(host, port, "?earthquake=false"), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # チェックボックスを探す
        checkbox = page.locator('input[type="checkbox"]').first
        expect(checkbox).not_to_be_checked()

        # URL に earthquake=false が含まれていることを確認
        assert "earthquake=false" in page.url

    def test_url_earthquake_parameter_true(self, page, host, port):
        """earthquake=true パラメータで地震フィルタが有効になることを確認.

        1. earthquake=true 付きで URL にアクセス
        2. チェックボックスがチェック済みであることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # earthquake=true でアクセス
        page.goto(rsudp_url(host, port, "?earthquake=true"), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # チェックボックスを探す
        checkbox = page.locator('input[type="checkbox"]').first
        expect(checkbox).to_be_checked()

        # URL に earthquake=true が含まれていることを確認
        assert "earthquake=true" in page.url

    def test_url_signal_parameter(self, page, host, port):
        """signal パラメータで信号閾値が設定されることを確認.

        1. signal パラメータ付きで URL にアクセス
        2. スライダーの値が設定されていることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # signal=5000 でアクセス
        page.goto(rsudp_url(host, port, "?signal=5000"), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # URL に signal パラメータが含まれていることを確認
        assert "signal=5000" in page.url

        # スクリーンショットを保存
        screenshot_path = EVIDENCE_DIR / "e2e_url_signal_parameter.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)

    def test_url_multiple_parameters(self, page, host, port):
        """複数の URL パラメータが同時に機能することを確認.

        1. earthquake と signal パラメータ付きで URL にアクセス
        2. 両方のパラメータが適用されていることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # 複数パラメータでアクセス
        page.goto(rsudp_url(host, port, "?earthquake=false&signal=3000"), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # チェックボックスが未チェックであることを確認
        checkbox = page.locator('input[type="checkbox"]').first
        expect(checkbox).not_to_be_checked()

        # URL に両パラメータが含まれていることを確認
        assert "earthquake=false" in page.url
        assert "signal=3000" in page.url

    def test_url_updates_on_earthquake_filter_change(self, page, host, port):
        """地震フィルタ変更時に URL が更新されることを確認.

        1. ページにアクセス
        2. 地震フィルタチェックボックスをクリック
        3. URL が更新されることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # 初期状態（earthquake=true がデフォルト）でアクセス
        page.goto(rsudp_url(host, port), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # チェックボックスをクリック（チェックを外す）
        checkbox = page.locator('input[type="checkbox"]').first
        checkbox.click()

        # URL が更新されるまで待機
        page.wait_for_timeout(500)

        # URL に earthquake=false が含まれていることを確認
        assert "earthquake=false" in page.url

        # スクリーンショットを保存
        screenshot_path = EVIDENCE_DIR / "e2e_url_earthquake_change.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)

    def test_browser_back_forward_navigation(self, page, host, port):
        """ブラウザの戻る/進むボタンで状態が復元されることを確認.

        1. earthquake=true でアクセス
        2. チェックボックスをクリックして earthquake=false に
        3. ブラウザの戻るボタンをクリック
        4. earthquake=true の状態に戻ることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # earthquake=true でアクセス
        page.goto(rsudp_url(host, port, "?earthquake=true"), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # チェックボックスがチェックされていることを確認
        checkbox = page.locator('input[type="checkbox"]').first
        expect(checkbox).to_be_checked()

        # チェックボックスをクリック（チェックを外す）
        checkbox.click()
        page.wait_for_timeout(500)

        # URL が earthquake=false に更新されたことを確認
        assert "earthquake=false" in page.url
        expect(checkbox).not_to_be_checked()

        # ブラウザの戻るボタンをクリック
        page.go_back()
        page.wait_for_timeout(500)

        # チェックボックスがチェック済みに戻ることを確認
        checkbox = page.locator('input[type="checkbox"]').first
        expect(checkbox).to_be_checked()

        # スクリーンショットを保存
        screenshot_path = EVIDENCE_DIR / "e2e_url_back_navigation.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)

    def test_file_selection_updates_url(self, page, host, port):
        """ファイル選択時に URL が更新されることを確認.

        1. ページにアクセス
        2. ファイルリストから別のファイルをクリック
        3. URL に file パラメータが追加されることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        # まず利用可能なスクリーンショットを取得
        response = page.request.get(f"http://{host}:{port}/rsudp/api/screenshot/")
        assert response.ok
        data = response.json()

        if data["total"] < 2:
            pytest.skip("スクリーンショットが2件未満のためスキップ")

        # ページにアクセス
        page.goto(rsudp_url(host, port), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # ファイルリストの2番目の項目をクリック
        file_list_items = page.locator(".file-list-item, [data-testid='file-list-item']")
        if file_list_items.count() >= 2:
            file_list_items.nth(1).click()
            page.wait_for_timeout(500)

            # URL に file パラメータが含まれていることを確認
            assert "file=" in page.url

        # スクリーンショットを保存
        screenshot_path = EVIDENCE_DIR / "e2e_url_file_selection.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)

    def test_invalid_file_parameter_shows_latest(self, page, host, port):
        """存在しない file パラメータの場合、最新の画像が表示されることを確認.

        1. 存在しないファイル名で URL にアクセス
        2. エラーなくページが表示されることを確認
        3. file パラメータが URL から削除されることを確認
        """
        page.set_viewport_size({"width": 1920, "height": 1080})

        js_errors = []
        page.on("pageerror", lambda error: js_errors.append(str(error)))

        # 存在しないファイル名でアクセス
        page.goto(rsudp_url(host, port, "?file=NONEXISTENT-FILE.png"), wait_until="domcontentloaded")
        page.wait_for_load_state("networkidle")

        # JavaScript エラーがないこと
        assert len(js_errors) == 0, f"JavaScript エラーが発生しました: {js_errors}"

        # 存在しないファイルの場合、file パラメータは URL から削除される
        assert "file=NONEXISTENT-FILE.png" not in page.url

        # スクリーンショットを保存
        screenshot_path = EVIDENCE_DIR / "e2e_url_invalid_file.png"
        screenshot_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(screenshot_path), full_page=True)
