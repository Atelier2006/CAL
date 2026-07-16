# キャリアセンター相談予約システム（Flask統合版）

`html_20260708`（Flask雛形）と `login/`（Google認証）を統合し、`docs/作業指示書.md`
のコア機能を実装した動作する予約システム。学生の申請 → 管理者の承認 → 確定/キャンセル
までの一連のフローが SQLite 上で通る。

## 起動方法

```bash
cd html_20260708
pip install flask
# 本番Google認証を使う場合のみ: pip install google-auth
python app.py            # http://127.0.0.1:5000
```

起動時に `career.db` が無ければ `schema.sql` + シードデータ（db.py）で自動生成される。
作り直したいときは `career.db` を削除して再起動。

## ログイン

- 学生: `/`（トップ）… 学校Googleアカウント（本番）／**デモ用ログイン**（学生を選択）
- 管理者: `/admin-login` … 管理者Googleアカウント（本番）／**デモ用 管理者ログイン**

> Googleクレデンシャル未設定でも動作確認できるよう、DEVログイン（`/dev-login`）を併設。
> 本番の Google Identity Services 経路（`/login`, `/login2`）も実装済み（`google-auth` が必要）。

デモ用学生: `24AH9999 東京 電子` ほか。管理者は「デモ用 管理者ログイン」ボタン。

## 実装済み（作業指示書との対応）

| 区分 | 項目 | 実装 |
|---|---|---|
| A-1 | ログイン画面・権限分岐・アクセス制御・ログアウト | ✅ login.html/login2.html + role_required |
| A-2 | Flask基盤（app.py に統合、共通サイドバー部分テンプレート） | ✅ |
| A-3 | SQLite（users/counselors/reservations/announcements/inquiries/notifications/settings） | ✅ schema.sql + seed |
| B-1 | 新規予約フロー（空き枠カレンダー→フォーム→申請） | ✅ DB連動・乱数廃止・枠引継ぎ |
| B-2 | 予約確認／キャンセル→再予約／過去タブ／検索 | ✅ |
| B-3 | お知らせ（DB連動・掲載期限フィルタ・検索） | ✅ |
| B-4 | マイページ（次回予約カード・セッション情報表示） | ✅ |
| B-5 | 求人サイト遷移（仮URL §6-2） | ✅ home.html |
| C-2 | 相談員管理（全面作り直し・統計・登録/編集/休止） | ✅ |
| C-4 | 管理ダッシュボード/予約管理(承認＋場所必須/却下)/お知らせCRUD/設定保存 | ✅ |
| D-3 | 予約ルール（4枠・営業日3日前締切・1日上限・同日重複防止・枠競合防止） | ✅ |
| E-1 | ロールベースアクセス制御・パラメータ化クエリ・Jinja自動エスケープ | ✅（基本） |
| E-3 | 誤配置ファイル整理・管理画面CSSを common_a.css に集約・データ名寄せ | ✅ |

## スコープ外／フェーズ2（作業指示書の決定に準拠）

- **通知（D-1）**: フェーズ2。`notifications` テーブルのみ先行作成。設定画面のトグルは「準備中」で無効化。
- **Google Calendar連携（D-2）**: 未実装（バックログ）。
- **学生管理（C-1）／レポート（C-3）**: スコープ外決定のため未作成（サイドバーからも除外済み）。
- **CSV出力（D-4）／セミナー等アンケート（C-3満足度）**: 未実装（バックログ）。

## ディレクトリ

```
html_20260708/
├─ app.py            # 統合アプリ（認証・ルート・予約ルール・各アクション）
├─ db.py             # DB接続・初期化・シード・設定ヘルパ
├─ schema.sql        # テーブル定義
├─ static/           # common.css(学生) / common_a.css(管理・共通部品) / reserve_form.css
└─ templates/
   ├─ login.html, login2.html
   ├─ user/  home, info, mypage, check, reserve_c, reserve_form
   └─ admin/ _sidebar(部分), dashboard, reservation, notice, staff, setting
```

## 備考（統合時に判明した「変わっていた点」）

- 元の `templates/admin/` に置かれていた `check / reserve_c / reserve_form` は
  学生用画面のため `templates/user/` へ移動。
- `login.py` が参照する学生用 `login.html` が欠落していたため新規作成。
- `templates詳細.txt`・重複ファイル（check copy 等）は整理・統合。
- 旧プロトタイプ `html_20260702/` は参照用として残置。
