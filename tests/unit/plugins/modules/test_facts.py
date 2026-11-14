# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

from ansible_collections.dukovo.system.plugins.modules import facts

from .conftest import fixture

READS = {
    "feature list --json": "feature-list",
    "service list --json": "service-list",
    "bundle list --json": "bundle-list",
}
STATUS = "sysupdate status --json"
CHECK = "dukovo-check --last --json"


def recorded(machine, status="sysupdate-status", check="check-last"):
    for command, name in READS.items():
        machine.says(command, fixture(name))
    machine.says(STATUS, fixture(status))
    if check:
        machine.says(CHECK, fixture(check))
    return machine


def test_the_facts_say_the_release_the_slot_the_channel_and_the_wave(machine):
    outcome = recorded(machine).run(facts.main)
    assert not outcome.failed
    assert outcome.result["changed"] is False
    dukovo = outcome.result["ansible_facts"]["dukovo"]
    assert dukovo["version"] == "0.15.0"
    assert dukovo["slot"] == "a"
    assert dukovo["firmware"] == "2026.2"
    assert dukovo["channel"] == "beta"
    assert dukovo["wave"] == 412
    assert dukovo["canary"] is True
    assert dukovo["rescue"] == "0.14.0"
    assert dukovo["held"] == {"system": "0.16.0", "firmware": None}


def test_the_facts_name_the_update_waiting_for_a_restart(machine):
    dukovo = recorded(machine).run(facts.main).result["ansible_facts"]["dukovo"]
    assert dukovo["staged"] == {"slot": "b", "version": "0.16.0", "tries_left": 2}


def test_a_machine_with_nothing_staged_says_none(machine):
    dukovo = recorded(machine, "sysupdate-status-idle").run(facts.main).result["ansible_facts"]["dukovo"]
    assert dukovo["staged"] is None
    assert dukovo["wave"] is None
    assert dukovo["rescue"] is None
    assert dukovo["canary"] is False


def test_the_facts_hold_the_features_the_services_and_the_bundles(machine):
    dukovo = recorded(machine).run(facts.main).result["ansible_facts"]["dukovo"]
    assert dukovo["features"] == {"developer-tools": "added", "file-sharing": "partly"}
    assert dukovo["services"]["sshd"] == "running"
    assert dukovo["services"]["nginx"] == "disabled"
    assert len(dukovo["services"]) == 5
    nginx = [each for each in dukovo["bundles"] if each["id"] == "org.nginx.nginx" and each["for_everyone"]]
    assert nginx == [
        {"id": "org.nginx.nginx", "version": "1.2.0", "for_everyone": True, "held": False, "update": "1.3.0"}
    ]
    assert len(dukovo["bundles"]) == 3


def test_the_facts_hold_the_last_check(machine):
    dukovo = recorded(machine).run(facts.main).result["ansible_facts"]["dukovo"]
    assert dukovo["check"] == {
        "checked": "2026-11-12T05:17:03Z",
        "release": "0.15.0",
        "counts": {"passed": 13, "warning": 1, "failed": 0, "skipped": 1},
    }


def test_a_check_that_cannot_be_read_is_none(machine):
    recorded(machine, check=None).says(CHECK, rc=1, stderr="dukovo-check: no result is kept\n")
    outcome = machine.run(facts.main)
    assert outcome.result["ansible_facts"]["dukovo"]["check"] is None


def test_a_check_of_another_version_is_none(machine):
    recorded(machine, check=None).says(CHECK, json.dumps({"version": 2}))
    assert machine.run(facts.main).result["ansible_facts"]["dukovo"]["check"] is None


def test_the_facts_run_in_check_mode_and_change_nothing(machine):
    outcome = recorded(machine).run(facts.main, check=True)
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert all(command.endswith("--json") for command in outcome.ran)


def test_a_command_that_fails_fails_the_module_with_its_error_id(machine):
    recorded(machine).script[STATUS] = [(1, "", "sysupdate: the slot state cannot be read (BOOT-104)\n")]
    outcome = machine.run(facts.main)
    assert outcome.failed
    assert outcome.result["error_id"] == "BOOT-104"
    assert outcome.result["rc"] == 1
    assert "BOOT-104" in outcome.result["msg"]
