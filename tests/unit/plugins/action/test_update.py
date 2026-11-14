# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from unittest import mock

import pytest

from ansible.plugins.action import ActionBase

from ansible_collections.dukovo.system.plugins.action import update


def waiting(**changes):
    """What the module says of a machine with an update staged into slot b."""
    said = {
        "changed": False,
        "reboot_needed": True,
        "running_slot": "a",
        "running_version": "0.15.0",
        "staged_slot": "b",
        "staged_version": "0.16.0",
        "status": {"running": "a"},
    }
    said.update(changes)
    return said


def running(**changes):
    """What the module says once the machine runs the update."""
    said = {
        "changed": False,
        "reboot_needed": False,
        "running_slot": "b",
        "running_version": "0.16.0",
        "staged_slot": None,
        "staged_version": None,
        "status": {"running": "b"},
    }
    said.update(changes)
    return said


class Plugin(object):
    """An action plugin with its task and what it asks of Ansible made up."""

    def __init__(self, args, module_results, restart_result=None, check_mode=False):
        self.module_calls = []
        self.restarts = []
        results = list(module_results)

        def execute_module(module_args=None, task_vars=None, **unused):
            self.module_calls.append(module_args)
            return results.pop(0)

        def restart(task_vars, timeout):
            self.restarts.append(timeout)
            return restart_result or {"changed": True, "rebooted": True}

        self.action = update.ActionModule.__new__(update.ActionModule)
        self.action._task = mock.Mock(args=args, check_mode=check_mode)
        self.action._execute_module = execute_module
        self.action._restart = restart

    def run(self):
        with mock.patch.object(ActionBase, "run", return_value={}):
            return self.action.run(task_vars={})


def test_a_task_without_reboot_only_runs_the_module():
    plugin = Plugin({"state": "applied"}, [waiting()])
    result = plugin.run()
    assert plugin.restarts == []
    assert result["reboot_needed"] is True
    assert result["changed"] is False


def test_checked_and_staged_never_restart():
    for state in ("checked", "staged", "channel"):
        plugin = Plugin({"state": state, "reboot": True}, [waiting()])
        plugin.run()
        assert plugin.restarts == []


def test_check_mode_does_not_restart():
    plugin = Plugin({"state": "applied", "reboot": True}, [waiting(changed=True)], check_mode=True)
    result = plugin.run()
    assert plugin.restarts == []
    assert result["changed"] is True


def test_nothing_staged_does_not_restart():
    plugin = Plugin({"state": "applied", "reboot": True}, [waiting(reboot_needed=False, staged_slot=None)])
    result = plugin.run()
    assert plugin.restarts == []
    assert result["changed"] is False


def test_a_module_that_fails_does_not_restart():
    plugin = Plugin({"state": "applied", "reboot": True}, [{"failed": True, "msg": "UPD-110"}])
    assert plugin.run()["failed"] is True
    assert plugin.restarts == []


def test_a_staged_update_is_restarted_into_and_found_running():
    plugin = Plugin({"state": "applied", "reboot": True, "reboot_timeout": 900}, [waiting(), running()])
    result = plugin.run()
    assert plugin.restarts == [900]
    assert plugin.module_calls == [None, {"state": "checked"}]
    assert not result.get("failed")
    assert result["changed"] is True
    assert result["rebooted"] is True
    assert result["running_version"] == "0.16.0"
    assert result["running_slot"] == "b"
    assert result["reboot_needed"] is False


def test_the_timeout_is_ten_minutes_unless_the_task_says():
    plugin = Plugin({"state": "applied", "reboot": "yes"}, [waiting(), running()])
    plugin.run()
    assert plugin.restarts == [600]


def test_a_machine_that_comes_back_on_the_old_version_fails_the_task():
    fell_back = running(running_slot="a", running_version="0.15.0")
    plugin = Plugin({"state": "applied", "reboot": True}, [waiting(), fell_back])
    result = plugin.run()
    assert result["failed"] is True
    assert result["changed"] is True
    assert "runs in slot a, not the update to 0.16.0 in slot b" in result["msg"]
    assert result["running_version"] == "0.15.0"


def test_a_machine_that_does_not_come_back_fails_the_task():
    plugin = Plugin(
        {"state": "applied", "reboot": True},
        [waiting()],
        restart_result={"failed": True, "msg": "Timed out waiting for last boot time check"},
    )
    result = plugin.run()
    assert result["failed"] is True
    assert "did not come back" in result["msg"]
    assert "Timed out" in result["msg"]


def test_a_status_that_cannot_be_read_after_the_restart_fails_the_task():
    plugin = Plugin({"state": "applied", "reboot": True}, [waiting(), {"failed": True, "msg": "no answer"}])
    result = plugin.run()
    assert result["failed"] is True
    assert "status cannot be read" in result["msg"]


@pytest.mark.parametrize("value", [False, "no", "false"])
def test_reboot_false_in_any_spelling_does_not_restart(value):
    plugin = Plugin({"state": "applied", "reboot": value}, [waiting()])
    plugin.run()
    assert plugin.restarts == []
