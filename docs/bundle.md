<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# dukovo.system.bundle

Install, remove, update and hold back the apps of a Dukovo machine, which are
bundles. The module's own reference is `ansible-doc dukovo.system.bundle`.

## What it runs

It reads `bundle list --json`, finds the bundle by its ID in the place asked,
and runs a command only when the bundle is not as asked:

| `state` | When | Command |
| --- | --- | --- |
| `present` | not installed | `bundle install ID [--from CATALOG] [--for-everyone] --yes` |
| `latest` | installed, a newer version listed, not held | `bundle update ID [--for-everyone] --yes` |
| `absent` | installed | `bundle remove ID [--for-everyone] [--purge]` |
| `held` | not held | `bundle hold ID [--for-everyone]`, after an install if needed |
| `unheld` | held | `bundle unhold ID [--for-everyone]` |

`for_everyone` defaults to true: an administrator's install, which every
account sees, and the one a service needs. Set it to false for the account
the module runs as.

## Examples

```yaml
- name: Python, for Ansible's own modules and for the people
  become: true
  dukovo.system.bundle:
    id: org.python.python
    state: present

- name: A web server, kept up to date
  become: true
  dukovo.system.bundle:
    id: org.nginx.nginx
    catalog: dukovo
    state: latest

- name: Keep it at this version
  become: true
  dukovo.system.bundle:
    id: org.nginx.nginx
    state: held
```

## Returns

`bundle` holds the bundle as it is after the module ran, or as it would be in
check mode: `id`, `for_everyone`, `installed`, `version`, `catalog`, `held` and
`newer`, the newer version its catalog lists, or `null`. `commands` lists the commands run, or that would run. With `--diff`,
`before` and `after` are that same object.

## Things to know

- The module answers yes to the install sheet, as `--yes` does, since nothing
  can answer a question. Read what a bundle asks for before listing it.
- `state: latest` leaves a held bundle as it is and warns that its update
  waits; `state: unheld` lets it go.
- An `unheld` bundle that is not installed is not held, so nothing changes.
- A failed command fails the task with its error ID in `error_id`.
