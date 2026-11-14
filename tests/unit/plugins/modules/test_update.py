# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

from ansible_collections.dukovo.system.plugins.modules import update

from .conftest import document, fixture

STATUS = "sysupdate status --json"
CHECK = "update check --json"
APPLY = "update apply --yes"


def nothing_offered():
    """The recorded check, with each part of the system and firmware up to date."""
    recorded = document("update")
    for each in recorded["offers"]:
        if each["item"] in ("system", "firmware"):
            each["state"] = "current"
    recorded["unchecked"] = []
    return json.dumps(recorded)


def firmware_only():
    """The recorded check, with the system up to date and a firmware set on offer."""
    recorded = json.loads(nothing_offered())
    for each in recorded["offers"]:
        if each["item"] == "firmware":
            each["state"] = "update"
    return json.dumps(recorded)


def system_unchecked():
    recorded = document("update")
    recorded["offers"] = recorded["offers"][1:]
    recorded["unchecked"] = [{"item": "system", "why": "the update server cannot be reached"}]
    return json.dumps(recorded)


def after_stage():
    """The recorded status of a machine that staged an update into slot b."""
    recorded = document("sysupdate-status")
    recorded["staged"]["tries_left"] = 3
    return json.dumps(recorded)


def test_checked_reads_the_status_and_what_is_offered_and_changes_nothing(machine):
    machine.says(STATUS, fixture("sysupdate-status")).says(CHECK, fixture("update"))
    outcome = machine.run(update.main)
    assert not outcome.failed
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["running_version"] == "0.15.0"
    assert outcome.result["staged_version"] == "0.16.0"
    assert outcome.result["staged_slot"] == "b"
    assert outcome.result["reboot_needed"] is True
    assert outcome.result["status"]["channel"] == "beta"
    assert "format" not in outcome.result["status"]
    assert outcome.result["updates"]["offers"][0]["item"] == "system"
    assert "diff" not in machine.run(update.main, diff=True).result


