-- ==============================================================
-- Discord Bot - Full Database Schema
-- Engine : SQLite (aiosqlite)
-- Version: 1.0.0
-- ==============================================================

PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;
PRAGMA synchronous = NORMAL;
PRAGMA cache_size = -64000;   -- 64 MB page cache
PRAGMA temp_store = MEMORY;

-- ==============================================================
-- GUILDS (server settings)
-- ==============================================================
CREATE TABLE IF NOT EXISTS guilds (
    guild_id            TEXT PRIMARY KEY,
    prefix              TEXT NOT NULL DEFAULT '!',
    language            TEXT NOT NULL DEFAULT 'en',

    -- Role IDs
    mod_role_id         TEXT,
    admin_role_id       TEXT,
    manager_role_id     TEXT,
    mute_role_id        TEXT,
    verify_role_id      TEXT,
    autorole_id         TEXT,

    -- Channel IDs
    log_channel_id      TEXT,
    mod_log_channel_id  TEXT,
    welcome_channel_id  TEXT,
    leave_channel_id    TEXT,
    verify_channel_id   TEXT,
    ticket_category_id  TEXT,
    ticket_log_id       TEXT,
    count_channel_id    TEXT,
    music_channel_id    TEXT,

    -- Welcome / Leave messages
    welcome_msg         TEXT DEFAULT 'Welcome {user} to {server}!',
    leave_msg           TEXT DEFAULT '{user} has left {server}.',

    -- Counting game
    count_current       INTEGER DEFAULT 0,
    count_last_user     TEXT,
    count_record        INTEGER DEFAULT 0,

    -- Toggles
    antispam_enabled    INTEGER DEFAULT 0,
    antilink_enabled    INTEGER DEFAULT 0,
    antilog_enabled     INTEGER DEFAULT 0,
    automod_enabled     INTEGER DEFAULT 0,
    leveling_enabled    INTEGER DEFAULT 1,

    created_at          TEXT DEFAULT (datetime('now')),
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- ==============================================================
-- GUILD COMMAND SETTINGS
-- ==============================================================
CREATE TABLE IF NOT EXISTS disabled_commands (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    command_name    TEXT NOT NULL,
    disabled_by     TEXT NOT NULL,
    disabled_at     TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, command_name),
    FOREIGN KEY (guild_id) REFERENCES guilds(guild_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ignored_channels (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    channel_id  TEXT NOT NULL,
    ignored_by  TEXT NOT NULL,
    UNIQUE(guild_id, channel_id)
);

CREATE TABLE IF NOT EXISTS ignored_roles (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    role_id     TEXT NOT NULL,
    ignored_by  TEXT NOT NULL,
    UNIQUE(guild_id, role_id)
);

CREATE TABLE IF NOT EXISTS ignored_users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    ignored_by  TEXT NOT NULL,
    UNIQUE(guild_id, user_id)
);

-- ==============================================================
-- CUSTOM COMMANDS
-- ==============================================================
CREATE TABLE IF NOT EXISTS custom_commands (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    name        TEXT NOT NULL,
    response    TEXT NOT NULL,
    embed       INTEGER DEFAULT 0,
    creator_id  TEXT NOT NULL,
    uses        INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now')),
    updated_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, name)
);

-- ==============================================================
-- MODERATION - Cases
-- ==============================================================
CREATE TABLE IF NOT EXISTS mod_cases (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id     INTEGER NOT NULL,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    user_tag    TEXT NOT NULL,
    mod_id      TEXT NOT NULL,
    mod_tag     TEXT NOT NULL,
    action      TEXT NOT NULL,    -- kick | ban | softban | mute | unmute | warn |
                                  -- timeout | untimeout | voiceban | deafen | undeafen
    reason      TEXT DEFAULT 'No reason provided',
    duration    TEXT,             -- human readable: "1h", "7d"
    expires_at  TEXT,
    active      INTEGER DEFAULT 1,
    log_msg_id  TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, case_id)
);

CREATE INDEX IF NOT EXISTS idx_cases_guild   ON mod_cases(guild_id);
CREATE INDEX IF NOT EXISTS idx_cases_user    ON mod_cases(guild_id, user_id);
CREATE INDEX IF NOT EXISTS idx_cases_active  ON mod_cases(guild_id, active);

