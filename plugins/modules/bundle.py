#!/usr/bin/python
# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
module: bundle
short_description: Install, remove, update and hold back bundles on Dukovo
version_added: 0.1.0
description:
  - Manages the apps of a Dukovo machine, which are bundles, with C(bundle).
  - It reads C(bundle list --json) and runs C(bundle install), C(bundle remove),
    C(bundle update), C(bundle hold) and C(bundle unhold) only when the bundle is not as asked,
    so a second run reports no change.
  - C(bundle) acts for the account that runs it. Run through C(become) as an administrator, it
    manages the bundles installed for everyone, which is what O(for_everyone) says.
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
  id:
    description:
      - The bundle's ID, such as V(org.nginx.nginx).
    type: str
    required: true
    aliases: [name]
  state:
    description:
      - V(present) installs the bundle when it is not installed, and leaves an installed one at its
        version.
      - V(latest) also updates it when its catalog lists a newer version, which bundled last read
        from the catalog. A held bundle is left as it is, and the module warns.
      - V(absent) removes it.
      - V(held) holds it at its version so that no update takes it, installing it first when it is
        not installed.
      - V(unheld) lifts the hold. A bundle that is not installed is not held.
    type: str
    choices: [present, absent, latest, held, unheld]
    default: present
  catalog:
    description:
      - The catalog to install the bundle from, as C(bundle catalog) lists them. Without it, the
        first catalog that lists the bundle.
    type: str
  for_everyone:
    description:
      - Whether the bundle is installed for everyone, which an administrator does, or for the
        account the module runs as.
    type: bool
    default: true
  purge:
    description:
      - With O(state=absent), also delete the bundle's settings and data, which are otherwise
        kept for a later install.
    type: bool
    default: false
notes:
  - The module answers yes to the install sheet, as C(--yes) does, since it cannot answer a
    question. Review what a bundle asks for before listing it in a playbook.
  - Bundles that bring a service install only for everyone.
author:
  - The Dukovo contributors (@dukovo-os)
"""

EXAMPLES = r"""
- name: Install nginx for everyone from Dukovo's catalog
  dukovo.system.bundle:
    id: org.nginx.nginx
    catalog: dukovo
    state: present

- name: Keep it up to date
  dukovo.system.bundle:
    id: org.nginx.nginx
    state: latest

- name: Hold it at the version it has, until it is let go
  dukovo.system.bundle:
    id: org.nginx.nginx
    state: held

- name: Remove it and its data
  dukovo.system.bundle:
    id: org.nginx.nginx
    state: absent
    purge: true
"""

RETURN = r"""
bundle:
  description: The bundle as it is after the module ran, or as it would be in check mode.
  returned: always
  type: dict
  contains:
    id:
      description: The bundle's ID.
      type: str
      sample: org.nginx.nginx
    for_everyone:
      description: Whether this is the copy installed for everyone.
      type: bool
    installed:
      description: Whether the bundle is installed.
      type: bool
    version:
      description: The installed version, or V(null) when it is not installed, or in check mode
        before an install.
      type: str
      sample: 1.2.0
    catalog:
      description: The catalog it updates from, or V(null) for its own feed or none.
      type: str
    held:
      description: Whether it is held at its version.
      type: bool
    update:
      description: The newest version the catalog lists when it is newer than the installed one.
      type: str
commands:
  description: The commands the module ran, or would run in check mode.
  returned: always
  type: list
  elements: str
  sample: ["bundle install org.nginx.nginx --from dukovo --for-everyone --yes"]
"""

from ansible.module_utils.basic import AnsibleModule

from ansible_collections.dukovo.system.plugins.module_utils.dukovo import Dukovo


def view(bundle_id, for_everyone, row):
    """The bundle as the module reports it, from its row of bundle list, if it has one."""
    row = row or {}
    return {
        "id": bundle_id,
        "for_everyone": for_everyone,
        "installed": bool(row),
        "version": row.get("version"),
        "catalog": row.get("catalog"),
        "held": bool(row.get("held")),
        "update": row.get("update"),
    }


def find(document, bundle_id, for_everyone):
    """The row of bundle list for the bundle in the place asked, or None."""
    for row in document["bundles"]:
        if row["id"] == bundle_id and row["for_everyone"] == for_everyone:
            return row
    return None


def plan(params, before):
    """The commands that bring the bundle to params from before, which view says."""
    bundle_id, state = params["id"], params["state"]
    scope = ["--for-everyone"] if params["for_everyone"] else []
    if state == "absent":
        if not before["installed"]:
            return []
        return [["bundle", "remove", bundle_id] + scope + (["--purge"] if params["purge"] else [])]
    if state == "unheld":
        return [["bundle", "unhold", bundle_id] + scope] if before["held"] else []
    commands = []
    if not before["installed"]:
        install = ["bundle", "install", bundle_id]
        if params["catalog"]:
            install += ["--from", params["catalog"]]
        commands.append(install + scope + ["--yes"])
    elif state == "latest" and before["update"] and not before["held"]:
        commands.append(["bundle", "update", bundle_id] + scope + ["--yes"])
    if state == "held" and not before["held"]:
        commands.append(["bundle", "hold", bundle_id] + scope)
    return commands


def predict(params, before):
    """What the bundle comes to after plan's commands, for check mode."""
    after = dict(before)
    state = params["state"]
    if state == "absent":
        return view(params["id"], params["for_everyone"], None)
    if state == "unheld":
        after["held"] = False
        return after
    if not before["installed"]:
        after.update(installed=True, catalog=params["catalog"])
    elif state == "latest" and before["update"] and not before["held"]:
        after.update(version=before["update"], update=None)
    if state == "held":
        after["held"] = True
    return after


def main():
    module = AnsibleModule(
        argument_spec=dict(
            id=dict(type="str", required=True, aliases=["name"]),
            state=dict(
                type="str",
                default="present",
                choices=["present", "absent", "latest", "held", "unheld"],
            ),
            catalog=dict(type="str"),
            for_everyone=dict(type="bool", default=True),
            purge=dict(type="bool", default=False),
        ),
        supports_check_mode=True,
    )
    dukovo = Dukovo(module)
    params = module.params
    listed = ["bundle", "list", "--json"]
    before = view(
        params["id"],
        params["for_everyone"],
        find(dukovo.read(listed), params["id"], params["for_everyone"]),
    )
    if params["state"] == "latest" and before["held"] and before["update"]:
        module.warn(
            "%s is held at %s, so %s waits; state=unheld lets it update"
            % (params["id"], before["version"], before["update"])
        )
    commands = plan(params, before)
    if not commands:
        dukovo.finish(False, before, before, commands, bundle=before)
    if module.check_mode:
        after = predict(params, before)
    else:
        dukovo.apply(commands)
        after = view(
            params["id"],
            params["for_everyone"],
            find(dukovo.read(listed), params["id"], params["for_everyone"]),
        )
    dukovo.finish(True, before, after, commands, bundle=after)


if __name__ == "__main__":
    main()
