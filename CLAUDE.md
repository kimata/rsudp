# CLAUDE.md

このファイルは Claude Code がこのリポジトリで作業する際のガイダンスを提供します。

## 概要

Raspberry Shake の地震データをリアルタイムで監視・解析するための Docker 環境です。rsudp（Raspberry Shake UDP クライアント）を Docker で動作させ、地震検出時のスクリーンショットを Web UI で閲覧できます。また、気象庁の地震情報を定期収集し、スクリーンショットと照合する機能も備えています。

### 主な機能

- Raspberry Shake からの UDP データ受信とリアルタイム可視化
- 地震検出時の波形スクリーンショット自動保存
- 気象庁 API からの地震情報定期収集（1時間間隔）
- スクリーンショットと地震情報の照合・フィルタリング
- 信号強度（STA/LTA）によるフィルタリング
- React ベースの Web UI

## 重要な注意事項

### コード変更時のドキュメント更新

コードを更新した際は、以下のドキュメントも更新が必要か**必ず検討してください**:

| ドキュメント | 更新が必要なケース                                                 |
| ------------ | ------------------------------------------------------------------ |
| README.md    | 機能追加・変更、使用方法の変更、依存関係の変更                     |
| CLAUDE.md    | アーキテクチャ変更、新規モジュール追加、設定項目変更、開発手順変更 |

### my-lib（共通ライブラリ）の修正について

`my_lib` のソースコードは **`../my-py-lib`** に存在します。

リファクタリング等で `my_lib` の修正が必要な場合:

1. **必ず事前に何を変更したいか説明し、確認を取ること**
2. `../my-py-lib` で修正を行い、commit & push
3. このリポジトリの `pyproject.toml` の my-lib のコミットハッシュを更新
4. `uv lock && uv sync` で依存関係を更新

```bash
# my-lib 更新の流れ
cd ../my-py-lib
# ... 修正 ...
git add . && git commit -m "変更内容" && git push
cd ../rsudp
# pyproject.toml の my-lib ハッシュを更新
uv lock && uv sync
```

### プロジェクト管理ファイルについて

以下のファイルは **`../py-project`** で一元管理しています:

- `pyproject.toml`
- `.pre-commit-config.yaml`
- `.gitignore`
- `.gitlab-ci.yml`
- その他プロジェクト共通設定

**これらのファイルを直接編集しないでください。**

修正が必要な場合:

1. **必ず事前に何を変更したいか説明し、確認を取ること**
2. `../py-project` のテンプレートを更新
3. このリポジトリに変更を反映

## 開発環境

### パッケージ管理

- **パッケージマネージャー**: uv
- **依存関係のインストール**: `uv sync`
- **依存関係の更新**: `uv lock --upgrade-package <package-name>`

### アプリケーション実行

```bash
# Web UI サーバー起動
uv run python src/webui.py

# 地震情報クローラー単体実行
uv run python src/rsudp/quake/crawl.py

# rsudp 本体（Docker 内で実行）
bash rsudp/unix-start-rsudp.sh
```

### React フロントエンド

```bash
cd react
npm install          # 依存関係インストール
npm run dev          # 開発サーバー起動
npm run build        # プロダクションビルド
npm run lint         # ESLint チェック
```

### リント・フォーマット

```bash
uv run ruff check src/    # リントチェック
uv run ruff format src/   # フォーマット
uv run pyright            # 型チェック
```

## アーキテクチャ

### ディレクトリ構成

```
src/
├── webui.py                    # Flask Web サーバーのエントリーポイント
└── rsudp/
    ├── screenshot_manager.py   # スクリーンショット管理・メタデータキャッシュ
    ├── quake/
    │   ├── crawl.py            # 気象庁 API クローラー
    │   └── database.py         # 地震データベース管理
    └── webui/
        └── api/
            └── viewer.py       # REST API エンドポイント

react/                          # React フロントエンド
├── src/
│   ├── App.tsx                 # メインコンポーネント
│   ├── api.ts                  # API クライアント
│   ├── types.ts                # TypeScript 型定義
│   └── components/             # UI コンポーネント
└── dist/                       # ビルド出力

schema/
├── config.schema               # 設定ファイルの JSON Schema
└── sqlite.schema               # SQLite データベーススキーマ

patch/                          # rsudp へのパッチファイル
data/                           # ランタイムデータ
├── screenshots/                # スクリーンショット格納
├── cache.db                    # メタデータキャッシュ
└── quake.db                    # 地震データベース
```

