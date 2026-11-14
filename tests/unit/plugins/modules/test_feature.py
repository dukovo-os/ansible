# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

from ansible_collections.dukovo.system.plugins.modules import feature

from .conftest import document, fixture

LIST = "feature list --json"


def with_states(**states):
    """The recorded feature list with the state of some features set."""
    recorded = document("feature-list")
    for each in recorded["features"]:
        each["state"] = states.get(each["id"].replace("-", "_"), each["state"])
    return json.dumps(recorded)


def test_a_feature_that_is_added_is_present_without_a_command(machine):
    machine.says(LIST, fixture("feature-list"))
    outcome = machine.run(feature.main, name=["developer-tools"])
    assert not outcome.failed
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["features"] == {"developer-tools": "added"}


def test_a_feature_added_in_part_is_added_again(machine):
    machine.says(LIST, fixture("feature-list")).says(LIST, with_states(file_sharing="added"))
    outcome = machine.run(feature.main, name=["file-sharing"])
    assert outcome.result["changed"] is True
    assert outcome.changing == ["feature add --yes file-sharing"]
    assert outcome.result["features"] == {"file-sharing": "added"}


def test_only_the_features_that_are_not_added_are_added(machine):
    machine.says(LIST, fixture("feature-list")).says(LIST, with_states(file_sharing="added"))
    outcome = machine.run(feature.main, name=["developer-tools", "file-sharing"])
    assert outcome.changing == ["feature add --yes file-sharing"]
    assert outcome.result["features"] == {"developer-tools": "added", "file-sharing": "added"}


def test_check_mode_says_it_would_add_and_runs_nothing_that_changes(machine):
    machine.says(LIST, fixture("feature-list"))
    outcome = machine.run(feature.main, name=["file-sharing"], check=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.ran == [LIST]
    assert outcome.result["features"] == {"file-sharing": "added"}


def test_diff_mode_gives_the_states_before_and_after(machine):
    machine.says(LIST, fixture("feature-list")).says(LIST, with_states(file_sharing="added"))
    diff = machine.run(feature.main, name=["file-sharing"], diff=True).result["diff"]
    assert diff["before"] == {"file-sharing": "partly"}
    assert diff["after"] == {"file-sharing": "added"}


def test_diff_mode_of_check_mode_predicts_the_after(machine):
    machine.says(LIST, fixture("feature-list"))
    diff = machine.run(feature.main, name=["file-sharing"], diff=True, check=True).result["diff"]
    assert diff == {"before": {"file-sharing": "partly"}, "after": {"file-sharing": "added"}}


def test_no_diff_without_diff_mode(machine):
    machine.says(LIST, fixture("feature-list"))
    assert "diff" not in machine.run(feature.main, name=["developer-tools"]).result


def test_absent_removes_a_feature_that_is_added_and_keeps_its_data(machine):
    machine.says(LIST, fixture("feature-list")).says(LIST, with_states(developer_tools="not added"))
    outcome = machine.run(feature.main, name=["developer-tools"], state="absent")
    assert outcome.changing == ["feature remove developer-tools"]
    assert outcome.result["features"] == {"developer-tools": "not added"}


def test_absent_with_purge_removes_the_data_too(machine):
    machine.says(LIST, fixture("feature-list")).says(LIST, with_states(developer_tools="not added"))
    outcome = machine.run(feature.main, name=["developer-tools"], state="absent", purge=True)
    assert outcome.changing == ["feature remove --purge developer-tools"]


def test_absent_removes_a_feature_added_in_part(machine):
    machine.says(LIST, fixture("feature-list")).says(LIST, with_states(file_sharing="not added"))
    outcome = machine.run(feature.main, name=["file-sharing"], state="absent")
    assert outcome.changing == ["feature remove file-sharing"]


def test_absent_of_a_feature_that_is_not_added_changes_nothing(machine):
    machine.says(LIST, with_states(file_sharing="not added"))
    outcome = machine.run(feature.main, name=["file-sharing"], state="absent")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_check_mode_of_absent_says_it_would_remove(machine):
    machine.says(LIST, fixture("feature-list"))
    outcome = machine.run(feature.main, name=["developer-tools"], state="absent", check=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.result["features"] == {"developer-tools": "not added"}


def test_a_feature_there_is_not_fails_the_module_and_names_those_there_are(machine):
    machine.says(LIST, fixture("feature-list"))
    outcome = machine.run(feature.main, name=["mail"])
    assert outcome.failed
    assert "no such feature: mail" in outcome.result["msg"]
    assert "developer-tools, file-sharing" in outcome.result["msg"]
    assert outcome.changing == []


def test_a_command_that_fails_fails_the_module_with_its_error_id(machine):
    machine.says(LIST, fixture("feature-list"))
    machine.says(
        "feature add --yes file-sharing",
        rc=1,
        stdout="installing org.example.tool\n",
        stderr="feature: org.example.tool cannot be installed: no catalog lists it (UPD-203)\n",
    )
    outcome = machine.run(feature.main, name=["file-sharing"])
    assert outcome.failed
    assert outcome.result["error_id"] == "UPD-203"
    assert outcome.result["rc"] == 1
    assert "UPD-203" in outcome.result["msg"]
    assert outcome.result["stdout"] == "installing org.example.tool\n"
    assert "no catalog lists it" in outcome.result["stderr"]


def test_a_failing_read_fails_the_module(machine):
    machine.says(LIST, rc=1, stderr="feature: bundled does not answer\n")
    outcome = machine.run(feature.main, name=["file-sharing"])
    assert outcome.failed
    assert "bundled does not answer" in outcome.result["msg"]
