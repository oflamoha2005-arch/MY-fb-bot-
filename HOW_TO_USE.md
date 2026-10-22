# 📖 Complete Step-by-Step Guide: Facebook Group Lead Bot

Welcome to your **Facebook Group Lead & Traffic Bot**! This guide walks you through every single step to turn commenters on Facebook group posts into readers and buyers for your story e-book.

---

## 🎯 How It Works in 30 Seconds
1. You find a popular story post in an English Facebook group.
2. The bot extracts the profiles of all real people who commented on it.
3. The bot sends each person a unique, personalized DM offering your free chapter/sample.
4. They read your sample, get hooked, and buy your full story collection.

---

## 📋 Phase 1: Setup & Customization (Do This Once)

### 1. Put Your Book Link in `templates.txt`
* Open the file named `templates.txt` inside your bot folder.
* Look for:
  ```text
  https://your-book-link.com/free-sample
  ```
* Replace it with your actual link (e.g., Gumroad free sample, Google Drive PDF, Amazon Kindle preview, or BookFunnel).
* **Why Spintax?** The `{Hey|Hi|Hello}` syntax ensures that Facebook never sees the exact same message twice, protecting your account from spam filters.

---

## 🚀 How to Launch the Bot (New Desktop GUI)

Simply double-click **`start.bat`** (or run `py gui.py` in your terminal).
A sleek, modern **Dark-Mode Desktop Dashboard** will open with dedicated tabs:

1. 📢 **Auto-Poster Tab:** Paste Facebook group links, set story teasers, and automatically publish to groups every 4–6 minutes.
2. 🔍 **Comment Scraper Tab:** Paste any post URL to extract readers who commented into your database.
3. 💬 **Direct Messenger Tab:** Send personalized sample links to your scraped leads with human typing speed and anti-ban delays.
4. 📝 **Templates Tab:** Easily edit your DM and Story Post templates with instant Spintax random preview.
5. 📊 **Leads & Stats Tab:** View all extracted leads and open `leads.csv` directly in Excel.
6. 🔥 **Account Warmer Tab:** Standalone warm-up sessions (feed scrolling, watching reels, natural likes) to build trust scores.
7. 🔎 **Viral Post Spy Tab:** Scan groups/pages for the most viral story posts, ranked by reactions, comments, and viral score.
8. 🌍 **Tier-1 Lead Filter Tab:** Filter commenters and members by country (USA, UK, Canada, Australia) into `tier1_leads.csv`.
9. 🤝 **Friend Connector Tab:** Send safe, human-spaced friend requests (10-15/day) to target readers to build an engaged 5,000-friend buyer profile.
10. 🔐 **Login / Save Session:** One-click button to open Chrome, log into your account, and save your credentials permanently.

---

### Step 1: Login to Facebook (Option 1)
* Select **Option 1**. A real Chrome window will open.
* Log into your Facebook account normally (enter your email, password, and 2FA code if enabled).
* **Join 3 to 5 active story groups:**
  * Search keywords on Facebook:
    * `Horror Fiction Community`
    * `Short Story Readers`
    * `Dark Fiction & Thrillers`
    * `Indie Book Lovers`
    * `Creepypasta Stories`
* Once logged in, go back to the terminal window and press **Enter**.
* Your session is now saved locally! You won't have to log in again.

---

### Step 2: Find a High-Traffic Post
* Open Facebook in your browser and visit one of your story groups.
* Look for posts with high engagement (e.g., 30 to 100+ comments) where people discuss stories.
* **Get the post link:**
  * Click on the post's timestamp (e.g., "2 hrs ago") or click **Share** ➡️ **Copy Link**.
  * The link will look like:  
    `https://www.facebook.com/groups/123456789/posts/987654321/`

---

### Step 3: Scrape the Commenters (Option 2)
* Select **Option 2** in the bot menu.
* Paste the Facebook post link when prompted.
* Enter how many commenters you want to scrape (e.g., `30` or `50`).
* The bot will automatically:
  1. Open the post in Chrome.
  2. Switch to **All Comments**.
  3. Scroll down and expand hidden comments.
  4. Collect clean profile links of every commenter and save them into `data/leads.csv`.

---

### Step 4: Send Safe Direct Messages (Option 3)
* Select **Option 3** in the bot menu.
* It will show you how many leads are ready to be messaged.
* Enter how many messages to send in this batch:
  * **Recommended:** `10` to `15` messages per day.
* Confirm with `y`.
* The bot will:
  1. Open each lead's profile.
  2. Click the **Message** button.
  3. Type the personalized message letter-by-letter (mimicking human typing speed).
  4. Send the message.
  5. Wait a random safe delay of **90 to 180 seconds** before the next person.
  6. Automatically log the profile in `data/history.json` so no one ever receives a duplicate message.

---

## 🛡️ Anti-Ban Golden Rules (Keep Your Account 100% Safe)

1. **Daily Limit:** Keep it between **10 to 20 messages per day** per account. Slow and steady wins the race.
2. **Account Quality:** Use an account that has a profile photo, is at least a few months old, and has some normal activity.
3. **Never Hard Sell First:** Always offer the **free sample/first chapter** as a gift. Foreign readers love reading sample chapters and are much more likely to buy when they enjoy the first few pages.
4. **Respond to Replies:** When someone replies to your DM saying *"Thanks!"* or *"Looks interesting"*, reply to them manually like a real author! That human connection is what generates sales.
