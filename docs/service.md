<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# dukovo.system.service

Start, stop and enable the services that Spark, Dukovo's first program,
supervises. The module's own reference is `ansible-doc dukovo.system.service`.

## What it runs

It reads `service list --json`, which is Spark's own document of its services,
finds the service by name, and compares what it is doing and whether it
starts at boot with what was asked:

| Asked | When | Command |
| --- | --- | --- |
| `enabled: true` | not enabled | `service NAME enable` |
| `enabled: false` | enabled | `service NAME disable` |
| `state: started` | not running | `service NAME start` |
| `state: stopped` | running | `service NAME stop` |
| `state: restarted` | always | `service NAME restart` |
| `state: reloaded` | always | `service NAME reload` |

At least one of `state` and `enabled` is needed. With both, `enable` or
`disable` runs first, then the command for `state`.

## Examples

```yaml
- name: The SSH server, now and at each boot
  become: true
  dukovo.system.service:
    name: sshd
    state: started
    enabled: true

- name: Read nginx's settings again after a change
  become: true
  dukovo.system.service:
    name: nginx
    state: reloaded
```

## Returns

`service` holds `name`, its `state` in Spark's words (`running`, `stopped`,
`disabled`, `failed`, `waiting`) and whether it is `enabled`, after the module
ran, or as it would be in check mode. `commands` lists the commands run, or
that would run. With `--diff`, `before` and `after` are that same object.

## Things to know

- A service that starts at its first connection is not running until one
  comes, so `state: started` starts it.
- `restarted` and `reloaded` always change, as they do in Ansible's other
  service modules; use a handler for them.
- A service the machine does not have fails the task, saying that `service
  list` shows which there are.