### コアコンポーネント

#### ScreenshotManager (`screenshot_manager.py`)

スクリーンショットファイルとメタデータの管理:

- PNG ファイルの日付ベースサブディレクトリへの自動整理
- ファイル名からのタイムスタンプ解析（UTC）
- PNG メタデータ（STA/LTA 値）の抽出
- SQLite キャッシュによる高速検索
- 信号値・地震時間窓によるフィルタリング

#### QuakeCrawler (`quake/crawl.py`)

気象庁 API からの地震情報収集:

- JMA REST API からの地震一覧・詳細取得
- 座標フォーマット解析（緯度/経度/深さ）
- 震度文字列の数値変換
- 1時間間隔でのバックグラウンド実行

#### QuakeDatabase (`quake/database.py`)

地震データの永続化:

- SQLite による地震データ管理
- タイムスタンプベースの検索
- 時間範囲の生成（地震前後の許容秒数考慮）

### API エンドポイント

Blueprint: `viewer_api` (URL prefix: `/rsudp`)

| メソッド | パス                                    | 説明                       |
| -------- | --------------------------------------- | -------------------------- |
| GET      | `/api/screenshot/`                      | スクリーンショット一覧     |
| GET      | `/api/screenshot/years/`                | 利用可能な年一覧           |
| GET      | `/api/screenshot/<year>/months/`        | 月一覧                     |
| GET      | `/api/screenshot/<year>/<month>/days/`  | 日一覧                     |
| GET      | `/api/screenshot/<year>/<month>/<day>/` | 指定日のスクリーンショット |
| GET      | `/api/screenshot/image/<filename>`      | 画像ファイル配信           |
| GET      | `/api/screenshot/latest/`               | 最新スクリーンショット     |
| GET      | `/api/screenshot/statistics/`           | 統計情報                   |
| POST     | `/api/earthquake/crawl/`                | 地震データのクロール実行   |
| GET      | `/api/earthquake/list/`                 | 地震データ一覧             |

クエリパラメータ:

- `min_max_signal`: 最小信号値フィルタ
- `earthquake_only`: 地震時間窓のみ返却（true/false）

## 設定ファイル

### config.yaml

```yaml
plot:
    screenshot:
        path: data/screenshots # スクリーンショット格納先

data:
    cache: data/cache.db # メタデータキャッシュ DB
    quake: data/quake.db # 地震データベース
    selenium: ./data # その他データディレクトリ

webapp:
    static_dir_path: react/dist # React ビルド出力パス
```

### SQLite スキーマ (`schema/sqlite.schema`)

```sql
CREATE TABLE earthquakes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    detected_at TEXT NOT NULL,       -- JST タイムスタンプ
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    magnitude REAL NOT NULL,
    depth INTEGER NOT NULL,
    epicenter_name TEXT NOT NULL,
    max_intensity TEXT,
    created_at TEXT NOT NULL,        -- UTC
    updated_at TEXT NOT NULL         -- UTC
);
```

## タイムゾーンの扱い

このプロジェクトでは2種類のタイムゾーンが混在するため、特に注意が必要です。

### タイムゾーン規約

| データ                       | タイムゾーン | 備考                            |
| ---------------------------- | ------------ | ------------------------------- |
| スクリーンショットファイル名 | UTC          | `SHAKE-2025-12-12-190542.png`   |
| 地震データ（detected_at）    | JST (+09:00) | 気象庁 API から取得したまま保存 |
| created_at / updated_at      | UTC          | システム管理用                  |

### 比較時の注意

- 必ず `datetime` オブジェクト（タイムゾーン情報付き）として比較する
- 文字列での比較は**絶対に行わない**（9時間のずれが発生する）
- `datetime.fromisoformat()` でパースすればタイムゾーン情報が保持される

