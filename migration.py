import os
import shutil
import subprocess
import stat
from github import Github
import csv
import time

# GitHub Personal Access Token from environment variable
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

if not GITHUB_TOKEN:
    raise ValueError("GITHUB_TOKEN environment variable not set.")

# Initialize GitHub connection
g = Github(GITHUB_TOKEN)

# Organization name where the repositories should be created
ORG_NAME = "capgemini-cg-demo"

# GitHub repo where the CI templates are stored
CI_TEMPLATE_REPO = "capgemini-ga-demo/github_centralized_workflows"
CI_TEMPLATE_BRANCH = "develop"
CI_TEMPLATE_PATH = "templates"

# File to store target repository URLs in org/repo format
target_repos_file = "target_repos.csv"

# Build system file indicators
build_systems = {
    'maven': 'pom.xml',
    'gradle': 'build.gradle',
    'npm': 'package.json',
    'yarn': 'yarn.lock',
    'make': 'Makefile',
    'cmake': 'CMakeLists.txt',
    'bazel': 'BUILD',
    'go': 'go.mod',
    'rust': 'Cargo.toml',
    'python_setuptools': 'setup.py',
    'python_pip': 'requirements.txt',
    'python_pyproject': 'pyproject.toml',
    'ruby_bundler': 'Gemfile',
    'ruby_gem': '.gemspec',
    'dotNET_CS': '.csproj',
    'dotNET_VB': '.vbproj',
    'dotNET_FS': '.fsproj',
    'dotNET_Solution': '.sln',
    'dotNET_SDK': 'global.json',
    'dotNET_NuGet': 'packages.config'
}

# CSV file path
csv_file_path = "migration_summary.csv"

def print_separator_with_repo_name(repo_name, phase="Starting migration"):
    """Prints a separator line with the repo_name in the middle."""
    total_length = 100  # Total length of the line including equal signs and repo_name
    repo_display = f" {phase} for {repo_name} "  # Add spaces for padding around repo_name
    num_equals = total_length - len(repo_display)
    
    left_equals = num_equals // 2
    right_equals = num_equals - left_equals
    
    print(f"\n{'=' * left_equals}{repo_display}{'=' * right_equals}\n")

def detect_language_and_build_system(repo_name):
    """Detect the primary language and the build system used in a GitHub repository."""
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

        return primary_language, build_systems_detected
    except Exception as e:
        print(f"Error fetching repository data for {repo_name}: {e}")
        return None, None

def load_repositories_from_file(file_path):
    """Read repository names from a file."""
    try:
        with open(file_path, "r") as file:
            return [line.strip() for line in file if line.strip()]
    except Exception as e:
        print(f"Error reading the file: {e}")
        return []

def fetch_ci_file_from_github(build_system):
    """Fetch the CI template from the Centralized Workflow repository."""
    try:
        repo = g.get_repo(CI_TEMPLATE_REPO)
        ci_file_path = f"{CI_TEMPLATE_PATH}/{build_system}-ci.yml"

        # Fetch the content if the file exists
        ci_file = repo.get_contents(ci_file_path, ref=CI_TEMPLATE_BRANCH)
        return ci_file.decoded_content.decode('utf-8')
    
    except Exception as e:
        print(f"Error fetching Centralized Workflow File for {build_system}: {e}")
        return None

def create_or_update_repo(repo_name):
    """Create or update a repository in the specified organization."""
    try:
        repo = g.get_organization(ORG_NAME).get_repo(repo_name)
        print(f"Repository '{repo_name}' already exists. Updating...")
        return repo
    except Exception:
        try:
            print(f"Creating repository '{repo_name}' under organization '{ORG_NAME}'...")
            repo = g.get_organization(ORG_NAME).create_repo(repo_name)
            print(f"\033[92mRepository '{repo.name}' created successfully.\033[0m")  # Green for success
            return repo
        except Exception as e:
            print(f"Error creating repository '{repo_name}': {e}")
            return None

def push_branches_and_tags(local_repo_path, push_url):
    """Push the branches and tags, excluding problematic refs like pull requests."""
    try:
        subprocess.run(['git', 'remote', 'rm', 'origin'], cwd=local_repo_path, check=True)
        subprocess.run(['git', 'remote', 'add', 'origin', push_url], cwd=local_repo_path, check=True)

        print(f"  - Pushing branches and tags to '{push_url}'...")
        subprocess.run(['git', 'push', '--all'], cwd=local_repo_path, check=True)  # Push all branches
        subprocess.run(['git', 'push', '--tags'], cwd=local_repo_path, check=True)  # Push all tags

    except subprocess.CalledProcessError as e:
        print(f"Error pushing branches and tags: {e}")

def log_migration_to_csv(source_url, target_url, migrated_with_workflow):
    """Log migration details to a CSV file without creating duplicate entries."""
    file_exists = os.path.isfile(csv_file_path)

    existing_entries = []
    if file_exists:
        with open(csv_file_path, mode='r', newline='') as csv_file:
            reader = csv.DictReader(csv_file)
            for row in reader:
                existing_entries.append(row['source_github_url'])

    if source_url not in existing_entries:
        with open(csv_file_path, mode='a', newline='') as csv_file:
            fieldnames = ['source_github_url', 'target_github_url', 'migrated_with_workflow_file']
            writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

            if not file_exists:
                writer.writeheader()

            writer.writerow({
                'source_github_url': source_url,
                'target_github_url': target_url,
                'migrated_with_workflow_file': migrated_with_workflow
            })
        print(f"Logged migration for {source_url} to {target_url}.")
    else:
        print(f"Duplicate entry detected for {source_url}. Skipping logging.")

