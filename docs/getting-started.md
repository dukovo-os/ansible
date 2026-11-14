<!--
SPDX-FileCopyrightText: 2026 The Dukovo contributors
SPDX-License-Identifier: GPL-3.0-or-later
-->

# Getting started

This page takes a control machine, anything that runs ansible-core 2.22 or
newer, to a playbook that manages a Dukovo machine: how it reaches the
machine, where Python comes from, and how a task becomes an administrator.

## Install the collection

From the tarball of a [release](https://github.com/dukovo-os/ansible/releases),
whose page gives the tarball's SHA-256:

```
$ ansible-galaxy collection install https://github.com/dukovo-os/ansible/releases/download/v0.1.0/dukovo-system-0.1.0.tar.gz
```

Or from a checkout: `ansible-galaxy collection build` makes the tarball, and
`ansible-galaxy collection install dukovo-system-0.1.0.tar.gz` installs it.
The collection is not on Ansible Galaxy yet.

The modules run Dukovo's own commands (`bundle`, `feature`, `service`,
`snap`, `sysupdate`, `update`) and read what they print with `--json`, so a
module needs a release whose commands print it, which the manual pages of
`bundle(1)`, `feature(8)`, `service(8)`, `snap(1)`, `sysupdate(8)` and
`update(8)` show with a section named JSON. A command that prints a `format`
this collection does not know fails the module, saying so, rather than
guessing.

## Turn on SSH

Dukovo's SSH server is off until an administrator turns it on, at the
machine:

```
$ elevate service sshd enable
```

Ansible signs in with a key. Dukovo takes keys of the kinds `ssh-ed25519`,
`ecdsa-sha2-nistp256` and `ecdsa-sha2-nistp384`, and not RSA keys, so make
one of those and put its public half in the `~/.ssh/authorized_keys` of the
account Ansible signs in as:

```
$ ssh-keygen -t ed25519 -f ~/.ssh/dukovo
$ ssh-copy-id -i ~/.ssh/dukovo.pub alice@dukovo
```

The account must be an administrator, a member of the `admins` group, for
anything that changes the system.

## Inventory

```ini
[dukovo]
shop ansible_host=192.168.1.40

[dukovo:vars]
ansible_user=alice
ansible_ssh_private_key_file=~/.ssh/dukovo
ansible_python_interpreter=/applications/org.python.python/bin/python3
```

Or as YAML:

```yaml
all:
  children:
    dukovo:
      hosts:
        shop:
          ansible_host: 192.168.1.40
      vars:
        ansible_user: alice
        ansible_ssh_private_key_file: ~/.ssh/dukovo
        ansible_python_interpreter: /applications/org.python.python/bin/python3
```

The first connection shows the machine's key and asks whether to trust it,
as any SSH client does. Compare it with what `sshd` logged as it started
(`log -s sshd`), or with `ssh-keygen -lf
/system/state/sshd/ssh_host_ed25519_key.pub` on the machine.

Five wrong passwords from one address within ten minutes have Dukovo's
firewall drop its new connections to the sign-in ports for ten minutes
(`blocking.toml(5)`). Use keys for the connection, and mind the
`ansible_become_password` below: a wrong one counts.

## Python on Dukovo

Modules are Python programs that run on the machine, and a Dukovo machine
has no Python of its own. Python comes from the catalog as a bundle,
`org.python.python`, and is the one thing a playbook installs without a
module of its own to do it: `ansible.builtin.raw` needs no Python.

```yaml
- hosts: dukovo
  gather_facts: false
  become: true
  tasks:
    - name: Install Python for everyone
      ansible.builtin.raw: bundle install --for-everyone --yes org.python.python
```

The bundle lands in `/applications/org.python.python`, and its `python3` is
also in `/applications/commands`, which every session's `PATH` holds. Name it
in the inventory with `ansible_python_interpreter`, as above; the full path
keeps Ansible from searching for it.

