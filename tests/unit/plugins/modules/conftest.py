# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""A recorded Dukovo machine for the unit tests of the modules.

A test says what each command prints, in the JSON the commands printed
when it was recorded (fixtures/), runs a module's main() against it, and
reads what the module said and which commands it ran. No command runs.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json
import os
from contextlib import contextmanager
from unittest import mock

import pytest
from ansible.module_utils import basic

try:
    from ansible.module_utils.testing import patch_module_args
except ImportError:  # ansible-core before 2.19

    @contextmanager
    def patch_module_args(args):
        payload = json.dumps({"ANSIBLE_MODULE_ARGS": args}).encode("utf-8")
        with mock.patch.object(basic, "_ANSIBLE_ARGS", payload):
            yield


FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def fixture(name):
    """The recorded document fixtures/NAME.json, as text."""
    with open(os.path.join(FIXTURES, name + ".json")) as recorded:
        return recorded.read()


def document(name):
    """The recorded document fixtures/NAME.json, read."""
    return json.loads(fixture(name))


class Ended(Exception):
    """A module ended: it called exit_json or fail_json."""

    def __init__(self, failed, result):
        super(Ended, self).__init__(result)
        self.failed = failed
        self.result = result


class Outcome(object):
    """What a module did: whether it failed, what it said and the commands it ran."""

    def __init__(self, failed, result, ran):
        self.failed = failed
        self.result = result
        self.ran = ran

    @property
    def changing(self):
        """The commands that ran which change the machine: those that do not read its JSON."""
        return [command for command in self.ran if not command.endswith("--json")]


class Machine(object):
    """What each command of a Dukovo machine prints, in the order it is run.

    A read that is not told of fails the test; a command that changes
    something succeeds, printing nothing, unless it is told of. The last
    answer of a command is repeated, so a read that is run twice may say
    the same.
    """

    def __init__(self):
        self.script = {}
        self.ran = []

    def says(self, command, stdout="", rc=0, stderr=""):
        """The next answer of command, such as "bundle list --json"."""
        self.script.setdefault(command, []).append((rc, stdout, stderr))
        return self

    def _run_command(self, args, *unused, **unused_keywords):
        assert isinstance(args, list), "a command is a list, never a shell string: %r" % (args,)
        assert args[0].startswith("/system/commands/"), args
        command = " ".join([os.path.basename(args[0])] + args[1:])
        self.ran.append(command)
        answers = self.script.get(command)
        if not answers and not command.endswith("--json"):
            return 0, "", ""
        assert answers, "no answer for %r; the machine was told of %r" % (command, sorted(self.script))
        return answers.pop(0) if len(answers) > 1 else answers[0]

    def run(self, main, check=False, diff=False, **args):
        """Runs the module main() with args, as Ansible would, and returns its Outcome."""
        args = dict(args)
        if check:
            args["_ansible_check_mode"] = True
        if diff:
            args["_ansible_diff"] = True

        def exit_json(module, **result):
            raise Ended(False, result)

        def fail_json(module, msg, **result):
            result["msg"] = msg
            raise Ended(True, result)

        def get_bin_path(module, name, required=False, opt_dirs=None):
            return "/system/commands/" + name

        patches = (
            mock.patch.object(basic.AnsibleModule, "run_command", self._run_command),
            mock.patch.object(basic.AnsibleModule, "exit_json", exit_json),
            mock.patch.object(basic.AnsibleModule, "fail_json", fail_json),
            mock.patch.object(basic.AnsibleModule, "get_bin_path", get_bin_path),
        )
        with patch_module_args(args):
            for patch in patches:
                patch.start()
            try:
                main()
            except Ended as ended:
                return Outcome(ended.failed, ended.result, self.ran)
            finally:
                mock.patch.stopall()
        raise AssertionError("the module neither ended nor failed")


@pytest.fixture
def machine():
    return Machine()
