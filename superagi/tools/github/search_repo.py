from typing import Type

from pydantic import BaseModel, Field

from superagi.config.config import get_config
from superagi.helper.github_helper import GithubHelper
from superagi.tools.base_tool import BaseTool


class GithubSearchRepoSchema(BaseModel):
    repository_name: str = Field(
        ...,
        description="Repository name in which we have to search",
    )
    repository_owner: str = Field(
        ...,
        description="Owner of the github repository",
    )
    file_name: str = Field(
        ...,
        description="Name of the file we need to fetch from the repository",
    )
    folder_path: str = Field(
        ...,
        description="folder path in which file is present",
    )


class GithubRepoSearchTool(BaseTool):
    name = "GithubRepo Search"
    description = (
        "Search for a file inside a Github repository"
    )
    args_schema: Type[GithubSearchRepoSchema] = GithubSearchRepoSchema

    def _execute(self, repository_owner: str, repository_name: str, file_name: str, folder_path=None) -> str:
        github_access_token = get_config("GITHUB_ACCESS_TOKEN")
        github_username = get_config("GITHUB_USERNAME")
        github_repo_search = GithubHelper(github_access_token, github_username)
        content = github_repo_search.get_content_in_file(repository_owner, repository_name, file_name, folder_path)

        return content
