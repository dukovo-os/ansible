<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# dukovo.system.update

Check for, stage and apply the updates of Dukovo, and set its channel and
holds. The module's own reference is `ansible-doc dukovo.system.update`.

Dukovo runs its system from one of two slots. An update is staged into the
spare slot while the system runs, and starts at the next restart with three
tries to prove itself; one that does not falls back to the version before it
(the Updates page of Dukovo's handbook has the whole story).

## What it runs

It reads `sysupdate status --json`, and `update check --json` for the states
that look at the update server:

| `state` | What it does | Command |
| --- | --- | --- |
| `checked` | reads what the update server offers, and changes nothing | none |
| `staged` | stages the system update the channel offers, or its firmware set when no system update waits, unless one is staged already | `update apply --yes` |
| `applied` | as `staged`, then with `reboot: true` restarts into it | `update apply --yes`, then a restart |
| `channel` | makes the machine follow `channel` (`stable`, `beta` or `nightly`) | `sysupdate channel CHANNEL` |
| `held` | holds `item` (`system` or `firmware`) at the version offered now, or the one it runs | `update hold ITEM` |
| `unheld` | lifts the hold of `item` | `update unhold ITEM` |

Each command runs only when the machine is not as asked, so a second run
reports no change: the same channel, the same hold, an update that is staged
already, or none that waits.

## Applying, with and without a restart

Without `reboot`, `state: applied` is `state: staged`: it stages the update and
`reboot_needed` is true in what it returns, so a later task or a maintenance
window decides when to restart.

With `reboot: true` the module restarts the machine as `ansible.builtin.reboot`
does, and the restart is made by an action plugin of this collection, since a
module cannot wait for the machine it runs on. It:

1. stages the update, if none is staged;
2. runs `reboot` and waits, up to `reboot_timeout` seconds, for the machine to
   answer again, telling a new start from the old by the number of the start,
   which `/system/live/sysupdate/start` holds;
3. runs the module again and checks that `sysupdate status --json` says the
   slot and the version that were staged are the ones that run now.

A machine that came back on the old version, because the update did not prove
itself and the system fell back to it, fails the task, saying which version
runs. A machine that had nothing to update does not restart, and the task
reports no change. In check mode the machine is never restarted.

## Examples

```yaml
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

- name: Hold the system at the version it runs
  become: true
  dukovo.system.update:
    state: held
    item: system
```

## Returns

| Key | Holds |
| --- | --- |
| `status` | `sysupdate status --json` as last read, without its `format` |
| `updates` | `update check --json` without its `format`, for `checked`, `staged` and `applied` |
| `running_version`, `running_slot` | the release that runs, and its slot |
| `staged_version`, `staged_slot` | the update waiting for a restart, or `null` |
| `reboot_needed` | whether an update waits for a restart |
| `rebooted` | true when the machine was restarted into the update and came back running it |
| `commands` | the commands run, or that would run in check mode |

With `--diff`, `before` and `after` are what the module manages: for `staged`
and `applied` the slots and versions above, for `channel` the channel, for
`held` and `unheld` the item and whether it is held.

## Things to know

- Staging needs an administrator, so run the module with `become`.
- An update the server withdrew, or a server that cannot be reached, shows in
  `updates`; when the system or its firmware cannot be checked, `staged` and
  `applied` fail rather than say that nothing waits.
- A machine never goes back to an older version through a channel: it waits
  until the channel passes the version it runs.
- Hold an app with [dukovo.system.bundle](bundle.md), not here.