-- ==============================================================
-- MODERATION - Warnings
-- ==============================================================
CREATE TABLE IF NOT EXISTS warnings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    mod_id      TEXT NOT NULL,
    mod_tag     TEXT NOT NULL,
    reason      TEXT DEFAULT 'No reason provided',
    case_id     INTEGER,
    active      INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_warnings_guild_user ON warnings(guild_id, user_id, active);

-- ==============================================================
-- MODERATION - Mutes
-- ==============================================================
CREATE TABLE IF NOT EXISTS mutes (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    mod_id      TEXT NOT NULL,
    reason      TEXT,
    expires_at  TEXT,
    active      INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, user_id)
);

-- ==============================================================
-- MODERATION - Bans (persistent tracking)
-- ==============================================================
CREATE TABLE IF NOT EXISTS bans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    user_tag    TEXT,
    mod_id      TEXT NOT NULL,
    reason      TEXT,
    expires_at  TEXT,
    active      INTEGER DEFAULT 1,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, user_id)
);

-- ==============================================================
-- MODERATION - Voice Bans
-- ==============================================================
CREATE TABLE IF NOT EXISTS voice_bans (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    mod_id      TEXT NOT NULL,
    reason      TEXT,
    created_at  TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, user_id)
);

-- ==============================================================
-- AUTOMOD CONFIG
-- ==============================================================
CREATE TABLE IF NOT EXISTS automod_config (
    guild_id            TEXT PRIMARY KEY,
    anti_spam           INTEGER DEFAULT 0,
    spam_threshold      INTEGER DEFAULT 5,
    spam_interval_ms    INTEGER DEFAULT 5000,
    anti_link           INTEGER DEFAULT 0,
    allowed_links       TEXT DEFAULT '[]',     -- JSON array
    anti_caps           INTEGER DEFAULT 0,
    caps_threshold      INTEGER DEFAULT 70,    -- percentage
    anti_mention        INTEGER DEFAULT 0,
    mention_threshold   INTEGER DEFAULT 5,
    anti_emoji          INTEGER DEFAULT 0,
    emoji_threshold     INTEGER DEFAULT 10,
    anti_newline        INTEGER DEFAULT 0,
    newline_threshold   INTEGER DEFAULT 10,
    warn_on_trigger     INTEGER DEFAULT 1,
    delete_on_trigger   INTEGER DEFAULT 1,
    log_channel_id      TEXT,
    updated_at          TEXT DEFAULT (datetime('now'))
);

-- ==============================================================
-- WORD FILTER
-- ==============================================================
CREATE TABLE IF NOT EXISTS word_filters (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    word        TEXT NOT NULL,
    added_by    TEXT NOT NULL,
    added_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, word)
);

-- ==============================================================
-- BLACKLIST / WHITELIST
-- ==============================================================
CREATE TABLE IF NOT EXISTS blacklist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('user','role','channel','word')),
    reason      TEXT,
    added_by    TEXT NOT NULL,
    added_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, target_id, target_type)
);

CREATE TABLE IF NOT EXISTS whitelist (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    target_id   TEXT NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('user','role','channel')),
    added_by    TEXT NOT NULL,
    added_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, target_id, target_type)
);

-- ==============================================================
-- LEVELING SYSTEM
-- ==============================================================
CREATE TABLE IF NOT EXISTS levels (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    xp              INTEGER DEFAULT 0,
    level           INTEGER DEFAULT 0,
    total_messages  INTEGER DEFAULT 0,
    voice_minutes   INTEGER DEFAULT 0,
    last_xp_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_levels_xp ON levels(guild_id, xp DESC);

CREATE TABLE IF NOT EXISTS rank_rewards (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    level       INTEGER NOT NULL,
    role_id     TEXT NOT NULL,
    added_by    TEXT NOT NULL,
    added_at    TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, level)
);

