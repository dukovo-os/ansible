#!/usr/bin/python
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: feature
short_description: Add and remove the features of a Dukovo machine
version_added: 0.1.0
description:
  - A feature is something the machine does, such as file sharing or a web server. Adding one
    installs its bundles for everyone and turns its services on, now and at each boot; removing
    one turns them off and removes its bundles, except those another added feature needs.
  - The module reads C(feature list --json) and runs C(feature add) or C(feature remove) only
    for the features that are not as asked, so a second run reports no change.
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
      - The IDs of the features, as C(feature list) shows them, such as V(file-sharing).
    type: list
    elements: str
    required: true
    aliases: [id]
  state:
    description:
      - V(present) adds each feature that is not added. A feature that is added in part, with a
        service turned off or a bundle missing, is added again.
      - V(absent) removes each feature that is added or added in part.
    type: str
    choices: [present, absent]
    default: present
  purge:
    description:
      - With O(state=absent), also delete the settings and data of the bundles removed. They are
        otherwise kept for a later add.
    type: bool
    default: false
notes:
  - The module answers yes to what adding a feature asks, as C(feature add --yes) does, since it
    cannot answer a question.
author:
  - The Dukovo contributors (@dukovo-os)
"""

EXAMPLES = r"""
- name: Share files from this machine
  dukovo.system.feature:
    name: file-sharing
    state: present

- name: Take two features away with their data
  dukovo.system.feature:
    name:
      - file-sharing
      - developer-tools
    state: absent
    purge: true
"""

RETURN = r"""
features:
  description: The state of each feature named, as C(feature list) says it, after the module
    ran, or as it would be in check mode.
  returned: always
  type: dict
  sample: {"file-sharing": "added"}
commands:
  description: The commands the module ran, or would run in check mode.
  returned: always
  type: list
  elements: str
  sample: ["feature add --yes file-sharing"]
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.dukovo.system.plugins.module_utils.dukovo import Dukovo

ADDED = "added"
NOT_ADDED = "not added"


def states(document, names):
    """The state of each of names in a feature list, or None for a feature there is not."""
    known = dict((feature["id"], feature["state"]) for feature in document["features"])
    return dict((name, known.get(name)) for name in names), sorted(known)


def plan(params, before):
    """The commands that bring the features of before, by their states, to params."""
    names = [name for name in params["name"] if name in before]
    if params["state"] == "present":
        needed = [name for name in names if before[name] != ADDED]
        return [["feature", "add", "--yes"] + needed] if needed else []
    needed = [name for name in names if before[name] != NOT_ADDED]
    purge = ["--purge"] if params["purge"] else []
    return [["feature", "remove"] + purge + needed] if needed else []


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type="list", elements="str", required=True, aliases=["id"]),
            state=dict(type="str", default="present", choices=["present", "absent"]),
            purge=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )
    dukovo = Dukovo(module)
    params = module.params
    listed = ["feature", "list", "--json"]
    before, known = states(dukovo.read(listed), params["name"])
    unknown = [name for name, state in before.items() if state is None]
    if unknown:
        module.fail_json(
            msg="no such feature: %s; the features are %s" % (", ".join(unknown), ", ".join(known))
        )
    commands = plan(params, before)
    if not commands:
        dukovo.finish(False, before, before, commands, features=before)
    wanted = ADDED if params["state"] == "present" else NOT_ADDED
    if module.check_mode:
        after = dict((name, wanted) for name in before)
    else:
        dukovo.apply(commands)
        after = states(dukovo.read(listed), params["name"])[0]
    dukovo.finish(True, before, after, commands, features=after)


if __name__ == "__main__":
    main()
