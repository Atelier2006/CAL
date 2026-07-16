-- キャリアセンター相談予約システム スキーマ (SQLite)
-- 作業指示書 A-3 に基づく。UI必須の counselors / settings を追加。

DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS counselors;
DROP TABLE IF EXISTS reservations;
DROP TABLE IF EXISTS announcements;
DROP TABLE IF EXISTS inquiries;
DROP TABLE IF EXISTS notifications;
DROP TABLE IF EXISTS settings;

-- 学生ユーザー（学籍番号を主キーに）。role で管理者も収容
CREATE TABLE users (
    user_id      TEXT PRIMARY KEY,          -- 学籍番号 (例 24AH9999)
    name         TEXT NOT NULL,
    email        TEXT,
    department   TEXT,                       -- 学科
    grade        TEXT,                       -- 学年
    role         TEXT NOT NULL DEFAULT 'student'  -- student / admin
);

-- 相談員
CREATE TABLE counselors (
    id        TEXT PRIMARY KEY,             -- C-2026-001
    name      TEXT NOT NULL,
    field     TEXT,                          -- 相談分野
    work_days TEXT,                          -- 対応曜日 (例 月・水・金)
    email     TEXT,
    tel       TEXT,
    status    TEXT NOT NULL DEFAULT '対応中' -- 対応中 / 休止中
);

-- 予約管理
CREATE TABLE reservations (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id   TEXT NOT NULL,
    counselor_id TEXT,
    date         TEXT NOT NULL,              -- YYYY-MM-DD
    slot         TEXT NOT NULL,             -- 午前/昼/午後/放課後
    rtype        TEXT,                       -- 相談/添削/面接/その他
    content      TEXT,
    location     TEXT,                       -- 承認時に管理者が手入力 (§6-1)
    status       TEXT NOT NULL DEFAULT 'pending', -- pending/confirmed/cancelled/rejected
    created_at   TEXT NOT NULL,
    FOREIGN KEY (student_id)   REFERENCES users(user_id),
    FOREIGN KEY (counselor_id) REFERENCES counselors(id)
);

-- お知らせ（掲載期限 expiration_date を追加）
CREATE TABLE announcements (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    title        TEXT NOT NULL,
    content      TEXT,
    category     TEXT,                       -- 重要/イベント/その他
    publish_date TEXT,
    expiration_date TEXT,
    status       TEXT NOT NULL DEFAULT '公開中' -- 公開中/下書き/終了
);

-- 質問Q&A
CREATE TABLE inquiries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id      TEXT NOT NULL,
    question_text   TEXT NOT NULL,
    answer_text     TEXT,
    response_status TEXT NOT NULL DEFAULT 'waiting', -- waiting/answered
    created_at      TEXT NOT NULL
);

-- 通知（フェーズ2。テーブルのみ先行作成 §6-7 / A-3）
CREATE TABLE notifications (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    recipient_id TEXT,
    message_text TEXT,
    type         TEXT,                       -- reservation_update / new_announcement
    is_read      INTEGER NOT NULL DEFAULT 0,
    created_at   TEXT
);

-- システム設定（設定画面と予約ロジックが共有）
CREATE TABLE settings (
    key   TEXT PRIMARY KEY,
    value TEXT
);