CREATE TABLE IF NOT EXISTS level_config (
    guild_id            TEXT PRIMARY KEY,
    enabled             INTEGER DEFAULT 1,
    xp_min              INTEGER DEFAULT 10,
    xp_max              INTEGER DEFAULT 25,
    xp_cooldown_sec     INTEGER DEFAULT 60,
    xp_voice_per_min    INTEGER DEFAULT 5,
    level_up_channel    TEXT,
    level_up_msg        TEXT DEFAULT 'GG {user}, you hit level **{level}**! 🎉',
    stack_rewards       INTEGER DEFAULT 0,
    no_xp_roles         TEXT DEFAULT '[]',
    no_xp_channels      TEXT DEFAULT '[]'
);

-- ==============================================================
-- TICKET SYSTEM
-- ==============================================================
CREATE TABLE IF NOT EXISTS tickets (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ticket_id       INTEGER NOT NULL,
    guild_id        TEXT NOT NULL,
    channel_id      TEXT NOT NULL,
    creator_id      TEXT NOT NULL,
    assigned_to     TEXT,
    topic           TEXT DEFAULT 'Support',
    status          TEXT DEFAULT 'open' CHECK(status IN ('open','closed','deleted')),
    close_reason    TEXT,
    closed_by       TEXT,
    transcript_url  TEXT,
    created_at      TEXT DEFAULT (datetime('now')),
    closed_at       TEXT,
    UNIQUE(guild_id, ticket_id)
);

CREATE TABLE IF NOT EXISTS ticket_config (
    guild_id        TEXT PRIMARY KEY,
    enabled         INTEGER DEFAULT 1,
    category_id     TEXT,
    log_channel_id  TEXT,
    support_role_id TEXT,
    panel_msg_id    TEXT,
    max_per_user    INTEGER DEFAULT 1,
    welcome_msg     TEXT DEFAULT 'Hey {user}, staff will be with you shortly!'
);

