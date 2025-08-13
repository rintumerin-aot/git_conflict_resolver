from git_conflict_resolver.crew import GitConflictResolverCrew
import os
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,  # Or DEBUG for more verbosity
    format="%(asctime)s - %(levelname)s - %(message)s"
)


SUMMARY_REPORT_PATH = Path("output/conflicts.md")


def delete_summary_report():
    if SUMMARY_REPORT_PATH.exists():
        try:
            os.remove(SUMMARY_REPORT_PATH)
            print(f"Deleted summary report: {SUMMARY_REPORT_PATH}")
        except Exception as e:
            print(f"Failed to delete summary report: {e}")

os.makedirs('output', exist_ok=True)

def run():
    """
    Run the Resolver crew.
    """
    inputs = {
        # 'directory': "D:\AI Agent\git_conflict_detector\RebaseAutomation\hello.py",
        # 'file_list_path': 'D:\AI Agent\conflict_files.txt',
        "log_file_path": r"D:\AI Agent\conflict_files.txt",
        'keyword': 'WEBBAR'
    }

    # Create and run the crew
    
    try:
        delete_summary_report() 
        GitConflictResolverCrew().crew().kickoff(inputs=inputs)
        
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")
    

    print("\nConflict resolution complete. See 'output/conflicts.md'.")


if __name__ == "__main__":
    run()
