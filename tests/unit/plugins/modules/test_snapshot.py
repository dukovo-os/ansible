# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

from ansible_collections.dukovo.system.plugins.modules import snapshot

from .conftest import document, fixture

LIST = "snap list /users --json"
RECORDED = ["2026-11-12-0300", "before-the-upgrade", "2026-11-13-0300", "2026-11-14-0300", "unknown-time"]


def without(*names):
    """The recorded list of /users without some snapshots."""
    recorded = document("snap-list-place")
    recorded["snapshots"] = [each for each in recorded["snapshots"] if each["name"] not in names]
    return json.dumps(recorded)


def test_a_snapshot_that_is_there_is_present_without_a_command(machine):
    machine.says(LIST, fixture("snap-list-place"))
    outcome = machine.run(snapshot.main, place="/users", name="before-the-upgrade")
    assert not outcome.failed
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["snapshots"] == RECORDED


def test_a_snapshot_that_is_not_there_is_made_by_name(machine):
    machine.says(LIST, fixture("snap-list-place"))
    after = document("snap-list-place")
    after["snapshots"].append({"name": "kept", "made": "2026-11-14T10:00:00Z", "named": True, "kept": [], "prunable": False})
    machine.says(LIST, json.dumps(after))
    outcome = machine.run(snapshot.main, place="/users", name="kept")
    assert outcome.result["changed"] is True
    assert outcome.changing == ["snap create --name kept /users"]
    assert outcome.result["snapshots"][-1] == "kept"


def test_check_mode_says_it_would_make_the_snapshot_and_runs_nothing_that_changes(machine):
    machine.says(LIST, fixture("snap-list-place"))
    outcome = machine.run(snapshot.main, place="/users", name="kept", check=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.ran == [LIST]
    assert outcome.result["snapshots"] == RECORDED + ["kept"]


def test_diff_mode_gives_the_snapshots_before_and_after(machine):
    machine.says(LIST, fixture("snap-list-place")).says(LIST, without("2026-11-12-0300"))
    diff = machine.run(
        snapshot.main, place="/users", name="2026-11-12-0300", state="absent", diff=True
    ).result["diff"]
    assert diff["before"] == {"place": "/users", "snapshots": RECORDED}
    assert diff["after"] == {"place": "/users", "snapshots": RECORDED[1:]}


def test_no_diff_without_diff_mode(machine):
    machine.says(LIST, fixture("snap-list-place"))
    assert "diff" not in machine.run(snapshot.main, place="/users", name="before-the-upgrade").result


def test_absent_removes_a_snapshot_that_is_there(machine):
    machine.says(LIST, fixture("snap-list-place")).says(LIST, without("before-the-upgrade"))
    outcome = machine.run(snapshot.main, place="/users", name="before-the-upgrade", state="absent")
    assert outcome.changing == ["snap delete /users before-the-upgrade"]
    assert "before-the-upgrade" not in outcome.result["snapshots"]


def test_absent_of_a_snapshot_that_is_not_there_changes_nothing(machine):
    machine.says(LIST, fixture("snap-list-place"))
    outcome = machine.run(snapshot.main, place="/users", name="never-made", state="absent")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_check_mode_of_absent_says_it_would_remove(machine):
    machine.says(LIST, fixture("snap-list-place"))
    outcome = machine.run(
        snapshot.main, place="/users", name="before-the-upgrade", state="absent", check=True
    )
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert "before-the-upgrade" not in outcome.result["snapshots"]


def test_pruned_removes_what_retention_does_not_keep(machine):
    machine.says(LIST, fixture("snap-list-place")).says(LIST, without("2026-11-12-0300"))
    outcome = machine.run(snapshot.main, place="/users", state="pruned")
    assert outcome.result["changed"] is True
    assert outcome.changing == ["snap prune /users"]
    assert "2026-11-12-0300" not in outcome.result["snapshots"]


def test_pruned_changes_nothing_when_retention_keeps_every_snapshot(machine):
    machine.says(LIST, without("2026-11-12-0300"))
    outcome = machine.run(snapshot.main, place="/users", state="pruned")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_check_mode_of_pruned_predicts_the_snapshots_left(machine):
    machine.says(LIST, fixture("snap-list-place"))
    outcome = machine.run(snapshot.main, place="/users", state="pruned", check=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.result["snapshots"] == RECORDED[1:]


def test_a_name_is_needed_to_make_or_remove_a_snapshot(machine):
    outcome = machine.run(snapshot.main, place="/users", state="present")
    assert outcome.failed
    assert "name" in outcome.result["msg"]
    assert machine.run(snapshot.main, place="/users", state="absent").failed


def test_a_command_that_fails_fails_the_module_with_its_error_id(machine):
    machine.says(LIST, fixture("snap-list-place"))
    machine.says(
        "snap create --name kept /users",
        rc=1,
        stderr="snap: /users: kept exists already (SNAP-101)\n",
    )
    outcome = machine.run(snapshot.main, place="/users", name="kept")
    assert outcome.failed
    assert outcome.result["error_id"] == "SNAP-101"
    assert outcome.result["rc"] == 1
    assert "SNAP-101" in outcome.result["msg"]
    assert "kept exists already" in outcome.result["stderr"]


def test_a_place_that_cannot_be_read_fails_the_module(machine):
    machine.says(LIST, rc=1, stderr="snap: /users is not a subvolume\n")
    outcome = machine.run(snapshot.main, place="/users", name="kept")
    assert outcome.failed
    assert outcome.result["error_id"] is None
    assert "not a subvolume" in outcome.result["msg"]
