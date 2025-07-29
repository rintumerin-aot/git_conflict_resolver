from git_conflict_resolver.crew import GitConflictResolverCrew
import os

os.makedirs('output', exist_ok=True)

def run():
    """
    Run the Resolver crew.
    """
    inputs = {
        # 'directory': "D:\AI Agent\git_conflict_detector\RebaseAutomation\hello.py",
        # 'file_list_path': 'D:\AI Agent\conflict_files.txt',
        "log_file_path": r"C:\Users\adars\git_conflict_resolver\conflict.txt",
        'keyword': 'WEBBAR'
    }

    # Create and run the crew
    
    try:
        GitConflictResolverCrew().crew().kickoff(inputs=inputs)
        
    except Exception as e:
        raise Exception(f"An error occurred while running the crew: {e}")
    

    print("\nConflict resolution complete. See 'output/conflicts.md'.")


if __name__ == "__main__":
    run()
