# Changelog

このプロジェクトの注目すべき変更点をすべてこのファイルに記載します。

このファイルのフォーマットは [Keep a Changelog](https://keepachangelog.com/ja/1.1.0/) に基づいており、
このプロジェクトは [Semantic Versioning](https://semver.org/spec/v2.0.0.html) に準拠しています。

## [Unreleased]

## [0.1.1] - 2026-01-24

### 🐛 Fixed

- hatch-vcs ビルドフックの問題を修正
- Docker ビルド時の fallback-version を追加

## [0.1.0] - 2026-01-23

### ✨ Added

- Raspberry Shake からの UDP データ受信とリアルタイム可視化
- 地震検出時の波形スクリーンショット自動保存
- 気象庁 API からの地震情報定期収集（1時間間隔）
- スクリーンショットと地震情報の照合・フィルタリング
- 信号強度（STA/LTA）によるフィルタリング
- React ベースの Web UI
- スクリーンショットの自動リロード機能
- 最大振幅フィルタのスライダー（1000単位）
- 仮想スクロールによるファイルリストのパフォーマンス改善
- Docker / Kubernetes 対応
- CI/CD パイプライン（GitLab）

### 🔄 Changed

- CSS フレームワークを Bulma から Tailwind CSS v4 に移行

[Unreleased]: https://github.com/kimata/rsudp/compare/v0.1.1...HEAD
[0.1.1]: https://github.com/kimata/rsudp/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/kimata/rsudp/releases/tag/v0.1.0
