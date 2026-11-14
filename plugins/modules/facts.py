#!/usr/bin/python
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: facts
short_description: Gather facts about a Dukovo machine
version_added: 0.1.0
description:
  - Gathers what Dukovo says of itself, from the C(--json) of C(sysupdate status), C(feature list),
    C(service list), C(bundle list) and C(dukovo-check --last), into RV(ansible_facts.dukovo).
  - M(ansible.builtin.setup) names the system from the kernel's C(uname), which says Dukovo, so
    C(ansible_facts.distribution) is V(Dukovo) without this module. This one adds what only Dukovo
    knows, the release that runs among it.
extends_documentation_fragment:
  - ansible.builtin.action_common_attributes
  - ansible.builtin.action_common_attributes.facts
attributes:
  check_mode:
    support: full
  diff_mode:
    support: none
  facts:
    support: full
  platform:
    platforms: posix
notes:
  - C(dukovo-check --last) is read when the account may; the machine's last check is V(null)
    otherwise, or when no check has run.
author:
  - The Dukovo contributors (@dukovo-os)
"""

EXAMPLES = r"""
- name: Gather the facts of Dukovo
  dukovo.system.facts:

- name: Say which release runs and whether the machine is a canary
  ansible.builtin.debug:
    msg: "Dukovo {{ ansible_facts.dukovo.version }} in slot {{ ansible_facts.dukovo.slot }}"
  when: ansible_facts.dukovo.canary
"""

RETURN = r"""
ansible_facts:
  description: The facts, under V(dukovo).
  returned: always
  type: dict
  contains:
    dukovo:
      description: What Dukovo says of itself.
      type: dict
      contains:
        version:
          description: The release that runs.
          type: str
          sample: 0.15.0
        slot:
          description: The slot that runs, V(a) or V(b).
          type: str
          sample: a
        firmware:
          description: The firmware set the running slot names, or V(null).
          type: str
        channel:
          description: The update channel the machine follows.
          type: str
          sample: stable
        wave:
          description: The machine's number from 0 to 999, which places it in a wave of each release,
            or V(null) before it has drawn one.
          type: int
          sample: 412
        canary:
          description: Whether the machine takes each release on its first day.
          type: bool
        rescue:
          description: The release that Rescue holds, or V(null).
          type: str
        staged:
          description: An update waiting for the next restart, with its V(slot), V(version) and the
            V(tries_left), or V(null).
          type: dict
        held:
          description: The versions held back, V(system) and V(firmware).
          type: dict
        features:
          description: Each feature by its ID, with V(added), V(partly) or V(not added).
          type: dict
          sample: {"file-sharing": "added"}
        services:
          description: Each service by its name, with its state in Spark's words.
          type: dict
          sample: {"sshd": "running"}
        bundles:
          description: The installed bundles, each with its V(id), V(version), V(for_everyone), V(held)
            and V(update), the newer version its catalog lists.
          type: list
          elements: dict
        check:
          description: The result of the last C(dukovo-check), with when it was V(checked), the V(release)
            that ran it and its V(counts) of V(passed), V(warning), V(failed) and V(skipped); V(null)
            when none is kept or the account may not read it.
          type: dict
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.dukovo.system.plugins.module_utils.dukovo import Dukovo


def staged_update(status):
    """The update waiting for a restart in sysupdate status's document, or None."""
    staged = status["staged"]
    if staged is None or staged["slot"] == status["running"] or staged["tries_left"] < 1:
        return None
    slot = [each for each in status["slots"] if each["slot"] == staged["slot"]][0]
    return {"slot": staged["slot"], "version": slot["version"], "tries_left": staged["tries_left"]}


def last_check(document):
    """What the facts say of dukovo-check's saved result, or None."""
    if document is None:
        return None
    return {
        "checked": document.get("checked"),
        "release": document.get("release"),
        "counts": document.get("counts"),
    }


def gather(dukovo):
    """The facts, read from the commands."""
    status = dukovo.read(["sysupdate", "status", "--json"])
    running = [each for each in status["slots"] if each["slot"] == status["running"]][0]
    return {
        "version": running["version"],
        "slot": status["running"],
        "firmware": running["firmware"],
        "channel": status["channel"],
        "wave": status["wave"],
        "canary": status["canary"],
        "rescue": status.get("rescue"),
        "staged": staged_update(status),
        "held": status["held"],
        "features": dict(
            (each["id"], each["state"])
            for each in dukovo.read(["feature", "list", "--json"])["features"]
        ),
        "services": dict(
            (each["name"], each["state"])
            for each in dukovo.read(["service", "list", "--json"], "show_version")["services"]
        ),
        "bundles": [
            {
                "id": each["id"],
                "version": each["version"],
                "for_everyone": each["for_everyone"],
                "held": each["held"],
                "update": each["update"],
            }
            for each in dukovo.read(["bundle", "list", "--json"])["bundles"]
        ],
        "check": last_check(dukovo.read_optional(["dukovo-check", "--last", "--json"], "version")),
    }


def main():
    module = AnsibleModule(argument_spec=dict(), supports_check_mode=True)
    module.exit_json(changed=False, ansible_facts={"dukovo": gather(Dukovo(module))})


if __name__ == "__main__":
    main()
