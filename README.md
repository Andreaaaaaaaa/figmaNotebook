# Figma Update Monitor

This tool automatically fetches updates from Figma Release Notes and Blog, filters for core product updates, and sends notifications to an Enterprise WeChat (WeCom) group.

## Features
- **Sources**: Figma Release Notes (scraped), Figma Blog.
- **Filtering**: Excludes "pricing", "education", "student", "teacher" related updates.
- **Deduplication**: Uses `state.json` to track processed updates and prevent duplicates.
- **Daily Report**: Aggregates the top 5 latest updates into a single message.
- **Translation**: Automatically translates titles and summaries to Simplified Chinese.
- **Notifications**: Formatted Markdown messages to WeCom Webhook.

## Setup

1.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

2.  **Configuration**:
    Set the `WECOM_WEBHOOK_URL` environment variable.
    ```bash
    export WECOM_WEBHOOK_URL="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=YOUR_KEY"
    ```

3.  **Run Locally**:
    ```bash
    python3 main.py
    ```

## Deployment (GitHub Actions)

You can run this script automatically using GitHub Actions (free for public/private repos).

1.  Create a folder `.github/workflows` in your repository.
2.  Create a file `figma_monitor.yml` inside it with the following content:

```yaml
name: Figma Monitor

on:
  schedule:
    # Run daily at 10:00 AM Beijing Time (02:00 UTC)
    - cron: '0 2 * * *'
  workflow_dispatch: # Allow manual trigger

permissions:
  contents: write

jobs:
  run-monitor:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          # Important: Fetch full history if you want to commit state back, 
          # but for simple state tracking, we might need to commit the state.json back to the repo.
          # Alternatively, use a cache or external storage. 
          # For simplicity here, we will commit the state.json back.
          token: ${{ secrets.GITHUB_TOKEN }}

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.9'

      - name: Install dependencies
        run: |
          pip install -r figma_monitor/requirements.txt

      - name: Run Monitor
        env:
          WECOM_WEBHOOK_URL: ${{ secrets.WECOM_WEBHOOK_URL }}
        run: |
          cd figma_monitor
          python3 main.py

      - name: Commit State
        run: |
          git config --global user.name 'Figma Monitor Bot'
          git config --global user.email 'bot@noreply.github.com'
          git add figma_monitor/state.json
          git diff --quiet && git diff --staged --quiet || (git commit -m "Update state.json" && git push)
```

3.  **Add Secret**:
    Go to your GitHub Repo -> Settings -> Secrets and variables -> Actions.
    Add a new repository secret named `WECOM_WEBHOOK_URL` with your WeCom Webhook URL.

## Deployment (Local Cron)

To run on your local machine or server:

1.  Open crontab:
    ```bash
    crontab -e
    ```
2.  Add a line to run daily at 10:00 AM:
    ```bash
    0 10 * * * cd /Users/andreazhang/Desktop/new/figma_monitor && WECOM_WEBHOOK_URL="your_url" /usr/bin/python3 main.py >> monitor.log 2>&1
    ```
