# 🤖 Facebook Book Marketing Bot Suite (Enterprise Master Funnel v2.5)

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Playwright](https://img.shields.io/badge/Playwright-Chromium-green.svg)](https://playwright.dev/)
[![CustomTkinter](https://img.shields.io/badge/GUI-CustomTkinter%20Dark-orange.svg)](https://github.com/TomSchimansky/CustomTkinter)
[![Telegram](https://img.shields.io/badge/Alerts-Telegram%20Bot%20API-blue.svg)](https://core.telegram.org/bots/api)
[![Anti-Ban](https://img.shields.io/badge/Anti--Ban-Session%20Sandwich%20Stealth-red.svg)](#-anti-ban--stealth-engineering)

A high-performance, fully autonomous marketing engine and growth bot designed specifically for indie authors and publishers to promote English fiction and story e-books on Facebook. Built with persistent browser sessions, anti-ban stealth mechanics, multi-account rotation, global Tier-1 reader isolation, and real-time Telegram telemetry.

---

## 🌟 Key Capabilities & Architectural Upgrades

### 1. ⚡ 1-Click Daily Master Routine (`daily_orchestrator.py`)
Automates the entire daily marketing routine in a single click with zero manual supervision:
* **Phase 1 (Niche Warming):** 10 minutes of human feed scrolling, liking posts, and watching video clips.
* **Phase 2 & 3 (Scout & Filter):** Automatically finds the top viral story post in target groups, extracts commenters, and isolates readers living in Tier-1 countries.
* **Phase 4 (Multi-Account Outreach):** Rotates across healthy accounts with Session Sandwiches (90s pre-warm / 60s post-cool), delivers micro-engagements (❤️ Like before DM), public notification replies, conversational DMs, and sends targeted friend requests.
* **Phase 5 (Group Story Auto-Poster):** Publishes teaser chapters across groups with cover image attachments and multi-account load balancing.
* **Phase 6 (Telegram Telemetry):** Dispatches a full funnel performance report directly to your phone.

### 2. 📱 Telegram Emergency Alerts & Reporting (`telegram_notifier.py`)
Integrated directly with Telegram Bot API:
* **Live Checkpoint Screenshots:** If Facebook triggers a Captcha, checkpoint, or temporary block, the bot automatically captures a live browser screenshot and sends an emergency alert to your phone within seconds.
* **Campaign & Daily Summaries:** Receives instant notifications when group campaigns finish and daily funnel reports showing qualified leads harvested, DMs delivered, and group posts published.

### 3. 🌍 Global Tier-1 Geolocation Engine (1,934 Verified Locations)
Advanced regex word-boundary filter in `country_filter.py` backed by `data/tier1_locations.json`:
* **Americas & Anglo Sphere:** All 50 US states (+ state code abbreviations), 400+ US cities, UK counties & cities, Canada, Australia, New Zealand, Ireland.
* **High-Purchasing European Nations:** Germany, Netherlands, Sweden, Norway, Denmark, Switzerland, France, Spain, Portugal, Italy, Austria, Belgium, and Finland.
* **Dual-Spelling Intelligence:** Supports native accented characters and clean ASCII equivalents (e.g., `München` / `Munich`, `Zürich` / `Zurich`, `Malmö` / `Malmo`).

### 4. ❤️ Micro-Engagement & Zero-Link Conversational Funnel
* **❤️ Like Comment Before DM:** Clicks "Like" on the reader's comment first, triggering an instant mobile push notification (*"Author/Profile liked your comment"*). This primes the reader and raises message open rates by 40-50%.
* **Zero External Links:** Avoids Facebook's link spam filters by sending natural conversational copy that shares the **Book Title** and **Author Name**, prompting organic searches on Amazon and Goodreads that boost Amazon BSR rankings.

### 5. 📢 Multi-Account Group Story Auto-Poster
* **Permanent State Persistence:** Post text (`posts.txt`) and group queues (`data/poster_history.json`) persist across application restarts. Post content is only cleared when 100% of groups have been reached.
* **Cover Image Sync:** Synchronizes the selected book cover image between the Auto-Poster and Daily Tasks tabs via `data/poster_config.json`.
* **Zero Cooldown:** Daily group posting without artificial multi-day lockouts.

### 6. 🛡️ Anti-Ban & Stealth Engineering
* **Session Sandwich:** Wraps every outreach and posting session in a 90-second pre-warming and 60-second post-cooling human feed browse.
* **Auto-Skip Checkpoint Accounts:** Automatically checks `data/accounts_health.json` before opening browser sessions to skip flagged accounts and protect them from permanent bans.
* **Lead Deduplication Guard:** In-memory queue deduplication guarantees zero duplicate messages to the same reader.
* **Persistent Profiles:** Preserves real browser cookies and local storage in `profiles/account_X`.

---

## 🗄️ The 3-Databases Engine

| Database | File(s) | Function |
| :--- | :--- | :--- |
| **Database 1: Groups** | `groups.txt`, `data/spy_history.json` | Clean Facebook group URLs (one per line). Tracks scouted timestamps and yield. |
| **Database 2: Viral Posts** | `data/viral_posts.csv`, `data/scraped_posts_history.json` | Discovered high-engagement story discussions (&ge; 2 comments, &le; 3 months). Tracks completed scrapes to prevent redundant work. |
| **Database 3: Qualified Leads** | `data/tier1_leads.csv`, `data/history.json` | Fully qualified Tier-1 readers with location data and centralized outreach history. |
| **Database 4: Accounts Health** | `data/accounts_health.json` | Tracks daily DM quotas, friend requests, warmup minutes, and safety status per account. |

---

## 📁 Project Structure

```text
├── daily_orchestrator.py   # ⚡ Master Daily Funnel Coordinator (6-Phase Routine)
├── telegram_notifier.py    # 📱 Telegram Bot Alerting, Screenshots & Reports
├── country_filter.py       # 🌍 1,934 Tier-1 Locations Filtration Engine
├── auto_poster.py          # 📢 Multi-Account Group Story Auto-Poster
├── comment_replier.py      # 💬 Micro-Engagement (Like ❤️) & Public Comment Reply Engine
├── messenger.py            # ✉️ Safe Human-Spaced Direct Messenger
├── scraper.py              # 🔍 Post Comment Scraper & Lead Harvester
├── competitor_spy.py       # 🔎 Viral Post Discovery & Group Scout Engine
├── friend_connector.py     # 🤝 Targeted Friend Request Growth Engine
├── account_warmer.py       # 🔥 Organic Human Feed Browsing & Trust-Score Warmer
├── browser.py              # 🌐 Playwright Chromium Engine with Checkpoint Detection
├── config.py               # ⚙️ Global Paths, Fallbacks & Configuration
├── utils.py                # 🛠️ Shared Helpers, Health Tracking & Spintax Parser
├── gui.py                  # 🖥️ CustomTkinter Modern Dark-Themed Desktop Dashboard
├── start.bat               # 🚀 Quick Launcher for Windows Desktop
├── templates.txt           # 📝 Spintax Templates for Direct Outreach
├── posts.txt               # 📜 Current Active Story Post for Group Campaigns
├── groups.txt              # 📋 Target Facebook Group URLs (Clean Links)
├── reply_templates.json    # 💬 Spintax Templates for Comment Replies
└── data/                   # 💾 Centralized Databases & Tracking Storage
    ├── tier1_locations.json       # 1,934 Curated Tier-1 Locations
    ├── telegram_config.json       # Telegram Bot Credentials
    ├── accounts_health.json       # Health Status & Daily Action Quotas
    ├── poster_config.json         # Persistent Cover Image Path
    ├── poster_history.json        # Group Posting Progress & State
    ├── scraped_posts_history.json # Completed Scrapes Memory
    ├── tier1_leads.csv            # Qualified Tier-1 High-Intent Readers
    ├── viral_posts.csv            # Discovered Viral Posts
    └── history.json               # Centralized Cross-Account Outreach History
```

---

## 🚀 Quick Start Guide

### 1. Prerequisites
* Python 3.10 or higher installed on Windows.
* Playwright browsers installed:
  ```bash
  pip install -r requirements.txt
  playwright install chromium
  ```

### 2. Launch the Application
Double-click **`start.bat`** or run in your terminal:
```bash
py gui.py
```

### 3. Initial Setup
1. **Login to Accounts (Tab: Login):** Select `account_1`, click **Launch Browser for Login**, log into your Facebook account, and close the window to save the persistent session. Repeat for `account_2` and `account_3`.
2. **Add Target Groups:** Paste relevant Facebook story/book group URLs into `groups.txt` (or via the GUI).
3. **Configure Telegram Alerts:** Click **📱 Telegram Alerts** in the sidebar, input your Bot Token and Chat ID, and click **Test Alert**.
4. **Launch Daily Master Routine:** Navigate to the **⚡ Daily Tasks** tab, verify your settings, and click **Start Daily Master Routine**. The bot will autonomously execute the entire 6-phase marketing cycle.

---

## 🔒 Security & Privacy Notice
All Facebook session data, cookies, local storage profiles (`profiles/`), and personal lead records (`data/`) are strictly isolated and excluded via `.gitignore` to prevent any credentials or proprietary data from leaking to version control.
