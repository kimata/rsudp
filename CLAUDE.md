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
uv run rsudp-webui

# ヘルスチェック
uv run rsudp-healthz

# スクリーンショットクリーナー
uv run rsudp-cleaner

# rsudp 本体（Docker 内で実行）
bash rsudp/unix-start-rsudp.sh
```

### React フロントエンド

```bash
cd frontend
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
└── rsudp/
    ├── cli/                        # CLI エントリーポイント群
    │   ├── webui.py                # Web UI サーバー（rsudp-webui）
    │   ├── healthz.py              # Liveness チェック（rsudp-healthz）
    │   └── cleaner.py              # スクリーンショットクリーナー（rsudp-cleaner）
    ├── screenshot_manager.py       # スクリーンショット管理・メタデータキャッシュ
    ├── types.py                    # 共通型定義（dataclass）
    ├── quake/
    │   ├── crawl.py                # 気象庁 API クローラー
    │   └── database.py             # 地震データベース管理
    └── webui/
        └── api/
            └── viewer.py           # REST API エンドポイント

frontend/                           # React フロントエンド
├── src/
│   ├── App.tsx                     # メインコンポーネント
│   ├── api.ts                      # API クライアント
│   ├── types.ts                    # TypeScript 型定義
│   └── components/                 # UI コンポーネント
└── dist/                           # ビルド出力

schema/
├── config.schema                   # 設定ファイルの JSON Schema
└── sqlite.schema                   # SQLite データベーススキーマ

patch/                              # rsudp へのパッチファイル
data/                               # ランタイムデータ
├── screenshots/                    # スクリーンショット格納
├── cache.db                        # メタデータキャッシュ
└── quake.db                        # 地震データベース
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
    static_dir_path: frontend/dist # React ビルド出力パス
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

### dataclass の活用

内部データ構造には dataclass を使用し、型安全性を確保する:

- `rsudp/types.py` に共通の型定義を集約
- `dict` を返す関数には dataclass で戻り値型を明示
- フロントエンドの `frontend/src/types.ts` と整合性を保つ
- API レスポンスでは `dataclasses.asdict()` で辞書に変換

```python
from dataclasses import dataclass

@dataclass
class ParsedFilename:
    filename: str
    prefix: str
    year: int
    # ...

# 使用例: API レスポンスでの変換
import dataclasses
return flask.jsonify(dataclasses.asdict(parsed))
```

### 型安全性のガイドライン

#### Protocol の導入について

- Protocol は既存の dataclass や型ヒントで十分な場合は導入しない
- インターフェースが複数の異なるクラスで共有される場合にのみ検討

#### dict vs dataclass の選択基準

- 構造が固定されているデータには dataclass を使用
- 外部 API（JMA 等）のレスポンスは dict のまま受け取り、内部で dataclass に変換
- API レスポンスでは `dataclasses.asdict()` で辞書に変換

```python
# 外部 API レスポンスを内部データ構造に変換
def get_all_earthquakes() -> list[EarthquakeData]:
    rows = fetch_from_db()
    return [EarthquakeData(**dict(row)) for row in rows]

# API レスポンスで辞書に戻す
import dataclasses
return flask.jsonify([dataclasses.asdict(eq) for eq in earthquakes])
```

#### 関数の共通化基準

- 完全に同一のコードが2箇所以上で重複している場合は共通化
- 2-3行程度の単純な計算式は共通化しない（可読性低下のデメリット）
- 共通関数は適切なモジュールに配置（型に関連する関数は types.py など）

### コード重複の回避

同じデータ構造を構築するコードは共通関数に集約する:

- 辞書構築ロジックはヘルパー関数（例: `rsudp.types.row_to_screenshot_dict()`）にまとめる
- 複数箇所で同じ処理がある場合は DRY 原則に従う
- パス解決など共通操作も関数化する

### 地震時間範囲計算

地震発生時刻から前後の時間範囲を計算する場合は、`rsudp.types.calculate_earthquake_time_range()` を使用する:

```python
start_time, end_time = rsudp.types.calculate_earthquake_time_range(
    earthquake.detected_at,
    before_seconds=30,
    after_seconds=240,
)
```

### Path オブジェクトの扱い

- `shutil.move()`, `shutil.copy()` 等には Path オブジェクトをそのまま渡す
- 不要な `str()` 変換は行わない（Python 3.6+ でサポート）

```python
# 推奨: Path オブジェクトをそのまま渡す
shutil.move(file_path, new_path)

# 非推奨: 不要な str() 変換
shutil.move(str(file_path), str(new_path))
```

