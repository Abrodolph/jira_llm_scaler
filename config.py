# --- Configuration File ---

# 1. Projects to Scrape
PROJECTS_TO_FETCH = ["SPARK", "KAFKA", "HADOOP"]

# 2. API & Scraper Settings
BASE_URL = "https://issues.apache.org/jira/rest/api/2/search"
REQUEST_FIELDS = "summary,description,comment,status,priority,assignee,labels,created,updated,issuetype,reporter"
PAGE_SIZE = 100
MAX_RETRIES = 5
NETWORK_TIMEOUT = 30 # Seconds

# 3. Filepaths (This is the most important part)
#    Both scripts will read from these constants.
CHECKPOINT_FILE = 'checkpoint.json'
RAW_DATA_FILE = 'jira_corpus_raw.jsonl'
LLM_DATA_FILE = 'jira_corpus_llm_ready.jsonl'