-- ==============================================================
-- GIVEAWAY SYSTEM
-- ==============================================================
CREATE TABLE IF NOT EXISTS giveaways (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    channel_id      TEXT NOT NULL,
    message_id      TEXT NOT NULL UNIQUE,
    host_id         TEXT NOT NULL,
    prize           TEXT NOT NULL,
    winners_count   INTEGER DEFAULT 1,
    entries         TEXT DEFAULT '[]',      -- JSON array of user IDs
    winners         TEXT DEFAULT '[]',      -- JSON array after end
    required_role   TEXT,
    min_level       INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'active' CHECK(status IN ('active','ended','cancelled')),
    ends_at         TEXT NOT NULL,
    ended_at        TEXT,
    created_at      TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_giveaways_active ON giveaways(guild_id, status, ends_at);

-- ==============================================================
-- POLLS
-- ==============================================================
CREATE TABLE IF NOT EXISTS polls (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    channel_id  TEXT NOT NULL,
    message_id  TEXT NOT NULL UNIQUE,
    creator_id  TEXT NOT NULL,
    question    TEXT NOT NULL,
    options     TEXT NOT NULL,     -- JSON: [{"emoji":"1️⃣","text":"Yes","votes":[]}]
    multi_vote  INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'active' CHECK(status IN ('active','ended')),
    ends_at     TEXT,
    ended_at    TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ==============================================================
-- REMINDERS
-- ==============================================================
CREATE TABLE IF NOT EXISTS reminders (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    guild_id    TEXT,
    channel_id  TEXT,
    reminder    TEXT NOT NULL,
    remind_at   TEXT NOT NULL,
    sent        INTEGER DEFAULT 0,
    created_at  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(remind_at, sent);

-- ==============================================================
-- AFK SYSTEM
-- ==============================================================
CREATE TABLE IF NOT EXISTS afk (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    reason      TEXT DEFAULT 'AFK',
    since       TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, user_id)
);

-- ==============================================================
-- MUSIC STATS
-- ==============================================================
CREATE TABLE IF NOT EXISTS music_stats (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    user_id     TEXT NOT NULL,
    track_title TEXT NOT NULL,
    track_url   TEXT,
    duration_s  INTEGER DEFAULT 0,
    played_at   TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS music_config (
    guild_id        TEXT PRIMARY KEY,
    dj_role_id      TEXT,
    dj_only         INTEGER DEFAULT 0,
    default_volume  INTEGER DEFAULT 100,
    max_queue       INTEGER DEFAULT 500,
    vote_skip_pct   INTEGER DEFAULT 50,
    auto_leave_sec  INTEGER DEFAULT 300,
    channel_id      TEXT
);

-- ==============================================================
-- VERIFY SYSTEM
-- ==============================================================
CREATE TABLE IF NOT EXISTS verify_config (
    guild_id        TEXT PRIMARY KEY,
    enabled         INTEGER DEFAULT 0,
    channel_id      TEXT,
    role_id         TEXT,
    panel_msg_id    TEXT,
    verify_type     TEXT DEFAULT 'button' CHECK(verify_type IN ('button','captcha','react')),
    welcome_dm      INTEGER DEFAULT 1,
    welcome_msg     TEXT DEFAULT 'You have been verified in {server}!'
);

-- ==============================================================
-- INVITE TRACKER
-- ==============================================================
CREATE TABLE IF NOT EXISTS invite_tracker (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    inviter_id      TEXT NOT NULL,
    invite_code     TEXT NOT NULL,
    uses            INTEGER DEFAULT 0,
    regular         INTEGER DEFAULT 0,
    left            INTEGER DEFAULT 0,
    fake            INTEGER DEFAULT 0,
    updated_at      TEXT DEFAULT (datetime('now')),
    UNIQUE(guild_id, invite_code)
);

CREATE TABLE IF NOT EXISTS invite_joins (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    user_id         TEXT NOT NULL,
    inviter_id      TEXT,
    invite_code     TEXT,
    joined_at       TEXT DEFAULT (datetime('now'))
);

-- ==============================================================
-- STARBOARD  (bonus)
-- ==============================================================
CREATE TABLE IF NOT EXISTS starboard_config (
    guild_id        TEXT PRIMARY KEY,
    enabled         INTEGER DEFAULT 0,
    channel_id      TEXT,
    threshold       INTEGER DEFAULT 3,
    emoji           TEXT DEFAULT '⭐',
    self_star       INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS starboard_entries (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id        TEXT NOT NULL,
    original_msg_id TEXT NOT NULL UNIQUE,
    starboard_msg_id TEXT,
    channel_id      TEXT NOT NULL,
    author_id       TEXT NOT NULL,
    stars           INTEGER DEFAULT 0,
    created_at      TEXT DEFAULT (datetime('now'))
);

-- ==============================================================
-- BACKUPS METADATA
-- ==============================================================
CREATE TABLE IF NOT EXISTS backups (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    TEXT NOT NULL,
    backup_id   TEXT NOT NULL UNIQUE,
    created_by  TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    size_bytes  INTEGER,
    note        TEXT,
    created_at  TEXT DEFAULT (datetime('now'))
);

-- ==============================================================
-- BOT STATS (uptime, command usage)
-- ==============================================================
CREATE TABLE IF NOT EXISTS command_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    command_name    TEXT NOT NULL,
    guild_id        TEXT,
    user_id         TEXT NOT NULL,
    used_at         TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_cmd_stats_name ON command_stats(command_name);

CREATE TABLE IF NOT EXISTS bot_stats (
    id              INTEGER PRIMARY KEY,
    started_at      TEXT DEFAULT (datetime('now')),
    commands_run    INTEGER DEFAULT 0,
    messages_seen   INTEGER DEFAULT 0,
    guilds_peak     INTEGER DEFAULT 0
);

INSERT OR IGNORE INTO bot_stats(id) VALUES(1);

-- ==============================================================
-- TRIGGERS - auto update timestamps
-- ==============================================================
CREATE TRIGGER IF NOT EXISTS trg_guilds_updated
AFTER UPDATE ON guilds
BEGIN
    UPDATE guilds SET updated_at = datetime('now') WHERE guild_id = NEW.guild_id;
END;

CREATE TRIGGER IF NOT EXISTS trg_custom_commands_updated
AFTER UPDATE ON custom_commands
BEGIN
    UPDATE custom_commands SET updated_at = datetime('now') WHERE id = NEW.id;
END;
