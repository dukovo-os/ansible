# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""The restart of dukovo.system.update.

A module runs on the machine it changes, so it cannot wait for that
machine to restart. This action plugin runs the module, and when the task
has state=applied and reboot=true and an update waits for a restart, asks
the reboot action of Ansible to restart the machine and wait for it. It then
runs the module again to read sysupdate status, and fails unless that says
the staged update is the one that runs.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

from ansible.module_utils.parsing.convert_bool import boolean
from ansible.plugins.action import ActionBase

# How the machine's start is told from the one before: the number of its record, which the
# health check writes into /system/live/sysupdate once it begins. It is a new number at each
# start, and it is not there until the services are up, so a command that fails there is
# retried by the reboot action until the machine has come back.
BOOT_TIME_COMMAND = "cat /system/live/sysupdate/start"

# The command that restarts the machine, which Spark stops the services for.
REBOOT_COMMAND = "reboot"


class ActionModule(ActionBase):
    """Runs the update module, and restarts the machine into the update it staged."""

    def _restart(self, task_vars, timeout):
        """Restarts the machine and waits for it, with Ansible's reboot action."""
        task = self._task.copy()
        task.args = {
            "reboot_command": REBOOT_COMMAND,
            "boot_time_command": BOOT_TIME_COMMAND,
            "reboot_timeout": timeout,
            "msg": "Restarting into the update (dukovo.system.update)",
        }
        task.action = "ansible.builtin.reboot"
        action = self._shared_loader_obj.action_loader.get(
            "ansible.builtin.reboot",
            task=task,
            connection=self._connection,
            play_context=self._play_context,
            loader=self._loader,
            templar=self._templar,
            shared_loader_obj=self._shared_loader_obj,
        )
        return action.run(task_vars=task_vars)

    def run(self, tmp=None, task_vars=None):
        self._supports_check_mode = True
        result = super(ActionModule, self).run(tmp, task_vars)
        del tmp
        args = self._task.args
        restart = args.get("state") == "applied" and boolean(args.get("reboot", False), strict=False)
        timeout = int(args.get("reboot_timeout", 600))
        result.update(self._execute_module(task_vars=task_vars))
        if result.get("failed") or not restart or self._task.check_mode:
            return result
        if not result.get("reboot_needed"):
            return result
        staged_slot, staged_version = result["staged_slot"], result["staged_version"]
        restarted = self._restart(task_vars, timeout)
        if restarted.get("failed"):
            result.update(
                failed=True,
                changed=True,
                msg="the machine did not come back after the restart into the update: %s"
                % restarted.get("msg", "the reboot action failed"),
            )
            return result
        after = self._execute_module(module_args={"state": "checked"}, task_vars=task_vars)
        if after.get("failed"):
            result.update(
                failed=True,
                changed=True,
                msg="the machine came back, and its status cannot be read: %s" % after.get("msg"),
            )
            return result
        result.update(
            changed=True,
            rebooted=True,
            reboot_needed=after["reboot_needed"],
            running_version=after["running_version"],
            running_slot=after["running_slot"],
            staged_version=after["staged_version"],
            staged_slot=after["staged_slot"],
            status=after["status"],
        )
        if after["running_slot"] != staged_slot or after["running_version"] != staged_version:
            result.update(
                failed=True,
                msg="the machine restarted, but Dukovo %s runs in slot %s, not the update to %s in "
                "slot %s; update history says how the update ended"
                % (after["running_version"], after["running_slot"], staged_version, staged_slot),
            )
        return result
