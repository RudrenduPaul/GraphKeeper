"""Ported from test/git.test.ts."""
from __future__ import annotations

import tempfile

import pytest

from graphkeeper.git import GitError, assert_is_git_repo, mine_co_change, unquote_git_path

from .conftest import cleanup, commit_all, make_temp_git_repo, run_git, write_file


@pytest.fixture
def temp_repo():
    dirs = []

    def _make():
        d = make_temp_git_repo()
        dirs.append(d)
        return d

    yield _make
    for d in dirs:
        cleanup(d)


def test_assert_is_git_repo_does_not_throw_for_real_repo(temp_repo):
    repo = temp_repo()
    assert_is_git_repo(repo)  # does not raise


def test_assert_is_git_repo_raises_for_non_repo():
    plain = tempfile.mkdtemp(prefix="gk-plain-")
    try:
        with pytest.raises(GitError):
            assert_is_git_repo(plain)
    finally:
        cleanup(plain)


class TestUnquoteGitPath:
    def test_returns_plain_paths_unchanged(self):
        assert unquote_git_path("src/index.py") == "src/index.py"

    def test_unquotes_c_quoted_path_with_escaped_quote(self):
        assert unquote_git_path('"weird\\"file.py"') == 'weird"file.py'

    def test_unquotes_octal_escapes(self):
        # \303\251 is UTF-8 for "e-acute" when git quotes bytes individually.
        assert unquote_git_path('"caf\\303\\251.py"') == "café.py"

    def test_unquotes_n_and_t_control_char_escapes(self):
        assert unquote_git_path('"line\\nbreak.py"') == "line\nbreak.py"
        assert unquote_git_path('"tab\\tstop.py"') == "tab\tstop.py"

    def test_passes_unrecognized_escape_literal_char_through(self):
        assert unquote_git_path('"weird\\qfile.py"') == "weirdqfile.py"

    def test_keeps_trailing_backslash_with_nothing_after_it(self):
        assert unquote_git_path('"trailing\\"') == "trailing\\"


def test_mine_co_change_raises_git_error_when_git_log_fails():
    dir_ = tempfile.mkdtemp(prefix="gk-unborn-")
    try:
        run_git(dir_, ["init", "-q"])
        with pytest.raises(GitError):
            mine_co_change(dir_)
    finally:
        cleanup(dir_)


class TestMineCoChange:
    def test_returns_no_data_for_single_empty_commit(self, temp_repo):
        repo = temp_repo()
        result = mine_co_change(repo)
        assert result.co_change == []
        assert result.commits_analyzed == 0

    def test_counts_pair_of_files_changing_together(self, temp_repo):
        repo = temp_repo()
        write_file(repo, "a.py", "1")
        write_file(repo, "b.py", "1")
        commit_all(repo, "add a and b")
        write_file(repo, "a.py", "2")
        write_file(repo, "b.py", "2")
        commit_all(repo, "touch a and b again")
        write_file(repo, "c.py", "1")
        commit_all(repo, "add c alone")

        result = mine_co_change(repo)
        assert result.commits_analyzed == 3
        pair = next(
            (e for e in result.co_change if (e.a == "a.py" and e.b == "b.py") or (e.a == "b.py" and e.b == "a.py")),
            None,
        )
        assert pair is not None
        assert pair.count == 2
        # c.py never co-occurred with anything.
        assert not any(e.a == "c.py" or e.b == "c.py" for e in result.co_change)
        assert result.file_commit_counts["a.py"] == 2
        assert result.file_commit_counts["c.py"] == 1

    def test_skips_commits_touching_more_files_than_max(self, temp_repo):
        repo = temp_repo()
        for i in range(5):
            write_file(repo, f"f{i}.py", "1")
        commit_all(repo, "touch 5 files")

        result = mine_co_change(repo, max_files_per_commit=3)
        assert result.commits_analyzed == 0
        assert result.commits_skipped == 1
        assert result.co_change == []

    def test_excludes_merge_commits(self, temp_repo):
        repo = temp_repo()
        write_file(repo, "main.py", "1")
        commit_all(repo, "base")
        run_git(repo, ["checkout", "-q", "-b", "feature"])
        write_file(repo, "feature.py", "1")
        commit_all(repo, "feature work")
        run_git(repo, ["checkout", "-q", "-"])
        write_file(repo, "other.py", "1")
        commit_all(repo, "unrelated work on main")
        run_git(repo, ["merge", "-q", "--no-ff", "-m", "merge feature", "feature"])

        result = mine_co_change(repo)
        # 3 real commits (base, feature work, unrelated), merge commit excluded.
        assert result.commits_analyzed == 3

    def test_sorts_results_by_descending_co_change_count(self, temp_repo):
        repo = temp_repo()
        write_file(repo, "x.py", "1")
        write_file(repo, "y.py", "1")
        commit_all(repo, "x+y once")
        write_file(repo, "x.py", "2")
        write_file(repo, "z.py", "1")
        commit_all(repo, "x+z once")
        write_file(repo, "x.py", "3")
        write_file(repo, "z.py", "2")
        commit_all(repo, "x+z twice")

        result = mine_co_change(repo)
        assert result.co_change[0].count >= result.co_change[1].count
