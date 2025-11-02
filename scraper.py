import requests
import json
import time
import os
import logging  # <-- NEW: Import logging

# --- Setup Professional Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraper.log"),  # Log to a file
        logging.StreamHandler()              # Also log to the console
    ]
)

# --- Configuration Constants ---
BASE_URL = "https://issues.apache.org/jira/rest/api/2/search"
REQUEST_FIELDS = "summary,description,comment,status,priority,assignee,labels,created,updated,issuetype,reporter"
PAGE_SIZE = 100
PROJECTS_TO_FETCH = ["SPARK", "KAFKA", "HADOOP"]
CHECKPOINT_FILE = 'checkpoint.json'
OUTPUT_FILE = 'jira_corpus_raw.jsonl'
MAX_RETRIES = 5
NETWORK_TIMEOUT = 30 # Seconds


class JiraScraper:
    """
    A class to scrape, transform, and save Jira issues,
    with checkpointing and error handling.
    """
    
    def __init__(self, projects, base_url, fields, output_file, checkpoint_file):
        self.projects_to_fetch = projects
        self.base_url = base_url
        self.request_fields = fields
        self.output_file = output_file
        self.checkpoint_file = checkpoint_file
        self.checkpoint_data = self._load_checkpoint()

    def _load_checkpoint(self):
        """Loads the checkpoint file or creates a new one."""
        if not os.path.exists(self.checkpoint_file):
            logging.info("No checkpoint file found. Creating a new one.")
            return {project: 0 for project in self.projects_to_fetch}
        
        try:
            with open(self.checkpoint_file, 'r') as f:
                checkpoint_data = json.load(f)
                # Ensure all projects from config are in the checkpoint
                for project in self.projects_to_fetch:
                    if project not in checkpoint_data:
                        checkpoint_data[project] = 0
                logging.info(f"Checkpoint loaded: {checkpoint_data}")
                return checkpoint_data
                
        except json.JSONDecodeError:
            logging.warning("Checkpoint file corrupted. Starting from scratch.")
            return {project: 0 for project in self.projects_to_fetch}

    def _save_checkpoint(self):
        """Saves the current progress to the checkpoint file."""
        with open(self.checkpoint_file, 'w') as f:
            json.dump(self.checkpoint_data, f, indent=2)

    def _save_issues_to_jsonl(self, issues_list):
        """Appends a list of raw issue dictionaries to the JSONL output file."""
        try:
            with open(self.output_file, 'a', encoding='utf-8') as f:
                for issue in issues_list:
                    f.write(json.dumps(issue) + '\n')
            return True
        except IOError as e:
            logging.error(f"Failed to write to output file: {e}")
            return False

    def _fetch_jira_page(self, project_key, start_at):
        """Fetches a single page of Jira issues with robust error handling."""
        params = {
            'jql': f"project = {project_key}",
            'fields': self.request_fields,
            'maxResults': PAGE_SIZE,
            'startAt': start_at
        }
        
        for attempt in range(MAX_RETRIES):
            try:
                response = requests.get(self.base_url, params=params, timeout=NETWORK_TIMEOUT)

                if response.status_code == 429:
                    logging.warning("Rate limited (429). Sleeping for 60 seconds...")
                    time.sleep(60)
                    continue 

                if response.status_code >= 500:
                    logging.warning(f"Server error ({response.status_code}). Retrying in 15 seconds...")
                    time.sleep(15)
                    continue

                if not response.ok:
                    logging.error(f"Client error. Status: {response.status_code}, Body: {response.text}")
                    return None 

                return response.json()

            except requests.exceptions.RequestException as e:
                logging.warning(f"Network request failed: {e}. Retrying in 15 seconds...")
                time.sleep(15)
                
        logging.error(f"Failed to fetch data for {project_key} at {start_at} after {MAX_RETRIES} retries.")
        return None

    def run_pipeline(self):
        """Runs the main scraping pipeline for all projects."""
        logging.info("--- Starting Jira scraping pipeline ---")
        
        for project in self.projects_to_fetch:
            current_index = self.checkpoint_data.get(project, 0)
            total_issues = -1

            if current_index == "COMPLETED":
                logging.info(f"--- Project {project} is already COMPLETED. Skipping. ---")
                continue
                
            logging.info(f"\n--- Starting project: {project}, resuming from index: {current_index} ---")

            while True:
                data = self._fetch_jira_page(project, current_index)
                
                if data is None:
                    logging.error(f"Fetch failed for {project}. Stopping project and saving progress.")
                    break # Exit loop for this project, will retry next time
                
                if total_issues == -1:
                    total_issues = data.get('total', 0)
                    if total_issues == 0:
                        logging.info(f"No issues found for project {project}.")
                        break
                    logging.info(f"Found {total_issues} total issues for {project}.")

                issues_on_page = data.get('issues', [])
                if not issues_on_page:
                    if current_index >= total_issues:
                         logging.info("All issues fetched.")
                    else:
                        logging.warning("No issues returned on this page. Assuming end of project.")
                    
                    self.checkpoint_data[project] = "COMPLETED"
                    self._save_checkpoint()
                    logging.info(f"--- Project {project} finished and marked as COMPLETED. ---")
                    break
                    
                # --- Transaction-like save ---
                # 1. Save the data we just got
                if not self._save_issues_to_jsonl(issues_on_page):
                    logging.error(f"CRITICAL: Failed to write issues to {self.output_file}. Stopping pipeline.")
                    return # A critical error, stop everything
                
                # 2. Update our new position
                current_index += len(issues_on_page)
                
                # 3. Save our new position to the checkpoint
                self.checkpoint_data[project] = current_index
                self._save_checkpoint()

                logging.info(f"  -> Collected {current_index} / {total_issues} issues for {project}. Progress saved.")
                
                # 4. Check if we're done
                if current_index >= total_issues:
                    self.checkpoint_data[project] = "COMPLETED"
                    self._save_checkpoint()
                    logging.info(f"--- Project {project} finished and marked as COMPLETED. ---")
                    break

                time.sleep(0.3)

        logging.info("\n--- All projects processed. Pipeline finished. ---")


# --- Main execution ---
if __name__ == "__main__":
    # 1. Create an instance of the scraper
    scraper = JiraScraper(
        projects=PROJECTS_TO_FETCH,
        base_url=BASE_URL,
        fields=REQUEST_FIELDS,
        output_file=OUTPUT_FILE,
        checkpoint_file=CHECKPOINT_FILE
    )
    
    # 2. Run the pipeline
    scraper.run_pipeline()