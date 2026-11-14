<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# dukovo.system.facts

Gather what Dukovo says of itself. The module's own reference is
`ansible-doc dukovo.system.facts`.

`ansible.builtin.setup` already names the system from `/etc/os-release`, so
`ansible_facts.distribution` is `Dukovo` and `ansible_facts.distribution_version`
is the release. This module adds what only Dukovo knows, under
`ansible_facts.dukovo`. It changes nothing, and runs in check mode.

## What it reads

`sysupdate status --json`, `feature list --json`, `service list --json`,
`bundle list --json` and `dukovo-check --last --json`. The first four are in
every release that prints JSON, and a failure of one fails the task.
`dukovo-check` is read when it is there and the account may read its file;
`check` is `null` otherwise, and when no check has run.

## The facts

| Fact | Holds |
| --- | --- |
| `version` | the release that runs, such as `0.15.0` |
| `slot` | the slot that runs, `a` or `b` |
| `firmware` | the firmware set the running slot names, or `null` |
| `channel` | `stable`, `beta` or `nightly` |
| `wave` | the machine's number from 0 to 999, which places it in a wave of each release, or `null` before it has drawn one |
| `canary` | whether the machine takes each release on its first day |
| `rescue` | the release that Rescue holds, or `null` when the install wrote none |
| `staged` | an update waiting for the next restart, with its `slot`, `version` and `tries_left`, or `null` |
| `held` | the versions held back, `system` and `firmware` |
| `features` | each feature by its ID: `added`, `partly` or `not added` |
| `services` | each service by its name, with its state in Spark's words |
| `bundles` | each installed bundle: `id`, `version`, `for_everyone`, `held` and `update` |
| `check` | the last `dukovo-check`: `checked`, `release` and `counts` of `passed`, `warning`, `failed` and `skipped`, or `null` |

## Examples

```yaml
- name: Gather the facts of Dukovo
  dukovo.system.facts:

- name: Say which release runs and whether the machine is a canary
  ansible.builtin.debug:
    msg: "Dukovo {{ ansible_facts.dukovo.version }} in slot {{ ansible_facts.dukovo.slot }}"
  when: ansible_facts.dukovo.canary

- name: List the bundles that have a newer version
  ansible.builtin.debug:
    msg: "{{ ansible_facts.dukovo.bundles | selectattr('update') | map(attribute='id') | list }}"
```

## Things to know

- `bundles` lists those the account can run, its own and everyone's, so a
  bundle installed for one other account does not show.
- `dukovo-check` keeps its last result in a file that root and the `admins`
  group may read, so without `become` an account that is not an administrator
  sees `check` as `null`.
