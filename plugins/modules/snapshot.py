#!/usr/bin/python
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: snapshot
short_description: Make, remove and prune the snapshots of Dukovo's Btrfs subvolumes
version_added: 0.1.0
description:
  - A snapshot is a read-only copy of a subvolume, which a place such as C(/users) names. The
    module manages them with C(snap).
  - It reads C(snap list PLACE --json) and runs C(snap create), C(snap delete) or C(snap prune)
    only when the snapshots are not as asked, so a second run reports no change.
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
  place:
    description:
      - The top folder of the subvolume, such as V(/users), V(/shared) or V(/system/settings), or a
        subvolume of another Btrfs disk in C(/volumes).
    type: str
    required: true
  name:
    description:
      - The snapshot's name, a file name that does not start with a dot and is not a time. A snapshot
        made by name is never removed by a prune.
      - Needed for O(state=present) and O(state=absent).
    type: str
  state:
    description:
      - V(present) makes the snapshot named O(name) when the place has none by that name. A
        snapshot is a copy of the place as it is when it is made, so one that exists is never made
        again.
      - V(absent) removes the snapshot named O(name).
      - V(pruned) removes the snapshots that the retention of C(snap.toml) does not keep, the
        place's O(name) ones excepted.
    type: str
    choices: [present, absent, pruned]
    default: present
notes:
  - Making and removing a snapshot needs an administrator, so run the module with C(become).
author:
  - The Dukovo contributors (@dukovo-os)
"""

EXAMPLES = r"""
- name: Keep the users' files as they are before an upgrade
  become: true
  dukovo.system.snapshot:
    place: /users
    name: before-the-upgrade
    state: present

- name: Drop it afterwards
  become: true
  dukovo.system.snapshot:
    place: /users
    name: before-the-upgrade
    state: absent

- name: Remove the snapshots retention no longer keeps
  become: true
  dukovo.system.snapshot:
    place: /users
    state: pruned
"""

RETURN = r"""
snapshots:
  description: The names of the place's snapshots after the module ran, oldest first, or as they
    would be in check mode.
  returned: always
  type: list
  elements: str
  sample: ["2026-11-13-0300", "before-the-upgrade"]
commands:
  description: The commands the module ran, or would run in check mode.
  returned: always
  type: list
  elements: str
  sample: ["snap create --name before-the-upgrade /users"]
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.dukovo.system.plugins.module_utils.dukovo import Dukovo


def view(place, document):
    """The place's snapshots as the module reports them, from its snap list document."""
    return {"place": place, "snapshots": [each["name"] for each in document["snapshots"]]}


def plan(params, document):
    """The commands that bring the place's snapshots, as its snap list document says, to params."""
    place, name, state = params["place"], params["name"], params["state"]
    names = [each["name"] for each in document["snapshots"]]
    if state == "present":
        return [] if name in names else [["snap", "create", "--name", name, place]]
    if state == "absent":
        return [["snap", "delete", place, name]] if name in names else []
    return [["snap", "prune", place]] if any(each["prunable"] for each in document["snapshots"]) else []


def predict(params, document):
    """The place's snapshots after plan's commands, for check mode."""
    place, name, state = params["place"], params["name"], params["state"]
    names = [each["name"] for each in document["snapshots"]]
    if state == "present" and name not in names:
        names.append(name)
    elif state == "absent":
        names = [each for each in names if each != name]
    elif state == "pruned":
        names = [each["name"] for each in document["snapshots"] if not each["prunable"]]
    return {"place": place, "snapshots": names}


def main():
    module = AnsibleModule(
        argument_spec=dict(
            place=dict(type="str", required=True),
            name=dict(type="str"),
            state=dict(type="str", default="present", choices=["present", "absent", "pruned"]),
        ),
        required_if=[("state", "present", ["name"]), ("state", "absent", ["name"])],
        supports_check_mode=True,
    )
    dukovo = Dukovo(module)
    params = module.params
    listed = ["snap", "list", params["place"], "--json"]
    document = dukovo.read(listed)
    before = view(params["place"], document)
    commands = plan(params, document)
    if not commands:
        dukovo.finish(False, before, before, commands, snapshots=before["snapshots"])
    if module.check_mode:
        after = predict(params, document)
    else:
        dukovo.apply(commands)
        after = view(params["place"], dukovo.read(listed))
    dukovo.finish(True, before, after, commands, snapshots=after["snapshots"])


if __name__ == "__main__":
    main()
