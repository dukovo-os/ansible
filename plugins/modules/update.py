#!/usr/bin/python
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: update
short_description: Check for, stage and apply updates of Dukovo, and set its channel and holds
version_added: 0.1.0
description:
  - Dukovo runs its system from one of two slots. An update is staged into the spare slot while the
    system runs, and starts at the next restart, with three tries to prove itself; one that does not
    falls back to the version before it.
  - The module reads C(sysupdate status --json) and C(update check --json), and runs
    C(update apply --yes), C(sysupdate channel), C(update hold) or C(update unhold) only when the
    machine is not as asked, so a second run reports no change.
  - With O(state=applied) and O(reboot=true) the module restarts the machine as the
    M(ansible.builtin.reboot) module does, waits for it to come back, and checks that
    C(sysupdate status --json) says that the new version runs. Without O(reboot) the update is
    staged and RV(reboot_needed) says that a restart is needed.
extends_documentation_fragment:
  - ansible.builtin.action_common_attributes
attributes:
  check_mode:
    support: full
  diff_mode:
    support: full
  action:
    support: full
    description: Indicates this has a corresponding action plugin so some parts of the options can be executed on the controller.
    details: The restart is made by an action plugin of this collection, since a module cannot wait for the machine it runs on.
  platform:
    platforms: posix
options:
  state:
    description:
      - V(checked) reads what the update server offers and changes nothing.
      - V(staged) stages the system update the channel offers, or its firmware set when no system
        update waits, so that it starts at the next restart. An update that is staged already, or
        none that waits, is no change. C(update apply) also updates the apps installed for everyone.
      - V(applied) stages the update as V(staged) does, and with O(reboot=true) restarts into it.
        An update that was staged before is restarted into, and a machine that has nothing to
        update is no change.
      - V(channel) makes the machine follow the channel O(channel) names.
      - V(held) holds the release or firmware set O(item) at the version offered now, or the one it
        runs, so that no update takes it until a newer version comes or the hold is lifted.
      - V(unheld) lifts the hold of O(item).
    type: str
    choices: [checked, staged, applied, channel, held, unheld]
    default: checked
  channel:
    description:
      - The channel to follow, needed for O(state=channel). A machine never goes back to an older
        version through a channel, and waits until the channel passes the version it runs.
    type: str
    choices: [stable, beta, nightly]
  item:
    description:
      - What to hold or let go, needed for O(state=held) and O(state=unheld). Hold an app with
        M(dukovo.system.bundle).
    type: str
    choices: [system, firmware]
  reboot:
    description:
      - With O(state=applied), restart the machine into the staged update, wait for it, and check
        that the new version runs.
    type: bool
    default: false
  reboot_timeout:
    description:
      - With O(reboot=true), the seconds to wait for the machine to come back.
    type: int
    default: 600
notes:
  - Staging needs an administrator, so run the module with C(become).
  - The restart waits for the machine to answer again, and finds it has restarted by the number of
    its start, which C(/system/live/sysupdate/start) holds.
author:
  - The Dukovo contributors (@dukovo-os)
"""

EXAMPLES = r"""
- name: Follow the beta channel
  become: true
  dukovo.system.update:
    state: channel
    channel: beta

- name: See what the update server offers
  dukovo.system.update:
    state: checked
  register: offered

- name: Stage the update and start the machine on it
  become: true
  dukovo.system.update:
    state: applied
    reboot: true
    reboot_timeout: 900

- name: Stage it and restart at a time that suits
  become: true
  dukovo.system.update:
    state: staged
  register: staged

- name: Hold the system at the version it runs
  become: true
  dukovo.system.update:
    state: held
    item: system
"""

RETURN = r"""
status:
  description: C(sysupdate status --json) as the module read it last, which is after its commands
    ran, without its C(format). In check mode it is as it is now.
  returned: always
  type: dict
  contains:
    running:
      description: The slot that runs, V(a) or V(b).
      type: str
    default:
      description: The slot that starts unless an update is being tried.
      type: str
    staged:
      description: An update that has not proved itself, with its V(slot) and the V(tries_left),
        or V(null).
      type: dict
    channel:
      description: The channel the machine follows.
      type: str
    wave:
      description: The machine's number from 0 to 999 that places it in a wave, or V(null).
      type: int
    canary:
      description: Whether the machine takes each release on its first day.
      type: bool
    held:
      description: The versions held back, V(system) and V(firmware), each a version or V(null).
      type: dict
    slots:
      description: What each slot holds, with its V(version) and V(firmware).
      type: list
      elements: dict
    rescue:
      description: The release that Rescue holds, or V(null).
      type: str
updates:
  description: C(update check --json) without its C(format), which says what each part offers, as V(offers),
    and V(unchecked), V(running_withdrawn) and V(notes). Not returned for V(channel), V(held) and
    V(unheld).
  returned: when state is checked, staged or applied
  type: dict
running_version:
  description: The version of the release that runs.
  returned: always
  type: str
  sample: 0.15.0
