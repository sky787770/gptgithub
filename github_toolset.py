import os

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from github import Auth, Github   # Used to interact with the GitHub API.
from pydantic import BaseModel, Field    # Used for data validation and serialization
from dotenv import load_dotenv
from github_oauth import token_storage, OAuthToken


load_dotenv()

class GitHubUser(BaseModel):      # Represents a GitHub user
    """GitHub user information"""

    login: str
    name: str | None = None
    email: str | None = None


class GitHubRepository(BaseModel): # Represents a GitHub repository with key metadata
    """GitHub repository information"""

    name: str = None
    full_name: str = None
    description: str | None = None
    url: str = None
    author: str | None = None
    license: Any | None = None
    private: bool | None = None
    archived: bool | None = None
    default_branch: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    pushed_at: str | None = None
    stars: int | None = None
    forks: int | None = None
    subscribers: int | None = None
    open_issues: int | None= None
    languages: dict[str, int] | None = None
    contributors: list[str] | None = None
    topics: list[str] | None = None
    collaborators: list[Any] | None = None
    branches: list[str] | None = None
    has_wiki: bool | None = None


class GitHubCommit(BaseModel): # Represents a commit in a repository
    """GitHub commit information"""

    sha: str
    message: str
    author: str
    date: str
    url: str


class GitHubResponse(BaseModel):
    """Base response model for GitHub API operations"""

    status: str
    message: str
    count: int | None = None
    error_message: str | None = None


class ModifiedSymbol(BaseModel):
    """Represents a function/class symbol modified within a diff patch"""

    name: str
    kind: str  # one of: function, class, method, unknown
    change_type: str  # one of: added, removed, modified
    file: str


class DiffFileChange(BaseModel):
    """Represents a file changed in a commit with parsed symbols"""

    filename: str
    status: str | None = None
    additions: int | None = None
    deletions: int | None = None
    changes: int | None = None
    patch: str | None = None
    modified_symbols: list[ModifiedSymbol] = Field(default_factory=list)

class CommitSummary(BaseModel):
    """Summary statistics for a commit"""
    files_changed: int | None = None
    total_additions: int | None = None
    total_deletions: int | None = None
    total_changes: int | None = None
    
class CommitWithFiles(BaseModel):
    """Response model for commit diff and parsed symbols"""
    commit: GitHubCommit | None = None
    files: list[DiffFileChange] = Field(default_factory=list)
    summary: CommitSummary | None = None

class CommitDiffResponse(GitHubResponse):
    """Response model for a commit diff and parsed symbols"""

    commits: list[CommitWithFiles] = Field(default_factory=list)

class RepositoryResponse(GitHubResponse):
    """Response model for repository operations"""

    data: list[GitHubRepository] | None = None


class CommitResponse(GitHubResponse):
    """Response model for commit operations"""

    data: list[GitHubCommit] | None = None