Name the interpreter by its path, as above, and not as `python3`. A command
of a bundle that runs with the access of whoever runs it, as Python does, asks
once at a console whether it may, with a warning, when it is run by its name;
no SSH session can answer that question. Run by its path, as a script or
Ansible runs it, the program asks nothing, as Dukovo's lab tests of Python
show (`lab/tests/services/python-commands.toml`), so a playbook needs no one at
the machine.

## Becoming an administrator

Dukovo has no setuid program. What other systems call `sudo` is `elevate`,
and `sudo` is the same program by the name that scripts use, with the
options Ansible's `sudo` method passes: `-H`, `-S`, `-n`, `-p` and `-u
root`. So Ansible's default method works:

```yaml
- hosts: dukovo
  become: true
  tasks:
    - name: Add a feature
      dukovo.system.feature:
        name: file-sharing
```

Three things differ from a Linux machine:

- **A password is always needed.** There is no `sudoers` file and no
  `NOPASSWD`: an administrator may run any command, after their password,
  unless their terminal pane typed it in the last 15 minutes, and an SSH
  session is a pane of its own. Give it as `ansible_become_password`, kept
  in an Ansible Vault:

  ```
  $ ansible-vault encrypt_string 'the password' --name ansible_become_password
  ```

  Without it Ansible runs `sudo -n`, and elevate answers that a password is
  needed, which fails the task.
- **Only root.** `become_user` other than `root` is refused: elevate runs
  commands as root alone. The environment of the command is root's: its
  `PATH` is `/system/commands:/applications/commands`, and nothing of the
  caller's but the terminal type and the language settings passes, so
  `become_flags: -E` is refused.
- **Only administrators.** An account that is not in `admins` is refused
  before any password.

## A first playbook

```yaml
- hosts: dukovo
  become: true
  gather_subset: [min]
  tasks:
    - name: Learn what the machine is
      dukovo.system.facts:

    - name: It is Dukovo
      ansible.builtin.assert:
        that: ansible_facts.distribution == "Dukovo"

    - name: Turn the SSH server on at each boot
      dukovo.system.service:
        name: sshd
        state: started
        enabled: true

    - name: Follow the stable channel
      dukovo.system.update:
        state: channel
        channel: stable
```

Run it twice. The second time reports `changed=0`, as every module reads the
state first and runs a command only when the state is not as asked. With
`--check` the modules read the state and say what would change, and
`--diff` shows the state before and after as the JSON of what the module
manages.

`gather_subset: [min]` keeps `ansible.builtin.setup` to the facts that do not
read Linux's files: `/proc` and `/sys` lead to Dukovo's `/processes` and
`/kernel`, which are laid out in their own way, so the hardware facts that
parse them have nothing to read. `ansible_facts.distribution` comes from
`ansible.builtin.setup`, which takes
the name of a system that is not Linux from the kernel's `uname`: `Dukovo`.
`dukovo.system.facts` adds what only Dukovo knows, under
`ansible_facts.dukovo`, the release that runs among it.

## The modules

| Module | What it does |
| --- | --- |
| [dukovo.system.bundle](bundle.md) | install, remove, update and hold back apps |
| [dukovo.system.feature](feature.md) | add and remove what the machine does |
| [dukovo.system.service](service.md) | start, stop and enable services |
| [dukovo.system.snapshot](snapshot.md) | make, remove and prune snapshots |
| [dukovo.system.update](update.md) | check, stage and apply updates; the channel and holds |
| [dukovo.system.facts](facts.md) | what Dukovo says of itself |

## When a task fails

A command that fails fails the task with what it printed, and Dukovo's error
ID, such as `UPD-101`, in `error_id`, with `rc`, `stdout` and `stderr`:

```yaml
- name: Stage the update
  become: true
  dukovo.system.update:
    state: staged
  register: staged
  failed_when: false

- name: Say why it failed
  ansible.builtin.debug:
    msg: "{{ staged.error_id }}: {{ staged.msg }}"
  when: staged is failed
```

Dukovo's repository has a page for each error ID, in `docs/errors/`.