```python
# 正しい比較方法
screenshot_ts = datetime.fromisoformat("2025-12-12T19:05:42+00:00")  # UTC
earthquake_ts = datetime.fromisoformat("2025-12-13T04:05:42+09:00")  # JST
# これらは同じ瞬間を指すので、比較すると等しい

# 誤った比較（文字列比較）
"2025-12-12T19:05:42" == "2025-12-13T04:05:42"  # False になってしまう
```

## コーディング規約

### Python バージョン

- Python 3.11 以上

### スタイル

- 最大行長: 110 文字
- ruff でフォーマット・lint
- pyright で型チェック
- 型ヒントを積極的に使用

### インポートスタイル

`from xxx import yyy` は基本的に使わず、`import xxx` としてモジュールをインポートし、使用時は `xxx.yyy` の形式で参照する。

```python
# 推奨
import my_lib.flask_util
my_lib.flask_util.file_etag(...)

# 非推奨
from my_lib.flask_util import file_etag
file_etag(...)
```

**例外:**

- 標準ライブラリの一般的なパターン（例: `from pathlib import Path`）
- 型ヒント用のインポート（`from typing import TYPE_CHECKING`）
- dataclass などのデコレータ（`from dataclasses import dataclass`）

### 型チェック（pyright）

pyright のエラー対策として、各行に `# type: ignore` コメントを付けて回避するのは**最後の手段**とします。

基本方針:

1. **型推論が効くようにコードを書く** - 明示的な型注釈や適切な変数の初期化で対応
2. **型の絞り込み（Type Narrowing）を活用** - `assert`, `if`, `isinstance()` 等で型を絞り込む
3. **どうしても回避できない場合のみ `# type: ignore`** - その場合は理由をコメントに記載

```python
# 推奨: 型の絞り込み
value = get_optional_value()
assert value is not None
use_value(value)

# 非推奨: type: ignore での回避
value = get_optional_value()
use_value(value)  # type: ignore
```

### docstring スタイル

複数行の docstring は、最初の行を空行とし、2行目から概要を記述する:

```python
def function():
    """
    関数の概要を記述する.

    Args:
        param: パラメータの説明

    Returns:
        戻り値の説明

    """
```

## デプロイ

### Docker

```bash
docker compose up
```

主なポート:

- **8888/UDP**: Raspberry Shake データ受信
- **5000**: Flask Web UI

### Kubernetes

- Deployment で1レプリカ運用
- Liveness Probe 対応

### CI/CD (GitLab)

1. **generate-tag**: タグを生成
2. **build-react**: React ビルド
3. **build-image**: Docker イメージ構築
4. **tag-latest**: latest タグ付与（master のみ）
5. **deploy**: Kubernetes デプロイ（master のみ）

## 依存ライブラリ

### Python

| ライブラリ | 用途                           |
| ---------- | ------------------------------ |
| flask      | Web フレームワーク             |
| flask-cors | CORS 対応                      |
| Pillow     | 画像処理（PNG メタデータ抽出） |
| requests   | HTTP クライアント（JMA API）   |
| my-lib     | 自作共通ライブラリ             |

### Node.js

| ライブラリ | 用途               |
| ---------- | ------------------ |
| react      | UI フレームワーク  |
| axios      | API クライアント   |
| bulma      | CSS フレームワーク |
| dayjs      | 日付処理           |
| vite       | ビルドツール       |

## トラブルシューティング

### タイムゾーン関連

| 問題                                         | 対処                                      |
| -------------------------------------------- | ----------------------------------------- |
| 地震データとスクリーンショットの照合がずれる | datetime オブジェクトで比較しているか確認 |
| 9時間のずれがある                            | 文字列比較になっていないか確認            |

### 地震クローラー

| 問題                     | 対処                           |
| ------------------------ | ------------------------------ |
| 地震データが取得できない | JMA API のエンドポイントを確認 |
| クローラーが停止する     | ログを確認し、例外処理を見直す |
