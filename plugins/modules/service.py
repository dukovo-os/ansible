#!/usr/bin/python
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: service
short_description: Start, stop and enable the services of Dukovo
version_added: 0.1.0
description:
  - Manages a service that Spark, Dukovo's first program, supervises, with C(service).
  - The module reads C(service list --json), which is Spark's own document of its services, and
    runs C(service NAME start), C(stop), C(restart), C(reload), C(enable) or C(disable) only when
    the service is not as asked, so a second run reports no change. V(restarted) and V(reloaded)
    always run, as they do in Ansible's other service modules.
extends_documentation_fragment:
  - ansible.builtin.action_common_attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
  platform:
    platforms: posix
options:
  name:
    description:
      - The service's name, its file's without C(.toml), as C(service list) shows it.
    type: str
    required: true
  state:
    description:
      - V(started) starts the service when it is not running, and waits until it is ready.
      - V(stopped) stops it when it runs, or waits to start again.
      - V(restarted) restarts it.
      - V(reloaded) asks it to read its settings again.
    type: str
    choices: [started, stopped, restarted, reloaded]
  enabled:
    description:
      - Whether the service starts at boot. Change it with or without O(state).
    type: bool
notes:
  - At least one of O(state) and O(enabled) is needed.
  - A service that starts at its first connection (V(listening)) is not running until one comes,
    so V(started) starts it.
author:
  - The Dukovo contributors (@dukovo-os)
"""

EXAMPLES = r"""
- name: Turn the SSH server on, now and at each boot
  dukovo.system.service:
    name: sshd
    state: started
    enabled: true

- name: Turn the web server off for good
  dukovo.system.service:
    name: nginx
    state: stopped
    enabled: false

- name: Read nginx's settings again
  dukovo.system.service:
    name: nginx
    state: reloaded
"""

RETURN = r"""
service:
  description: The service as it is after the module ran, or as it would be in check mode.
  returned: always
  type: dict
  contains:
    name:
      description: The service's name.
      type: str
      sample: sshd
    state:
      description: What it is doing, in Spark's words, such as V(running), V(stopped),
        V(disabled), V(failed) or V(waiting).
      type: str
      sample: running
    enabled:
      description: Whether it starts at boot.
      type: bool
commands:
  description: The commands the module ran, or would run in check mode.
  returned: always
  type: list
  elements: str
  sample: ["service sshd enable", "service sshd start"]
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.dukovo.system.plugins.module_utils.dukovo import Dukovo

# The states of Spark's document in which a service is running, or has run as it should and
# is done, and those in which it neither runs nor is to start by itself.
RUNNING = ("running", "starting", "done")
STOPPED = ("stopped", "disabled", "failed", "listening", "stopping")


def view(row):
    """The service as the module reports it, from its row of Spark's document."""
    return {"name": row["name"], "state": row["state"], "enabled": bool(row["enabled"])}


def find(document, name):
    """The row of Spark's document for the service, or None."""
    for row in document["services"]:
        if row["name"] == name:
            return row
    return None


def plan(params, before):
    """The commands that bring the service, as before says, to params."""
    name, state, enabled = params["name"], params["state"], params["enabled"]
    commands = []
    if enabled is not None and enabled != before["enabled"]:
        commands.append(["service", name, "enable" if enabled else "disable"])
    if state == "started" and before["state"] not in RUNNING:
        commands.append(["service", name, "start"])
    elif state == "stopped" and before["state"] not in STOPPED:
        commands.append(["service", name, "stop"])
    elif state == "restarted":
        commands.append(["service", name, "restart"])
    elif state == "reloaded":
        commands.append(["service", name, "reload"])
    return commands


def predict(params, before):
    """What the service comes to after plan's commands, for check mode."""
    after = dict(before)
    if params["enabled"] is not None:
        after["enabled"] = params["enabled"]
    if params["state"] in ("started", "restarted"):
        after["state"] = "running"
    elif params["state"] == "stopped":
        after["state"] = "stopped"
    return after


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="str", required=True),
            state=dict(type="str", choices=["started", "stopped", "restarted", "reloaded"]),
            enabled=dict(type="bool"),
        ),
        required_one_of=[["state", "enabled"]],
        supports_check_mode=True,
    )
    dukovo = Dukovo(module)
    params = module.params
    listed = ["service", "list", "--json"]
    row = find(dukovo.read(listed, "show_version"), params["name"])
    if row is None:
        module.fail_json(msg="no such service: %s; service list says which there are" % params["name"])
    before = view(row)
    commands = plan(params, before)
    if not commands:
        dukovo.finish(False, before, before, commands, service=before)
    if module.check_mode:
        after = predict(params, before)
    else:
        dukovo.apply(commands)
        row = find(dukovo.read(listed, "show_version"), params["name"])
        after = view(row) if row else predict(params, before)
    dukovo.finish(True, before, after, commands, service=after)


if __name__ == "__main__":
    main()