def test_checked_of_a_machine_with_nothing_staged_needs_no_restart(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(CHECK, nothing_offered())
    outcome = machine.run(update.main, state="checked")
    assert outcome.result["reboot_needed"] is False
    assert outcome.result["staged_version"] is None
    assert outcome.result["staged_slot"] is None
    assert outcome.result["running_version"] == "0.15.0"


def test_an_update_that_is_running_but_has_not_proved_itself_needs_no_restart(machine):
    running = document("sysupdate-status")
    running["running"], running["staged"]["slot"] = "b", "b"
    machine.says(STATUS, json.dumps(running)).says(CHECK, nothing_offered())
    outcome = machine.run(update.main)
    assert outcome.result["reboot_needed"] is False
    assert outcome.result["running_version"] == "0.16.0"


def test_an_update_that_ran_out_of_tries_is_not_waiting_for_a_restart(machine):
    failed = document("sysupdate-status")
    failed["staged"]["tries_left"] = 0
    machine.says(STATUS, json.dumps(failed)).says(CHECK, nothing_offered())
    assert machine.run(update.main).result["reboot_needed"] is False


def test_staged_stages_the_update_the_channel_offers(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(STATUS, after_stage())
    machine.says(CHECK, fixture("update")).says(APPLY, "System: staged\n")
    outcome = machine.run(update.main, state="staged")
    assert outcome.result["changed"] is True
    assert outcome.changing == [APPLY]
    assert outcome.result["reboot_needed"] is True
    assert outcome.result["staged_version"] == "0.16.0"
    assert outcome.result["commands"] == [APPLY]


def test_staged_is_unchanged_when_an_update_is_staged_already(machine):
    machine.says(STATUS, fixture("sysupdate-status")).says(CHECK, fixture("update"))
    outcome = machine.run(update.main, state="staged")
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["reboot_needed"] is True


def test_staged_is_unchanged_when_nothing_waits(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(CHECK, nothing_offered())
    outcome = machine.run(update.main, state="staged")
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["reboot_needed"] is False


def test_staged_takes_a_firmware_set_when_no_system_update_waits(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(STATUS, after_stage())
    machine.says(CHECK, firmware_only())
    outcome = machine.run(update.main, state="staged")
    assert outcome.changing == [APPLY]


def test_check_mode_of_staged_says_it_would_stage_and_runs_nothing_that_changes(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(CHECK, fixture("update"))
    outcome = machine.run(update.main, state="staged", check=True, diff=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.ran == [STATUS, CHECK]
    assert outcome.result["diff"]["before"]["reboot_needed"] is False
    assert outcome.result["diff"]["after"]["reboot_needed"] is True
    assert outcome.result["diff"]["after"]["staged_version"] == "0.16.0"


def test_diff_mode_of_staged_gives_the_versions_before_and_after(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(STATUS, after_stage())
    machine.says(CHECK, fixture("update"))
    diff = machine.run(update.main, state="staged", diff=True).result["diff"]
    assert diff["before"]["staged_version"] is None
    assert diff["after"]["staged_version"] == "0.16.0"
    assert diff["after"]["running_version"] == "0.15.0"


def test_staged_fails_when_the_system_cannot_be_checked(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(CHECK, system_unchecked())
    outcome = machine.run(update.main, state="staged")
    assert outcome.failed
    assert "the system cannot be checked: the update server cannot be reached" in outcome.result["msg"]
    assert outcome.changing == []


def test_applied_without_reboot_stages_and_says_a_restart_is_needed(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(STATUS, after_stage())
    machine.says(CHECK, fixture("update"))
    outcome = machine.run(update.main, state="applied")
    assert outcome.result["changed"] is True
    assert outcome.changing == [APPLY]
    assert outcome.result["reboot_needed"] is True


def test_applied_with_an_update_staged_already_leaves_the_restart_to_the_action(machine):
    machine.says(STATUS, fixture("sysupdate-status")).says(CHECK, fixture("update"))
    outcome = machine.run(update.main, state="applied", reboot=True)
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["reboot_needed"] is True
    assert outcome.result["staged_slot"] == "b"


def test_applied_of_a_machine_with_nothing_to_update_is_no_change(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(CHECK, nothing_offered())
    outcome = machine.run(update.main, state="applied", reboot=True)
    assert outcome.result["changed"] is False
    assert outcome.result["reboot_needed"] is False


def test_check_mode_of_applied_with_reboot_says_it_would_restart(machine):
    machine.says(STATUS, fixture("sysupdate-status")).says(CHECK, fixture("update"))
    outcome = machine.run(update.main, state="applied", reboot=True, check=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []


def test_check_mode_of_applied_without_reboot_with_a_staged_update_changes_nothing(machine):
    machine.says(STATUS, fixture("sysupdate-status")).says(CHECK, fixture("update"))
    outcome = machine.run(update.main, state="applied", check=True)
    assert outcome.result["changed"] is False


def test_a_stage_that_fails_fails_the_module_with_its_error_id(machine):
    machine.says(STATUS, fixture("sysupdate-status-idle")).says(CHECK, fixture("update"))
    machine.says(
        APPLY,
        rc=1,
        stdout="update: checking\n",
        stderr="update: the update could not be staged: the spare slot is full (UPD-110)\n",
    )
    outcome = machine.run(update.main, state="staged")
    assert outcome.failed
    assert outcome.result["error_id"] == "UPD-110"
    assert outcome.result["rc"] == 1
    assert "UPD-110" in outcome.result["msg"]
    assert outcome.result["stdout"] == "update: checking\n"


def test_channel_changes_the_channel_the_machine_follows(machine):
    after = document("sysupdate-status")
    after["channel"] = "stable"
    machine.says(STATUS, fixture("sysupdate-status")).says(STATUS, json.dumps(after))
    outcome = machine.run(update.main, state="channel", channel="stable", diff=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == ["sysupdate channel stable"]
    assert outcome.result["status"]["channel"] == "stable"
    assert outcome.result["diff"] == {"before": {"channel": "beta"}, "after": {"channel": "stable"}}


def test_channel_is_unchanged_when_the_machine_follows_it(machine):
    machine.says(STATUS, fixture("sysupdate-status"))
    outcome = machine.run(update.main, state="channel", channel="beta", diff=True)
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["diff"]["before"] == outcome.result["diff"]["after"]


def test_check_mode_of_channel_says_it_would_change_it(machine):
    machine.says(STATUS, fixture("sysupdate-status"))
    outcome = machine.run(update.main, state="channel", channel="nightly", check=True, diff=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.result["diff"]["after"] == {"channel": "nightly"}


def test_a_channel_that_fails_to_change_fails_the_module(machine):
    machine.says(STATUS, fixture("sysupdate-status"))
    machine.says("sysupdate channel stable", rc=1, stderr="sysupdate: /system/settings/updates.toml: read-only (UPD-120)\n")
    outcome = machine.run(update.main, state="channel", channel="stable")
    assert outcome.failed
    assert outcome.result["error_id"] == "UPD-120"


def test_held_holds_what_is_not_held(machine):
    held = document("sysupdate-status")
    held["held"]["firmware"] = "2026.3"
    machine.says(STATUS, fixture("sysupdate-status")).says(STATUS, json.dumps(held))
    outcome = machine.run(update.main, state="held", item="firmware", diff=True)
    assert outcome.changing == ["update hold firmware"]
    assert outcome.result["diff"] == {
        "before": {"item": "firmware", "held": False},
        "after": {"item": "firmware", "held": True},
    }
    assert outcome.result["status"]["held"]["firmware"] == "2026.3"


def test_held_is_unchanged_for_what_is_held_already(machine):
    machine.says(STATUS, fixture("sysupdate-status"))
    outcome = machine.run(update.main, state="held", item="system")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_unheld_lets_go_of_what_is_held(machine):
    free = document("sysupdate-status")
    free["held"]["system"] = None
    machine.says(STATUS, fixture("sysupdate-status")).says(STATUS, json.dumps(free))
    outcome = machine.run(update.main, state="unheld", item="system")
    assert outcome.changing == ["update unhold system"]
    assert outcome.result["status"]["held"]["system"] is None


def test_unheld_is_unchanged_for_what_is_not_held(machine):
    machine.says(STATUS, fixture("sysupdate-status"))
    outcome = machine.run(update.main, state="unheld", item="firmware")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_check_mode_of_held_and_unheld_runs_nothing_that_changes(machine):
    machine.says(STATUS, fixture("sysupdate-status"))
    held = machine.run(update.main, state="held", item="firmware", check=True)
    assert held.result["changed"] is True
    assert held.changing == []
    unheld = machine.run(update.main, state="unheld", item="system", check=True)
    assert unheld.result["changed"] is True
    assert unheld.changing == []


def test_a_channel_a_state_needs_is_required(machine):
    machine.says(STATUS, fixture("sysupdate-status"))
    assert machine.run(update.main, state="channel").failed
    assert machine.run(update.main, state="held").failed
    assert machine.run(update.main, state="unheld").failed


def test_a_failing_read_fails_the_module(machine):
    machine.says(STATUS, rc=1, stderr="sysupdate: this system did not start from a Dukovo root on a disk\n")
    outcome = machine.run(update.main)
    assert outcome.failed
    assert "did not start from a Dukovo root" in outcome.result["msg"]