running_slot:
  description: The slot that runs, V(a) or V(b).
  returned: always
  type: str
  sample: a
staged_version:
  description: The version of the update staged and waiting for a restart, or V(null).
  returned: always
  type: str
  sample: 0.16.0
staged_slot:
  description: The slot of the update staged and waiting for a restart, or V(null).
  returned: always
  type: str
  sample: b
reboot_needed:
  description: Whether an update is staged that starts at the next restart.
  returned: always
  type: bool
rebooted:
  description: Whether the machine was restarted into the update and came back running it.
  returned: when O(state=applied) and O(reboot=true) and the machine was restarted
  type: bool
commands:
  description: The commands the module ran, or would run in check mode.
  returned: always
  type: list
  elements: str
  sample: ["update apply --yes"]
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.dukovo.system.plugins.module_utils.dukovo import Dukovo

STATUS = ["sysupdate", "status", "--json"]
CHECK = ["update", "check", "--json"]


def slot_of(status, letter):
    """What the slot named letter holds, in sysupdate status's document."""
    for each in status["slots"]:
        if each["slot"] == letter:
            return each
    return {"slot": letter, "version": None, "firmware": None}


def where(status):
    """The running version, and the update staged and waiting for a restart: which slot and version."""
    staged = status["staged"]
    waiting = staged is not None and staged["slot"] != status["running"] and staged["tries_left"] > 0
    return {
        "running_slot": status["running"],
        "running_version": slot_of(status, status["running"])["version"],
        "staged_slot": staged["slot"] if waiting else None,
        "staged_version": slot_of(status, staged["slot"])["version"] if waiting else None,
        "reboot_needed": waiting,
    }


def without_format(document):
    """A command's document without its format member."""
    return dict((key, value) for key, value in document.items() if key != "format")


def to_stage(updates):
    """The offers that update apply stages: the system's, or else the firmware set's."""
    offers = [each for each in updates["offers"] if each["state"] == "update"]
    system = [each for each in offers if each["item"] == "system"]
    return system or [each for each in offers if each["item"] == "firmware"]


def stageable(module, updates):
    """Fails the module when the system or its firmware could not be checked."""
    for each in updates["unchecked"]:
        if each["item"] in ("system", "firmware"):
            module.fail_json(msg="the %s cannot be checked: %s" % (each["item"], each["why"]))


def staging(module, dukovo, params):
    """The states staged and applied: stage the update that waits, when none is staged yet."""
    status = dukovo.read(STATUS)
    updates = dukovo.read(CHECK)
    before = where(status)
    commands = []
    offer = []
    if not before["reboot_needed"]:
        stageable(module, updates)
        offer = to_stage(updates)
        if offer:
            commands.append(["update", "apply", "--yes"])
    restart = params["state"] == "applied" and params["reboot"]
    if module.check_mode:
        after = dict(before)
        if commands:
            after.update(
                reboot_needed=True,
                staged_version=offer[0]["to"] if offer[0]["item"] == "system" else before["running_version"],
            )
        changed = bool(commands) or (restart and after["reboot_needed"])
    else:
        dukovo.apply(commands)
        if commands:
            status = dukovo.read(STATUS)
        after = where(status)
        changed = bool(commands)
    result = dict(after, status=without_format(status), updates=without_format(updates))
    dukovo.finish(changed, before, after, commands, **result)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            state=dict(
                type="str",
                default="checked",
                choices=["checked", "staged", "applied", "channel", "held", "unheld"],
            ),
            channel=dict(type="str", choices=["stable", "beta", "nightly"]),
            item=dict(type="str", choices=["system", "firmware"]),
            reboot=dict(type="bool", default=False),
            reboot_timeout=dict(type="int", default=600),
        ),
        required_if=[
            ("state", "channel", ["channel"]),
            ("state", "held", ["item"]),
            ("state", "unheld", ["item"]),
        ],
        supports_check_mode=True,
    )
    dukovo = Dukovo(module)
    params = module.params
    state = params["state"]
    if state in ("staged", "applied"):
        return staging(module, dukovo, params)
    status = dukovo.read(STATUS)
    if state == "checked":
        updates = dukovo.read(CHECK)
        result = dict(where(status), status=without_format(status), updates=without_format(updates))
        return dukovo.finish(False, None, None, [], **result)
    commands = []
    if state == "channel":
        before = {"channel": status["channel"]}
        wanted = {"channel": params["channel"]}
        if status["channel"] != params["channel"]:
            commands.append(["sysupdate", "channel", params["channel"]])
    else:
        held = state == "held"
        before = {"item": params["item"], "held": status["held"][params["item"]] is not None}
        wanted = {"item": params["item"], "held": held}
        if before["held"] != held:
            commands.append(["update", "hold" if held else "unhold", params["item"]])
    if commands and not module.check_mode:
        dukovo.apply(commands)
        status = dukovo.read(STATUS)
    result = dict(where(status), status=without_format(status))
    dukovo.finish(bool(commands), before, wanted if commands else before, commands, **result)


if __name__ == "__main__":
    main()
