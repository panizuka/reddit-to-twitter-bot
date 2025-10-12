# 🤖 reddit-to-twitter-bot

[![Python Version](https://img.shields.io/badge/python-3.14-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python bot to automatically post top media from a Reddit multireddit to a Twitter account. It fetches images, GIFs, and videos and posts them with proper attribution and hashtags.

## Key Features

-   ✅ **Automated Content Sourcing**: Fetches the hottest submissions from a specified Reddit multireddit.
-   🖼️ **Multi-Format Support**: Handles single images, galleries, GIFs, and videos.
-   🔊 **High-Quality Media**: Intelligently selects the best available quality for both video and audio streams.
-   🐦 **Automatic Tweeting**: Posts the fetched content to a Twitter account using the v1.1 (for media upload) and v2 (for tweeting) APIs.
-   ✂️ **Smart Text Handling**: Automatically truncates post titles to fit within Twitter's character limit while preserving hashtags and credits.
-   🧹 **Self-Cleaning**: Deletes downloaded media files after a successful post to conserve disk space.
-   **(Optional)** **Tweet Management**: Includes a script to delete old tweets that don't meet a certain "like" threshold.

## Prerequisites

Before you begin, ensure you have the following:
-   Python 3.14+ (Developed and tested on 3.14.0)
-   Git
-   **FFmpeg**: Required for processing videos with audio.
-   Developer accounts and API credentials for both **Reddit** and **Twitter**.

## Installation & Configuration

Follow these steps to get your bot up and running. It is **highly recommended** to use a Python virtual environment.

**1. Clone the Repository**
```bash
git clone https://github.com/panihabb/reddit-to-twitter-bot.git
cd reddit-to-twitter-bot
```

**2. Install FFmpeg**

This bot uses **FFmpeg** to merge video and audio files downloaded from Reddit. It must be installed and accessible from your system's command line.

1.  Download a pre-compiled build of FFmpeg from the [official website](https://ffmpeg.org/download.html) (for Windows, the builds from [Gyan.dev](https://www.gyan.dev/ffmpeg/builds/) are recommended).
2.  Extract the archive to a permanent location on your computer (e.g., `C:\ffmpeg`).
3.  **Add the `bin` directory** from your FFmpeg installation (e.g., `C:\ffmpeg\bin`) to your system's **PATH environment variable**. This is a critical step that allows the script to find the `ffmpeg` executable.
4.  To verify the installation, open a **new** terminal window and run the following command:
    ```bash
    ffmpeg -version
    ```
    You should see version information printed to the console. If you see an error like "command not found", your PATH is not configured correctly.

**3. Create and Activate a Virtual Environment**

*   On **Windows**:
    ```bash
    python -m venv venv
    .\venv\Scripts\activate
    ```
*   On **macOS / Linux**:
    ```bash
    python3 -m venv venv
    source venv/bin/activate
    ```

**4. Install Python Dependencies**
Install all the required Python libraries from the `requirements.txt` file.
```bash
pip install -r requirements.txt
```

**5. Configure Environment Variables**
This project uses a `.env` file to securely manage API keys. Create a file named `.env` in the root of the project directory and add your credentials.

You can use the `.env.example` as a template:
```ini
# .env.example

#== Reddit API Credentials ==#
# Create an app here: https://www.reddit.com/prefs/apps
REDDIT_CLIENT_ID="your_reddit_client_id"
REDDIT_CLIENT_SECRET="your_reddit_client_secret"
REDDIT_USER_AGENT="A custom user agent (e.g., MyBot/0.1 by u/YourUsername)"
REDDIT_USERNAME="your_reddit_username"
REDDIT_PASSWORD="your_reddit_password"

#== Twitter API Credentials ==#
# Create an app here: https://developer.twitter.com/
# Make sure your app has "Read and Write" permissions.
TWITTER_API_KEY="your_twitter_api_key"
TWITTER_API_SECRET="your_twitter_api_secret"
TWITTER_ACCESS_TOKEN="your_twitter_access_token"
TWITTER_ACCESS_SECRET="your_twitter_access_secret"
TWITTER_USER_NAME="YourTwitterUsername" # Without the @
```

## Usage

**1. To Post Content from Reddit to Twitter**
Run the main script. The bot will find a valid post, download the media, and tweet it.
```bash
python main.py
```

**2. To Delete Old Tweets**
Run the `delete_tweets.py` script. You can customize the `favorite_threshold` and `days` parameters directly in the `if __name__ == '__main__':` block of the script.

> **⚠️ Important Note on `delete_tweets.py`**
> Due to recent and ongoing changes to the Twitter API, access to endpoints required for fetching and deleting tweets may be heavily restricted or unavailable on the free tier. This script may not function as expected without paid access to the Twitter API.

```bash
python delete_tweets.py
```

### Automation

For a truly automated experience, you can schedule these scripts to run periodically.

-   On **Linux/macOS**, you can use `cron`.
-   On **Windows**, you can use the **Task Scheduler**.

## Project Structure

-   **`main.py`**: The main entry point of the application.
-   **`reddit.py`**: Handles all interactions with the Reddit API.
-   **`twitter.py`**: Manages all interactions with the Twitter API.
-   **`delete_tweets.py`**: An optional utility script for account maintenance.
-   **`requirements.txt`**: A list of all Python libraries required for the project.
-   **`.env`**: (You create this) Stores all your secret API keys and credentials.
-   **`/images`**: A temporary directory used to store media files.

## Contributing

Contributions are welcome! If you have a feature request, a bug report, or want to improve the code, please feel free to open an issue or submit a pull request.

## License

This project is licensed under the MIT License. See the `LICENSE` file for more details.