### my_lib の積極的活用

my_lib の機能を活用してコードをシンプルにする:

- `my_lib.safe_access.safe()`: hasattr/getattr チェーンの簡略化
- `my_lib.config.accessor()`: 深いネストの設定アクセスを安全に

```python
# hasattr/getattr チェーンの簡略化
import my_lib.safe_access

sa = my_lib.safe_access.safe(obj)
if sa.attr1 and sa.attr2:
    value = sa.attr1.value()
```

### 未使用の dataclass について

`types.py` に定義された dataclass は積極的に活用する:

- 新しい辞書を返す関数を書く前に、既存の dataclass を確認
- `SignalStatistics`, `DateInfo` 等は定義済みなので活用すること
- 新規に定義する場合は `types.py` に集約

### タイムゾーン定数

- JST タイムゾーンは `rsudp.types.JST` を使用
- ファイルごとにローカル定義しない（`datetime.timezone(datetime.timedelta(hours=9))` 等）
- テストでも `rsudp.types.JST` を参照する

### テストコードの規約

- テストでも本番コードと同じインポートスタイル・規約に従う
- タイムゾーン定数は `rsudp.types.JST` を使用（`zoneinfo` や手動 `timezone` 構築は禁止）
- 共通のテストデータ挿入は `tests/helpers.py` の `insert_screenshot_metadata()` ヘルパー関数を使用

```python
# 推奨: helpers.py のヘルパー関数を使用
from tests.helpers import insert_screenshot_metadata

with sqlite3.connect(manager.cache_path) as conn:
    insert_screenshot_metadata(conn, max_count=500.0)

# 非推奨: 毎回 SQL INSERT 文を記述
with sqlite3.connect(manager.cache_path) as conn:
    conn.execute(
        """INSERT INTO screenshot_metadata (...) VALUES (?, ?, ...)""",
        (...),
    )
```

### タイムゾーン変換

- 手動オフセット追加 (`+ timedelta(hours=9)`) は使用しない
- 常に `astimezone(rsudp.types.JST)` を使用する

```python
# 推奨: astimezone() で変換
ts = datetime.datetime.fromisoformat(timestamp)
jst = ts.astimezone(rsudp.types.JST)

# 非推奨: 手動でオフセット追加
ts = datetime.datetime.fromisoformat(timestamp)
jst = ts + datetime.timedelta(hours=9)  # タイムゾーン情報が失われる
```

### isinstance() と Union 型

Python 3.10+ では `isinstance(x, Type1 | Type2)` が有効:

- タプル形式 `isinstance(x, (Type1, Type2))` と同等だが、より読みやすい
- このプロジェクトでは Union 型構文を使用してよい

```python
# Python 3.10+ では両方とも有効
isinstance(value, str | int)           # Union 型構文（推奨）
isinstance(value, (str, int))          # タプル形式（従来方式）
```

### コード重複の許容範囲

以下のケースは重複として扱わず、各箇所で明示的に記述する:

- クエリパラメータ取得（各エンドポイントで明示的に記述した方が可読性が高い）
- 2-3行程度の単純なパターン（共通化すると可読性が低下する）

```python
# 許容される重複: 各エンドポイントで明示的に取得
min_max_signal = flask.request.args.get("min_max_signal", type=float)
earthquake_only = flask.request.args.get("earthquake_only", "false").lower() == "true"
```

### 後方互換性コード

- `pyproject.toml` の `requires-python` を確認し、不要な互換性コードは削除
- Python 3.11+ では `datetime.fromisoformat()` が "Z" 接尾辞をサポート
- 古いバージョン向けの回避策は不要

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

## 開発ワークフロー規約

### タグ作成時の注意

タグを打つ際は、**CHANGELOG.md を必ず更新すること**。

- 新機能、バグ修正、破壊的変更などを記載
- セマンティックバージョニングに従ったタグ名を使用

### コミット時の注意

- 今回のセッションで作成し、プロジェクトが機能するのに必要なファイル以外は git add しないこと
- 気になる点がある場合は追加して良いか質問すること

### バグ修正の原則

- 憶測に基づいて修正しないこと
- 必ず原因を論理的に確定させた上で修正すること
- 「念のため」の修正でコードを複雑化させないこと

### コード修正時の確認事項

- 関連するテストも修正すること
- 関連するドキュメントも更新すること
- mypy, pyright, ty がパスすることを確認すること
