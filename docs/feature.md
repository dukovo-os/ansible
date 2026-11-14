<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# dukovo.system.feature

Add and remove the features of a Dukovo machine. A feature is something the
machine does, such as file sharing or a web server: adding one installs its
bundles for everyone and turns its services on, now and at each boot. The
module's own reference is `ansible-doc dukovo.system.feature`.

## What it runs

It reads `feature list --json`, which says each feature is `added`, `partly`
added or `not added`, and runs a command for the features that are not as
asked:

| `state` | Features it acts on | Command |
| --- | --- | --- |
| `present` | `partly` and `not added` | `feature add --yes IDS...` |
| `absent` | `added` and `partly` | `feature remove [--purge] IDS...` |

One command takes all the features of a task that need it, in the order
given. A name that `feature list` does not know fails the task before
anything changes.

## Examples

```yaml
- name: Share files from this machine
  become: true
  dukovo.system.feature:
    name: file-sharing

- name: Take two features away, with the data of their bundles
  become: true
  dukovo.system.feature:
    name:
      - file-sharing
      - developer-tools
    state: absent
    purge: true
```

## Returns

`features` maps each feature named to its state after the module ran, or as it
would be in check mode. `commands` lists the commands run, or that would run.
With `--diff`, `before` and `after` are the states of the features named.

## Things to know

- A feature added in part, with a service off or a bundle missing, is added
  again by `state: present`, which is how a drifted machine is put right.
- Removing a feature keeps the bundles that another added feature needs.
- The module answers yes to what adding asks, as `--yes` does.
