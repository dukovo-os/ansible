<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Ansible collection dukovo.system

Modules that manage [Dukovo](https://dukovo.org/), the operating system with
its own kernel, Radix, from Ansible: its apps, features, services, snapshots
and updates, and what it says of itself.

The modules run Dukovo's own commands on the machine and read what they print
with `--json`, so a module knows the state before it changes anything. Each
changes the machine only when it is not as asked, so a second run reports
`changed=0`; `--check` says what would change without changing it, and `--diff`
shows the state before and after.

## Modules

| Module | What it does |
| --- | --- |
| `dukovo.system.bundle` | install, remove, update and hold back apps |
| `dukovo.system.feature` | add and remove what the machine does |
| `dukovo.system.service` | start, stop and enable services |
| `dukovo.system.snapshot` | make, remove and prune snapshots of Btrfs subvolumes |
| `dukovo.system.update` | check, stage and apply updates, restart into them, set the channel and holds |
| `dukovo.system.facts` | the release, slot, channel, features, services and bundles of the machine |

## Requirements

- ansible-core 2.22 or newer on the control machine, and Python 3.13 or newer
  there: Dukovo's Python is 3.15, and 2.22 is the first release of
  ansible-core whose modules run under it.
- A Dukovo machine with its SSH server turned on, and Python on it: Python is
  the `org.python.python` bundle, which a first playbook installs with
  `ansible.builtin.raw`.
- An administrator's account for anything that changes the system. Dukovo's
  `sudo` is `elevate`, and Ansible's `become` works through it.

[docs/getting-started.md](docs/getting-started.md) takes it from there:
the inventory, Python, and `become`.

## Install

From the tarball of a [release](https://github.com/dukovo-os/ansible/releases):

```
$ ansible-galaxy collection install https://github.com/dukovo-os/ansible/releases/download/v0.1.0/dukovo-system-0.1.0.tar.gz
```

The collection is not on Ansible Galaxy yet.

## Example

```yaml
- hosts: dukovo
  become: true
  tasks:
    - name: Learn what the machine is
      dukovo.system.facts:

    - name: Share files from this machine
      dukovo.system.feature:
        name: file-sharing

    - name: Start the web server now and at each boot
      dukovo.system.service:
        name: nginx
        state: started
        enabled: true

    - name: Update, and restart into the update
      dukovo.system.update:
        state: applied
        reboot: true
```

## Documentation

- [Getting started](docs/getting-started.md)
- [bundle](docs/bundle.md), [feature](docs/feature.md),
  [service](docs/service.md), [snapshot](docs/snapshot.md),
  [update](docs/update.md) and [facts](docs/facts.md)
- Each module's own reference: `ansible-doc dukovo.system.bundle`, and so on.

## Tests

```
$ ansible-test sanity --python 3.13
$ ansible-test units --python 3.13
```

from `ansible_collections/dukovo/system` in a checkout laid out that way.
`tests/integration/targets/dukovo/` runs the modules against a Dukovo machine
that is given as the inventory. Dukovo's own boot test and lab test run a
playbook of the same modules against a machine in QEMU and an installed one.

## Releases

The Release workflow makes release `vVERSION`, where VERSION is the version
in `galaxy.yml`: run it from the Actions tab on main, which makes the tag, or
push the tag. It builds the tarball with `ansible-galaxy collection build`
and attaches it, with its SHA-256, to the GitHub release, and refuses a
version that is released already. Dukovo's tests pin a release by its URL
and that hash, in `tools/xtask/src/test/ansible.lock` of the Dukovo tree.

## License

GPL-3.0-or-later, as Ansible's modules are. The text is in `LICENSE`; every
file carries its SPDX header, which `reuse lint` checks.
