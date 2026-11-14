<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# dukovo.system.snapshot

Make, remove and prune the snapshots of Dukovo's Btrfs subvolumes. A snapshot
is a read-only copy of a subvolume, which a place such as `/users` names. The
module's own reference is `ansible-doc dukovo.system.snapshot`.

## What it runs

It reads `snap list PLACE --json` and runs a command only when the snapshots
are not as asked:

| `state` | When | Command |
| --- | --- | --- |
| `present` | the place has no snapshot by that `name` | `snap create --name NAME PLACE` |
| `absent` | the place has one by that `name` | `snap delete PLACE NAME` |
| `pruned` | `snap list` marks a snapshot as prunable | `snap prune PLACE` |

## Examples

```yaml
- name: Keep the users' files as they are before an upgrade
  become: true
  dukovo.system.snapshot:
    place: /users
    name: before-the-upgrade

- name: Drop it afterwards
  become: true
  dukovo.system.snapshot:
    place: /users
    name: before-the-upgrade
    state: absent

- name: Remove what retention no longer keeps
  become: true
  dukovo.system.snapshot:
    place: /users
    state: pruned
```

## Returns

`snapshots` lists the names of the place's snapshots after the module ran,
oldest first, or as they would be in check mode. `commands` lists the commands
run, or that would run. With `--diff`, `before` and `after` are the `place` and
its `snapshots`.

## Things to know

- A snapshot is the place as it is when it is made, so one that exists by that
  name is never made again; make a snapshot under a new name for a new copy.
- A snapshot made by name is never removed by a prune. Names that are times
  are the ones `snap` makes by itself, and the ones retention prunes.
- Making and removing needs an administrator, so run the module with `become`.
- A snapshot that cannot be made, or removed, fails the task with what `snap`
  printed and its error ID.
