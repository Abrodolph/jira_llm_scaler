# Apache Jira Scraping & Transformation Pipeline for LLM Training

This project is a two-part data pipeline built in Python. Its purpose is to scrape public issue data from Apache's Jira instance and transform it into a clean, structured dataset suitable for fine-tuning Large Language Models (LLMs).

## 🚀 Core Features

### Part 1: The Scraper (`scraper.py`)

- **Fault-Tolerant:** Automatically handles rate limits (`429`), server errors (`5xx`), and network timeouts with an exponential backoff retry system.
- **Resumable:** Uses a `checkpoint.json` file to save progress after every successful page. If the script is stopped or crashes, it can be restarted and will resume exactly where it left off.
- **Efficient:** Uses Python's `logging` module for structured logging and saves data scalably in `JSONL` format to handle millions of issues without high memory usage.
- **Polite:** Obeys a `time.sleep(1)` delay between requests to avoid overwhelming the public API.

### Part 2: The Transformer (`transform.py`)

- **Data Cleaning:** Automatically sanitizes all text data by removing HTML tags (with `BeautifulSoup`) and Jira-specific markup (with `regex`).
- **Anonymization:** Scrubs all text for potential PII, replacing emails and IP addresses with placeholders like `[EMAIL_REMOVED]`.
- **Derived Tasks:** Converts each raw issue into multiple "prompt/completion" pairs for LLM training, including:
  - Summarization
  - Question Answering (e.g., "What is the status?")
  - Classification (e.g., Priority, Issue Type)
- **Quality Control:** Automatically filters out duplicate tasks and drops "empty" or "meaningless" issues (those with no description or comments).

---

## 🛠️ How to Run This Project

### 1. Setup

First, set up the environment:

```bash
# Clone the repository
git clone [https://github.com/Abrodolph/jira_llm_scaler.git](https://github.com/Abrodolph/jira_llm_scaler.git)
cd jira_llm_scaler

# Create a Python virtual environment
# (The 'Jira' folder is the venv in this project)
python -m venv Jira

# Activate the virtual environment
# On Windows (PowerShell):
.\Jira\Scripts\activate

# On macOS/Linux:
# source Jira/bin/activate

# Install the required libraries
pip install -r requirements.txt
```

### 2. Run the Pipeline
The project is a two-step process.
#### Step 1: Run the Scraper 
This script will connect to the Apache Jira API and start scraping all issues from `SPARK`, `KAFKA`, and `HADOOP`. It will create `jira_corpus_raw.jsonl` as it runs.
```bash
python scraper.py
```
*(Note: This will take a very long time, as it's scraping thousands of issues politely.)*
#### Step 2: Run the Transformer
This script reads the raw data and creates the clean, LLM-ready dataset.
```bash
python transform.py
```
This will read `jira_corpus_raw.jsonl` and create `jira_corpus_llm_ready.jsonl`.

## 📂 Project Structure
```bash
Jira_Scraper/
│
├── .gitignore         # Tells Git which files to ignore (logs, venv, data)
├── requirements.txt   # All Python dependencies
│
├── scraper.py         # Script 1: Fetches and saves raw data
├── transform.py       # Script 2: Cleans and transforms data for LLMs
│
├── sample_raw.jsonl   # A "BEFORE" sample of the raw scraped data
└── sample_llm.jsonl   # An "AFTER" sample of the final, clean LLM-ready data
```
*(Runtime files like `scraper.log`, `transform.log`, and `checkpoint.json` will be created when the scripts are run.)*

## 📊 Data Samples
 `sample_raw.jsonl` (Before)
This file shows the raw, nested JSON data as it comes directly from the Jira API.  
`sample_llm.jsonl` (After)

This file shows the final, clean, LLM-ready training data. Note how each raw issue has been transformed into multiple, flat "prompt/completion" pairs.
