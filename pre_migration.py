import os
import csv
from github import Github

# GitHub connection
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable not set.")
g = Github(GITHUB_TOKEN)

# Input and output files
source_repos_file = "source_repos.csv"
pre_migration_csv = "pre_migration_summary.csv"

# Build system file indicators
build_systems = {
    'maven': 'pom.xml',
    'gradle': 'build.gradle',
    'npm': 'package.json',
    'python': 'requirements.txt',
    # Add others as necessary...
}

def load_repositories_from_file(file_path):
    """Read repository names from a CSV file."""
    repos = []
    with open(file_path, "r") as file:
        reader = csv.reader(file)
        repos = [row[0].strip() for row in reader if row]
    return repos

def detect_pre_migration_details(repo_name):
    """Fetch pre-migration details from the source repository."""
    try:
        repo = g.get_repo(repo_name)
        primary_language = repo.language
        contents = repo.get_contents("")
        repo_files = [content.path for content in contents]

        detected_build_systems = []
        for build_system, indicator_file in build_systems.items():
            if any(indicator_file in file for file in repo_files):
                detected_build_systems.append(build_system)

        build_systems_detected = ', '.join(detected_build_systems) if detected_build_systems else "No common build system detected."
        branches = [branch.name for branch in repo.get_branches()]
        branch_count = len(branches)
        repo_size = repo.size  # Repository size in KB

        return primary_language, build_systems_detected, branch_count, repo_size, branches
    except Exception as e:
        print(f"Error fetching repository data for {repo_name}: {e}")
        return None, None, None, None, None

def log_pre_migration_details(repo_name, primary_language, build_system, branch_count, repo_size, branches):
    """Log pre-migration details to a CSV file."""
    with open(pre_migration_csv, mode='a', newline='') as file:
        fieldnames = ['repo_name', 'primary_language', 'build_system', 'branch_count', 'repo_size', 'branches']
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        if file.tell() == 0:
            writer.writeheader()

        writer.writerow({
            'repo_name': repo_name,
            'primary_language': primary_language,
            'build_system': build_system,
            'branch_count': branch_count,
            'repo_size': repo_size,
            'branches': ', '.join(branches)
        })

if __name__ == "__main__":
    repos = load_repositories_from_file(source_repos_file)

    for repo_name in repos:
        print(f"Gathering pre-migration data for {repo_name}...")

        # Gather pre-migration details
        primary_language, build_system, branch_count, repo_size, branches = detect_pre_migration_details(repo_name)
        if primary_language and build_system:
            # Log pre-migration details
            log_pre_migration_details(repo_name, primary_language, build_system, branch_count, repo_size, branches)
            print(f"Pre-migration data logged for {repo_name}.")
        else:
            print(f"Skipping {repo_name} due to missing pre-migration data.")