import json
import os
import logging
import re
from bs4 import BeautifulSoup

# --- Configuration ---
RAW_INPUT_FILE = 'jira_corpus_raw.jsonl'
LLM_OUTPUT_FILE = 'jira_corpus_llm_ready.jsonl'

# --- Setup Logging ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("transform.log"), 
        logging.StreamHandler()
    ]
)

class DataTransformer:
    
    def __init__(self, raw_file, llm_file):
        self.raw_input_file = raw_file
        self.llm_output_file = llm_file

    def _clean_text(self, text):
        """
        Cleans raw Jira text:
        1. Removes HTML.
        2. Removes Jira markup.
        3. Anonymizes PII (emails, IPs).
        4. Normalizes whitespace.
        """
        if not text:
            return ""
        
        # 1. Strip all HTML tags
        soup = BeautifulSoup(text, 'html.parser')
        text = soup.get_text(separator=' ')
        
        # 2. Remove Jira-specific markup (like {code:java}, {panel}, {noformat}, etc.)
        text = re.sub(r'\{[^\}]+\}', ' ', text)
        
        # 3. Remove Jira link syntax [text|url] and keep just the text
        text = re.sub(r'\[([^\|\]]+)\|[^\]]+\]', r'\1', text)
        
        # 4. --- NEW: Anonymize Sensitive Information ---
        # Anonymize emails
        text = re.sub(r'\S+@\S+\.\S+', '[EMAIL_REMOVED]', text)
        # Anonymize IP addresses
        text = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP_REMOVED]', text)

        # 5. Normalize all whitespace (multiple spaces, newlines, tabs) to a single space
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

    def _create_derived_tasks(self, raw_issue):
        """
        Takes one raw issue and generates a list of
        prompt/completion pairs.
        """
        derived_tasks = []
        try:
            key = raw_issue.get('key')
            fields = raw_issue.get('fields', {})
            
            # 1. Get Metadata
            summary = fields.get('summary', '') or ''
            status = fields.get('status', {}).get('name', 'Unknown')
            priority = fields.get('priority', {}).get('name', 'Unknown')
            issuetype = fields.get('issuetype', {}).get('name', 'Unknown')

            # 2. Get AND CLEAN Description and Comments
            description = self._clean_text(fields.get('description', '') or '')
            
            comments_list = fields.get('comment', {}).get('comments', [])
            comments_text = ""
            for comment in comments_list:
                author = comment.get('author', {}).get('displayName', 'User')
                body = self._clean_text(comment.get('body', ''))
                
                if body: 
                    comments_text += f"\n\n--- Comment by {author} ---\n{body}"
            
            full_context = f"Description:\n{description}\n{comments_text}"

            # 3. Drop Empty/Meaningless Issues
            if not summary or not (description or comments_text):
                return [] 

            # 4. Create Derived Tasks
            
            # Task 1: Summarization
            derived_tasks.append({
                "id": f"{key}_summary",
                "prompt": f"Summarize the following Jira issue:\n\nTitle: {summary}\n\n{full_context}",
                "completion": summary
            })

            # Task 2: Q&A - Status
            derived_tasks.append({
                "id": f"{key}_qna_status",
                "prompt": f"Given the following issue, what is its current status?\n\nTitle: {summary}\n\n{full_context}",
                "completion": status
            })

            # Task 3: Classification - Priority
            derived_tasks.append({
                "id": f"{key}_classify_priority",
                "prompt": f"Classify the priority (e.g., Major, Minor, Blocker) of the following issue:\n\nTitle: {summary}\n\n{full_context}",
                "completion": priority
            })

            # Task 4: Classification - Issue Type
            derived_tasks.append({
                "id": f"{key}_classify_type",
                "prompt": f"Is the following issue a \"Bug\", \"New Feature\", or \"Task\"?\n\nTitle: {summary}\n\n{full_context}",
                "completion": issuetype
            })

        except Exception as e:
            logging.warning(f"Failed to transform issue {key}. Error: {e}")
            return []
            
        return derived_tasks

    def run_transformation(self):
        """
        Reads the raw JSONL file and transforms it into an
        LLM-ready JSONL file.
        """
        logging.info(f"--- Starting LLM transformation pipeline ---")
        
        if not os.path.exists(self.raw_input_file):
            logging.error(f"Raw data file not found: {self.raw_input_file}. Run scraper.py first.")
            return

        # --- NEW: Set for duplicate filtering ---
        seen_task_ids = set()

        try:
            with open(self.raw_input_file, 'r', encoding='utf-8') as infile, \
                 open(self.llm_output_file, 'w', encoding='utf-8') as outfile:
                
                count = 0
                derived_count = 0
                for line in infile:
                    try:
                        raw_issue = json.loads(line)
                        derived_tasks = self._create_derived_tasks(raw_issue)
                        
                        for task in derived_tasks:
                            # --- NEW: Duplicate check ---
                            if task['id'] not in seen_task_ids:
                                outfile.write(json.dumps(task) + '\n')
                                seen_task_ids.add(task['id'])
                                derived_count += 1
                            
                    except json.JSONDecodeError:
                        logging.warning(f"Skipping malformed line in raw file: {line}")
                        
                    count += 1
                    if count % 1000 == 0:
                        logging.info(f"Processed {count} raw issues (found {derived_count} unique tasks)...")
                        
            logging.info(f"--- Transformation complete. ---")
            logging.info(f"Processed {count} raw issues.")
            logging.info(f"Created {derived_count} unique LLM-ready training examples.")
            logging.info(f"LLM-ready data saved to: {self.llm_output_file}")

        except IOError as e:
            logging.error(f"File operation failed: {e}")

# --- Main execution ---
if __name__ == "__main__":
    
    transformer = DataTransformer(
        raw_file=RAW_INPUT_FILE,
        llm_file=LLM_OUTPUT_FILE
    )
    
    transformer.run_transformation()