def log_target_repo_url(target_url):
    """Log successfully migrated repository target URLs to a text file in org/repo format (without .git)."""
    # Extract org/repo from full target URL and ensure no .git is added
    org_repo = target_url.replace("https://github.com/", "").rstrip(".git")
    with open(target_repos_file, mode='a') as file:
        file.write(org_repo + '\n')
    print(f"Added target repo URL '{org_repo}' to target_repos.txt.")

# Helper function to remove read-only permission before deleting files
def remove_readonly(func, path, exc_info):
    """Change the file to writable before trying to delete it."""
    os.chmod(path, stat.S_IWRITE)
    func(path)

def cleanup_directory(directory_path):
    """Clean up a directory, ensuring all files are writable before deleting."""
    try:
        print(f"  - Cleaning up {directory_path}")
        shutil.rmtree(directory_path, onerror=remove_readonly)
    except Exception as e:
        print(f"  - Error cleaning up {directory_path}: {e}")

if __name__ == "__main__":
    file_path = "source_repos.csv"
    
    repos = load_repositories_from_file(file_path)
    
    if not repos:
        print("No repositories found in the file.")
    else:
        for repo_name in repos:
            print_separator_with_repo_name(repo_name, phase="Starting migration")

            primary_language, build_system = detect_language_and_build_system(repo_name)
            if primary_language and build_system:
                print(f"Repository: {repo_name}")
                print(f"  - Primary Language: {primary_language}")
                print(f"  - Build System(s): {build_system}")
                
                source_repo = g.get_repo(repo_name)

                build_system_list = build_system.split(', ')  
                ci_found = False
                ci_content = None
                for system in build_system_list:
                    ci_content = fetch_ci_file_from_github(system.strip())
                    if ci_content:
                        ci_found = True
                        print(f"\033[92m  - Centralized Workflow File Found for {system.strip()} from Centralized Workflow Repository\033[0m")
                        break
                    else:
                        print(f"\033[91m  - Centralized Workflow File {system.strip()}-ci.yml does not exist in Centralized Workflow Repository.\033[0m")

                local_repo_name = repo_name.split('/')[-1]
                local_repo_path = os.path.join(os.getcwd(), f"{local_repo_name}-repo")

                if os.path.exists(local_repo_path):
                    print(f"  - Directory '{local_repo_name}-repo' already exists. Removing it.")
                    shutil.rmtree(local_repo_path, onerror=remove_readonly)

                print(f"  - Cloning the repository as a mirror to '{local_repo_name}-repo'...")
                subprocess.run(['git', 'clone', '--mirror', f'https://github.com/{repo_name}.git', local_repo_path], check=True)

                temporary_work_dir = os.path.join(os.getcwd(), f"{local_repo_name}-worktree")
                if os.path.exists(temporary_work_dir):
                    print(f"  - Temporary worktree directory '{temporary_work_dir}' already exists. Removing it.")
                    shutil.rmtree(temporary_work_dir)

                subprocess.run(['git', 'clone', local_repo_path, temporary_work_dir], check=True)

                if ci_found and ci_content:
                    print(f"  - Saving Centralized Workflow File to '{temporary_work_dir}/.github/workflows/'...")
                    workflow_dir = os.path.join(temporary_work_dir, '.github', 'workflows')
                    os.makedirs(workflow_dir, exist_ok=True)
                    ci_file_path = os.path.join(workflow_dir, f"{system.strip()}-ci.yml")
                    with open(ci_file_path, 'w') as ci_file:
                        ci_file.write(ci_content)

                    try:
                        print(f"  - Committing and pushing the CI file for {local_repo_name}...")
                        subprocess.run(['git', 'add', '.'], cwd=temporary_work_dir, check=True)
                        subprocess.run(['git', 'commit', '-m', 'Added CI workflow file'], cwd=temporary_work_dir, check=True)
                        subprocess.run(['git', 'push', 'origin', 'main'], cwd=temporary_work_dir, check=True)
                        print(f"\033[92m  - CI file pushed successfully.\033[0m")
                    except subprocess.CalledProcessError as e:
                        print(f"\033[91m  - Error committing or pushing the CI file: {e}\033[0m")

                repo = create_or_update_repo(local_repo_name)

                if repo:
                    push_url = f'https://github.com/{ORG_NAME}/{local_repo_name}.git'
                    push_branches_and_tags(local_repo_path, push_url)

                    time.sleep(10)

                    source_url = f'https://github.com/{repo_name}.git'
                    target_url = push_url
                    log_migration_to_csv(source_url, target_url, ci_found)

                    # Log successfully migrated repository URL in org/repo.git format
                    log_target_repo_url(target_url)

                    # Run garbage collection to release any locks before cleanup
                    subprocess.run(['git', 'gc'], cwd=temporary_work_dir, check=True)

                    # Clean up local mirrored repository
                    cleanup_directory(local_repo_path)

                    # Clean up temporary working directory
                    cleanup_directory(temporary_work_dir)

                    print(f"\033[92m  - Migration complete for repository: {repo_name}\033[0m")
                else:
                    print(f"\033[91mFailed to create or update repository '{local_repo_name}' in organization '{ORG_NAME}'.\033[0m")

            else:
                print(f"\033[91mCould not determine the language or build system for repository: {repo_name}\033[0m")

            print_separator_with_repo_name(repo_name, phase="End of migration")