class GitHubToolset:
    """GitHub API toolset for querying repositories and recent updates"""

    def __init__(self, user_id: Optional[str] = None):
        self._github_client = None
        self._user_id = user_id

    def _get_github_client(self) -> Github:
        """Get GitHub client using OAuth token or fallback to environment token.

        Priority:
        1. OAuth token from user_id (if provided)
        2. GITHUB_TOKEN environment variable (fallback)
        3. Unauthenticated client (public data only)
        """
        if self._github_client is None:
            # Try OAuth token first
            if self._user_id:
                oauth_token = token_storage.get_token(self._user_id)
                if oauth_token and oauth_token.access_token:
                    auth = Auth.Token(oauth_token.access_token)
                    self._github_client = Github(auth=auth)
                    return self._github_client
            
            # Fallback to environment token
            github_token = os.getenv('GITHUB_TOKEN')
            if github_token:
                auth = Auth.Token(github_token)
                self._github_client = Github(auth=auth)
            else:
                # Unauthenticated client (lower rate limits, but still functional for public data)
                self._github_client = Github()
        return self._github_client

    # ------------------------------
    # Diff and symbol parsing helpers
    # ------------------------------
    def _infer_language_from_filename(self, filename: str) -> str:
        lower = filename.lower()
        if lower.endswith('.py'):
            return 'python'
        if lower.endswith('.ts') or lower.endswith('.tsx'):
            return 'typescript'
        if lower.endswith('.js') or lower.endswith('.jsx'):
            return 'javascript'
        if lower.endswith('.java'):
            return 'java'
        if lower.endswith('.go'):
            return 'go'
        if lower.endswith('.cls') or lower.endswith('.trigger') or lower.endswith('.apex'):
            return 'apex'
        if lower.endswith('.css'):
            return 'css'
        if lower.endswith('.html') or lower.endswith('.htm'):
            return 'html'
        if lower.endswith('.c'):
            return 'c'
        if lower.endswith('.cpp') or lower.endswith('.cc') or lower.endswith('.cxx') or lower.endswith('.hpp') or lower.endswith('.hh') or lower.endswith('.hxx'):
            return 'cpp'
        if lower.endswith('.cs'):
            return 'csharp'
        if lower.endswith('.h'):
            return 'c'
        return 'unknown'

    def _parse_symbols_from_patch(self, filename: str, patch: str | None) -> list[ModifiedSymbol]:
        """Parse modified function/class symbols from a unified diff patch.

        Heuristic, language-aware parsing for: Python, JS/TS, Java, Go, Apex, C, C++, C#.
        Falls back to hunk headers and keyword detection.
        """
        if not patch:
            return []

        import re

        language = self._infer_language_from_filename(filename)
        symbols: list[ModifiedSymbol] = []

        # Capture function context from hunk headers: @@ ... function signature ... @@
        hunk_header_re = re.compile(r'^@@.*?@@\s*(.*)$')

        # Language-specific regexes for added/removed declarations
        patterns_by_lang: dict[str, dict[str, re.Pattern[str]]] = {
            'python': {
                'func': re.compile(r'^[+\-]\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('),
                'class': re.compile(r'^[+\-]\s*class\s+([A-Za-z_][A-Za-z0-9_]*)\s*[:\(]'),
                'method': re.compile(r'^[+\-]\s*def\s+([A-Za-z_][A-Za-z0-9_]*)\s*\('),
            },
            'javascript': {
                'func': re.compile(r'^[+\-]\s*(?:function\s+([A-Za-z_$][\w$]*)\s*\(|const\s+([A-Za-z_$][\w$]*)\s*=\s*\([^)]*\)\s*=>|([A-Za-z_$][\w$]*)\s*=\s*function\s*\()'),
                'class': re.compile(r'^[+\-]\s*class\s+([A-Za-z_$][\w$]*)\s*'),
                'method': re.compile(r'^[+\-]\s*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{'),
            },
            'typescript': {
                'func': re.compile(r'^[+\-]\s*(?:function\s+([A-Za-z_$][\w$]*)\s*\(|const\s+([A-Za-z_$][\w$]*)\s*=\s*\([^)]*\)\s*=>)'),
                'class': re.compile(r'^[+\-]\s*class\s+([A-Za-z_$][\w$]*)\s*'),
                'method': re.compile(r'^[+\-]\s*(?:public|private|protected|static|readonly|async)?\s*([A-Za-z_$][\w$]*)\s*\([^)]*\)\s*\{'),
            },
            'java': {
                'func': re.compile(r'^[+\-]\s*(?:public|private|protected|static|final|synchronized|native|abstract|default)?\s*[\w\<\>\[\]]+\s+([a-zA-Z_][\w]*)\s*\('),
                'class': re.compile(r'^[+\-]\s*(?:public|private|protected)?\s*(?:final\s+)?class\s+([A-Za-z_][\w]*)'),
                'method': re.compile(r'^[+\-]\s*(?:public|private|protected|static|final|synchronized|native|abstract|default)?\s*[\w\<\>\[\]]+\s+([a-zA-Z_][\w]*)\s*\('),
            },
            'go': {
                'func': re.compile(r'^[+\-]\s*func\s+(?:\([^)]*\)\s*)?([A-Za-z_][\w]*)\s*\('),
                'class': re.compile(r'\bstruct\b\s+([A-Za-z_][\w]*)'),
                'method': re.compile(r'^[+\-]\s*func\s*\([^)]*\)\s*([A-Za-z_][\w]*)\s*\('),
            },
            # Apex (Salesforce): classes, methods, and triggers
            'apex': {
                'class': re.compile(r'^[+\-]\s*(?:global|public|private|protected)?\s*class\s+([A-Za-z_][\w]*)'),
                'method': re.compile(r'^[+\-]\s*(?:global|public|private|protected|static|virtual|override|abstract|testmethod)?\s*[\w<>,\[\]\s]+\s+([A-Za-z_][\w]*)\s*\('),
                'func': re.compile(r'^[+\-]\s*trigger\s+([A-Za-z_][\w]*)\s+on\s+[A-Za-z_][\w]*\s*\('),
            },
            # C (heuristic): functions
            'c': {
                'func': re.compile(r'^[+\-]\s*(?:[A-Za-z_][\w\s\*]*\s+)+([A-Za-z_][\w]*)\s*\([^;]*\)\s*\{'),
            },
            # C++ (heuristic): classes/structs and functions/methods (including scope ::)
            'cpp': {
                'class': re.compile(r'^[+\-]\s*(?:template\s*<[^>]+>\s*)?(?:class|struct)\s+([A-Za-z_][\w]*)'),
                'func': re.compile(r'^[+\-]\s*(?:[\w:<>,\s\*&]+)\s+([A-Za-z_][\w]*(?:::[A-Za-z_][\w]*)?)\s*\([^;{)]*\)\s*\{'),
                'method': re.compile(r'^[+\-]\s*(?:[\w:<>,\s\*&]+)\s+([A-Za-z_][\w]*(?:::[A-Za-z_][\w]*)?)\s*\([^;{)]*\)\s*\{'),
            },
            # C#
            'csharp': {
                'class': re.compile(r'^[+\-]\s*(?:public|private|protected|internal|sealed|abstract|partial|static)?\s*class\s+([A-Za-z_][\w]*)'),
                'method': re.compile(r'^[+\-]\s*(?:public|private|protected|internal|static|virtual|override|sealed|async|extern|unsafe|new|partial|readonly|ref|in|out)?\s*[\w<>,\[\]\s\?]+\s+([A-Za-z_][\w]*)\s*\([^;{)]*\)\s*\{'),
            },
            # For CSS/HTML we do not extract symbols; fallback to header/keyword context
        }

        lang_patterns = patterns_by_lang.get(language, {})

        for line in patch.splitlines():
            change_type = 'modified'
            if line.startswith('+') and not line.startswith('+++'):
                change_type = 'added'
            elif line.startswith('-') and not line.startswith('---'):
                change_type = 'removed'

            # Hunk header context capture (best-effort)
            if line.startswith('@@'):
                m = hunk_header_re.match(line)
                if m:
                    context = m.group(1).strip()
                    if context:
                        # Try to extract symbol name from context
                        context_name_match = re.search(r'([A-Za-z_$][\w$]*)\s*\(', context)
                        if context_name_match:
                            symbols.append(
                                ModifiedSymbol(
                                    name=context_name_match.group(1),
                                    kind='unknown',
                                    change_type='modified',
                                    file=filename,
                                )
                            )
                continue

            # Language-specific declarations
            for kind, pattern in lang_patterns.items():
                m = pattern.match(line)
                if m:
                    name = next((g for g in m.groups() if g), None)
                    if name:
                        symbols.append(
                            ModifiedSymbol(
                                name=name,
                                kind='method' if kind == 'method' else ('class' if kind == 'class' else 'function'),
                                change_type=change_type,
                                file=filename,
                            )
                        )
                    break
        # De-duplicate by (file, name, kind, change_type)
        unique: dict[tuple[str, str, str, str], ModifiedSymbol] = {}
        for s in symbols:
            key = (s.file, s.name, s.kind, s.change_type)
            unique[key] = s
        return list(unique.values())


    # ------------------------------
    # Public tools
    # ------------------------------
   
    def get_latest_commit_with_diff(self, repo_name: str, limit: int | None = None) -> CommitDiffResponse:
        """Get the most recent commits for a repository along with files changed, patches, and parsed symbols.

        Args:
            repo_name: Repository identifier in the form 'repo'.
            limit: Number of commits to return (default: 2)

        Returns:
            CommitDiffResponse with commit metadata, changed files, and modified symbols per file.
        """
        if limit is None:
            limit = 2

        try:
            github = self._get_github_client()
            
            # Get authenticated user or use provided username
            if self._user_id:
                oauth_token = token_storage.get_token(self._user_id)
                if oauth_token and oauth_token.user_login:
                    owner_login = oauth_token.user_login
                else:
                    authenticated_user = github.get_user()
                    owner_login = authenticated_user.login
            else:
                authenticated_user = github.get_user()
                owner_login = authenticated_user.login
                
            repo = github.get_repo(f"{owner_login}/{repo_name}")  # Exposes commits, issues, files, etc.

            # Get the most recent `limit` commits
            commits = repo.get_commits()[:limit]

            commit_with_files = []
            for commit in commits:
                
                # Commit metadata
                commit_model = GitHubCommit(
                    sha=commit.sha[:8],
                    message=commit.commit.message,
                    author=commit.commit.author.name if commit.commit.author else None,
                    date=(
                        commit.commit.author.date.astimezone(timezone.utc).isoformat()
                        if commit.commit.author and commit.commit.author.date.tzinfo
                        else commit.commit.author.date.replace(tzinfo=timezone.utc).isoformat()
                        if commit.commit.author else None
                    ),
                    url=commit.html_url,
                )

                # Files changed in this commit
                files: list[DiffFileChange] = []
                total_additions = total_deletions = total_changes = 0
                for f in commit.files:
                    symbols = self._parse_symbols_from_patch(f.filename, getattr(f, 'patch', None)) or []
                    additions = getattr(f, "additions", 0) or 0
                    deletions = getattr(f, "deletions", 0) or 0
                    changes = getattr(f, "changes", 0) or 0

                    total_additions += additions
                    total_deletions += deletions
                    total_changes += changes
                    
                    files.append(
                        DiffFileChange(
                            filename=f.filename,
                            status=getattr(f, 'status', None),
                            additions=getattr(f, 'additions', None),
                            deletions=getattr(f, 'deletions', None),
                            changes=getattr(f, 'changes', None),
                            patch=getattr(f, 'patch', None),
                            modified_symbols=symbols or [],
                        )
                    )
                summary = CommitSummary(
                    files_changed=len(files),
                    total_additions=total_additions,
                    total_deletions=total_deletions,
                    total_changes=total_changes,
                )
                commit_with_files.append(
                    CommitWithFiles(
                        commit=commit_model,
                        files=files,
                        summary=summary
                    )
                )


            return CommitDiffResponse(
                status='success',
                message=f'Successfully retrieved {len(commit_with_files)} latest commits and parsed diffs',
                commits=commit_with_files,   # now holds a list of commits+files
                count=len(commit_with_files),
            )

        except Exception as e:
            return CommitDiffResponse(
                status='error',
                message=f'Failed to get latest commits diff: {e!s}',
                error_message=f'Failed to get latest commits diff: {e!s}',
            )



    def get_commit_diff(self, repo_name: str, sha: str) -> CommitDiffResponse:
        """Get a specific commit's diff and parsed symbols.

        Args:
            repo_name: Repository identifier in the form 'repo'.
            sha: Full or short commit SHA.

        Returns:
            CommitDiffResponse with commit metadata, changed files, and modified symbols per file.
        """
        try:
            github = self._get_github_client()
            
            # Get authenticated user or use provided username
            if self._user_id:
                oauth_token = token_storage.get_token(self._user_id)
                if oauth_token and oauth_token.user_login:
                    owner_login = oauth_token.user_login
                else:
                    authenticated_user = github.get_user()
                    owner_login = authenticated_user.login
            else:
                authenticated_user = github.get_user()
                owner_login = authenticated_user.login
                
            repo = github.get_repo(f"{owner_login}/{repo_name}")
            commit = repo.get_commit(sha=sha)

            commit_with_files= []
            commit_model = GitHubCommit(
                sha=commit.sha[:8],
                message=commit.commit.message,
                author=commit.commit.author.name,
                date=(
                    commit.commit.author.date.astimezone(timezone.utc).isoformat()
                    if commit.commit.author.date.tzinfo
                    else commit.commit.author.date.replace(tzinfo=timezone.utc).isoformat()
                ),
                url=commit.html_url,
            )

            files: list[DiffFileChange] = []
            total_additions = total_deletions = total_changes = 0
            for f in commit.files:
                symbols = self._parse_symbols_from_patch(f.filename, getattr(f, 'patch', None)) or []
                additions = getattr(f, "additions", 0) or 0
                deletions = getattr(f, "deletions", 0) or 0
                changes = getattr(f, "changes", 0) or 0

                total_additions += additions
                total_deletions += deletions
                total_changes += changes
                files.append(
                    DiffFileChange(
                        filename=f.filename,
                        status=getattr(f, 'status', None),
                        additions=getattr(f, 'additions', None),
                        deletions=getattr(f, 'deletions', None),
                        changes=getattr(f, 'changes', None),
                        patch=getattr(f, 'patch', None),
                        modified_symbols=symbols,
                    )
                )
            summary = CommitSummary(
                    files_changed=len(files),
                    total_additions=total_additions,
                    total_deletions=total_deletions,
                    total_changes=total_changes,
                )
            commit_with_files.append(
                    CommitWithFiles(
                        commit=commit_model,
                        files=files,
                        summary=summary
                    )
                )


            return CommitDiffResponse(
                status='success',
                message=f'Successfully retrieved {len(commit_with_files)} latest commits and parsed diffs',
                commits=commit_with_files,   # now holds a list of commits+files
                count=len(commit_with_files),
            )
        except Exception as e:
            return CommitDiffResponse(
                status='error',
                message=f'Failed to get commit diff: {e!s}',
                error_message=f'Failed to get commit diff: {e!s}',
            )

    def get_user_repositories(
        self,
        username: str | None = None,
        days: int | None = None,
        limit: int | None = None,
    ) -> RepositoryResponse:
        """Get user's repositories with recent updates.

        If `username` is not provided, this method defaults to the authenticated
        user from GITHUB_TOKEN.
        Args:
            username: GitHub username (optional, defaults to authenticated user)
            days: Number of days to look for recent updates (default: 30 days)
            limit: Maximum number of repositories to return (default: 10)

        Returns:
            RepositoryResponse: Contains status, repository list, and metadata
        """
        # Set default values
        if days is None:
            days = 28
        if limit is None:
            limit = 15
            
        try:
            github = self._get_github_client()

            if username:
                user = github.get_user(username)
            else:
                # Default to the authenticated user
                if self._user_id:
                    oauth_token = token_storage.get_token(self._user_id)
                    if oauth_token and oauth_token.user_login:
                        user = github.get_user(oauth_token.user_login)
                    else:
                        user = github.get_user()
                else:
                    user = github.get_user()

            repos = []
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            for repo in user.get_repos(sort='updated', direction='desc'):
                if len(repos) >= limit:
                    break

                # Ensure both datetimes are timezone-aware in UTC
                repo_updated_at = (
                    repo.updated_at if repo.updated_at.tzinfo else repo.updated_at.replace(tzinfo=timezone.utc)
                )
                if repo_updated_at >= cutoff_date:
                    repos.append(
                        GitHubRepository(
                                name=repo.name,
                                full_name=repo.full_name,
                                description=repo.description,
                                url=repo.html_url,
                                author=repo.owner.login,
                                license=repo.license.spdx_id if repo.license else None,
                                private=repo.private,
                                archived=repo.archived,
                                default_branch=repo.default_branch,
                                created_at=repo.created_at.isoformat(),
                                updated_at=repo.updated_at.isoformat(),
                                pushed_at=repo.pushed_at.isoformat(),
                                stars=repo.stargazers_count,
                                forks=repo.forks_count,
                                subscribers=repo.subscribers_count,
                                open_issues=repo.open_issues_count,
                                languages=repo.get_languages(),
                                contributors=[c.login for c in repo.get_contributors(anon="true")],
                                topics=repo.get_topics(),
                                collaborators=repo.get_collaborators(),
                                branches=[b.name for b in repo.get_branches()],
                                has_wiki=repo.has_wiki,
                                
                                                )

                    )

            return RepositoryResponse(
                status='success',
                data=repos,
                count=len(repos),
                message=f'Successfully retrieved {len(repos)} repositories updated in the last {days} days',
            )
        except Exception as e:
            return RepositoryResponse(
                status='error',
                message=f'Failed to get repositories: {e!s}',
                error_message=f'Failed to get repositories: {e!s}',
            )

    def get_recent_commits(
        self, repo_name: str, days: int | None = None, limit: int | None = None
    ) -> CommitResponse:
        """Get recent commits for a repository

        Args:
            repo_name: Repository name in format 'repo'
            days: Number of days to look for recent commits (default: 20 days)
            limit: Maximum number of commits to return (default: 30)

        Returns:
            CommitResponse: Contains status, commit list, and metadata
        """
        # Set default values
        if days is None:
            days = 20
        if limit is None:
            limit = 30

        try:
            github = self._get_github_client()

            # Get authenticated user or use provided username
            if self._user_id:
                oauth_token = token_storage.get_token(self._user_id)
                if oauth_token and oauth_token.user_login:
                    owner_login = oauth_token.user_login
                else:
                    authenticated_user = github.get_user()
                    owner_login = authenticated_user.login
            else:
                authenticated_user = github.get_user()
                owner_login = authenticated_user.login
                
            repo = github.get_repo(f"{owner_login}/{repo_name}")
            commits = []
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)

            for commit in repo.get_commits(since=cutoff_date):
                if len(commits) >= limit:
                    break

                commits.append(
                    GitHubCommit(
                        sha=commit.sha[:8],
                        message=commit.commit.message,
                        author=commit.commit.author.name,
                        date=(
                            commit.commit.author.date.astimezone(timezone.utc).isoformat()
                            if commit.commit.author.date.tzinfo
                            else commit.commit.author.date.replace(tzinfo=timezone.utc).isoformat()
                        ),
                        url=commit.html_url,
                    )
                )

            return CommitResponse(
                status='success',
                data=commits,
                count=len(commits),
                message=f'Successfully retrieved {len(commits)} commits for repository {repo_name} in the last {days} days',
            )
        except Exception as e:
            return CommitResponse(
                status='error',
                message=f'Failed to get commits: {e!s}',
                error_message=f'Failed to get commits: {e!s}',
            )

    

    def get_tools(self) -> dict[str, Any]:
        """Return dictionary of available tools for OpenAI function calling"""
        return {
            'get_user_repositories': self,
            'get_recent_commits': self,
            'get_latest_commit_with_diff': self,
            'get_commit_diff': self,
        }
    
    @classmethod
    def create_with_user_id(cls, user_id: str) -> 'GitHubToolset':
        """Create GitHubToolset instance with user_id for OAuth authentication"""
        return cls(user_id=user_id)
