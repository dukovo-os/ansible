# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

import pytest

from ansible_collections.dukovo.system.plugins.modules import service

from .conftest import document, fixture

LIST = "service list --json"


def with_service(name, **changes):
    """The recorded service list with some members of one service changed."""
    recorded = document("service-list")
    for each in recorded["services"]:
        if each["name"] == name:
            each.update(changes)
    return json.dumps(recorded)


def test_a_service_that_runs_is_started_without_a_command(machine):
    machine.says(LIST, fixture("service-list"))
    outcome = machine.run(service.main, name="consoled", state="started")
    assert not outcome.failed
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["service"] == {"name": "consoled", "state": "running", "enabled": True}


@pytest.mark.parametrize("name", ["nginx", "web", "snap"])
def test_a_service_that_does_not_run_is_started(machine, name):
    machine.says(LIST, fixture("service-list")).says(LIST, with_service(name, state="running"))
    outcome = machine.run(service.main, name=name, state="started")
    assert outcome.result["changed"] is True
    assert outcome.changing == ["service %s start" % name]
    assert outcome.result["service"]["state"] == "running"


def test_enabled_and_started_enables_it_and_then_starts_it(machine):
    machine.says(LIST, fixture("service-list")).says(
        LIST, with_service("nginx", state="running", enabled=True)
    )
    outcome = machine.run(service.main, name="nginx", state="started", enabled=True)
    assert outcome.changing == ["service nginx enable", "service nginx start"]
    assert outcome.result["service"] == {"name": "nginx", "state": "running", "enabled": True}


def test_a_service_that_is_enabled_is_not_enabled_again(machine):
    machine.says(LIST, fixture("service-list"))
    outcome = machine.run(service.main, name="consoled", enabled=True)
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_a_running_service_that_is_not_enabled_is_enabled_and_left_running(machine):
    machine.says(LIST, fixture("service-list")).says(LIST, with_service("sshd", enabled=True))
    outcome = machine.run(service.main, name="sshd", state="started", enabled=True)
    assert outcome.changing == ["service sshd enable"]


def test_enabled_false_disables_a_service_that_starts_at_boot(machine):
    machine.says(LIST, fixture("service-list")).says(LIST, with_service("consoled", enabled=False))
    outcome = machine.run(service.main, name="consoled", enabled=False)
    assert outcome.changing == ["service consoled disable"]


def test_a_service_that_runs_is_stopped(machine):
    machine.says(LIST, fixture("service-list")).says(LIST, with_service("sshd", state="stopped"))
    outcome = machine.run(service.main, name="sshd", state="stopped")
    assert outcome.changing == ["service sshd stop"]
    assert outcome.result["service"]["state"] == "stopped"


@pytest.mark.parametrize("name", ["nginx", "web", "snap"])
def test_a_service_that_does_not_run_is_stopped_without_a_command(machine, name):
    machine.says(LIST, fixture("service-list"))
    outcome = machine.run(service.main, name=name, state="stopped")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_stopped_and_disabled_stops_it_and_turns_it_off_at_boot(machine):
    machine.says(LIST, fixture("service-list")).says(
        LIST, with_service("consoled", state="stopped", enabled=False)
    )
    outcome = machine.run(service.main, name="consoled", state="stopped", enabled=False)
    assert outcome.changing == ["service consoled disable", "service consoled stop"]


def test_restarted_and_reloaded_always_run(machine):
    machine.says(LIST, fixture("service-list"))
    restarted = machine.run(service.main, name="consoled", state="restarted")
    assert restarted.result["changed"] is True
    assert restarted.changing == ["service consoled restart"]
    reloaded = machine.run(service.main, name="consoled", state="reloaded")
    assert reloaded.result["changed"] is True
    assert reloaded.changing[-1] == "service consoled reload"


def test_check_mode_says_it_would_start_and_runs_nothing_that_changes(machine):
    machine.says(LIST, fixture("service-list"))
    outcome = machine.run(service.main, name="nginx", state="started", enabled=True, check=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.ran == [LIST]
    assert outcome.result["commands"] == ["service nginx enable", "service nginx start"]
    assert outcome.result["service"] == {"name": "nginx", "state": "running", "enabled": True}


def test_check_mode_of_a_service_that_is_as_asked_changes_nothing(machine):
    machine.says(LIST, fixture("service-list"))
    outcome = machine.run(service.main, name="consoled", state="started", check=True)
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_diff_mode_gives_the_service_before_and_after(machine):
    machine.says(LIST, fixture("service-list")).says(LIST, with_service("sshd", state="stopped"))
    diff = machine.run(service.main, name="sshd", state="stopped", diff=True).result["diff"]
    assert diff["before"] == {"name": "sshd", "state": "running", "enabled": False}
    assert diff["after"] == {"name": "sshd", "state": "stopped", "enabled": False}


def test_diff_mode_in_check_mode_predicts_the_after(machine):
    machine.says(LIST, fixture("service-list"))
    result = machine.run(service.main, name="sshd", state="stopped", diff=True, check=True).result
    assert result["diff"]["after"]["state"] == "stopped"


def test_no_diff_without_diff_mode(machine):
    machine.says(LIST, fixture("service-list"))
    assert "diff" not in machine.run(service.main, name="consoled", state="started").result


def test_a_service_there_is_not_fails_the_module(machine):
    machine.says(LIST, fixture("service-list"))
    outcome = machine.run(service.main, name="mail", state="started")
    assert outcome.failed
    assert "no such service: mail" in outcome.result["msg"]


def test_a_command_that_fails_fails_the_module_with_its_error_id(machine):
    machine.says(LIST, fixture("service-list"))
    machine.says(
        "service nginx start",
        rc=1,
        stderr="service: nginx did not become ready in 10 s: it exited with code 1 (SVC-102)\n",
    )
    outcome = machine.run(service.main, name="nginx", state="started")
    assert outcome.failed
    assert outcome.result["error_id"] == "SVC-102"
    assert outcome.result["rc"] == 1
    assert "SVC-102" in outcome.result["msg"]
    assert "did not become ready" in outcome.result["stderr"]


def test_a_document_of_another_show_version_is_refused(machine):
    machine.says(LIST, '{"show_version": 2, "services": []}')
    outcome = machine.run(service.main, name="sshd", state="started")
    assert outcome.failed
    assert "show_version 2" in outcome.result["msg"]


def test_a_state_or_enabled_is_needed(machine):
    machine.says(LIST, fixture("service-list"))
    outcome = machine.run(service.main, name="sshd")
    assert outcome.failed
    assert "state, enabled" in outcome.result["msg"]
