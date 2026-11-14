# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

"""Running Dukovo's commands for the modules of dukovo.system.

A module reads the state of the machine with a command's ``--json``
document, decides from it whether anything is to change, and runs the
commands that change it only when it is not in check mode. A command that
fails fails the module with the error ID the command printed.
"""

import json
import re

# The version of the documents the commands print, which every document
# names in its "format". A later one may mean something else by the
# members it has in common, so it is refused.
FORMAT = 1

# Where Dukovo keeps its commands, for a session whose PATH does not hold
# the folder.
BIN_DIRS = ["/system/commands", "/bin", "/usr/bin"]

# A Dukovo error ID: an area of two to five capitals, a dash and three
# digits, as in UPD-101 or SVC-102.
ERROR_ID = re.compile(r"\b[A-Z]{2,5}-[0-9]{3}\b")


def error_id_in(*texts):
    """The first Dukovo error ID in any of texts, or None."""
    for text in texts:
        found = ERROR_ID.search(text or "")
        if found:
            return found.group(0)
    return None


def first_line(text):
    """The first line of text that says something."""
    for line in (text or "").splitlines():
        if line.strip():
            return line.strip()
    return ""


def words(args):
    """The command args as one string, for a message."""
    return " ".join(args)


class Dukovo(object):
    """Runs Dukovo's commands for one module."""

    def __init__(self, module):
        self.module = module
        self._paths = {}

    def _command(self, args):
        name = args[0]
        if name not in self._paths:
            self._paths[name] = self.module.get_bin_path(name, required=True, opt_dirs=BIN_DIRS)
        return [self._paths[name]] + list(args[1:])

    def fail(self, args, rc, stdout, stderr, reason=None):
        """Fails the module because the command args ended with rc.

        The message names the command and says what it printed, with the
        error ID it printed; the ID is also in error_id.
        """
        error_id = error_id_in(stderr, stdout)
        msg = reason or "%s failed with exit status %s" % (words(args[:3]), rc)
        said = first_line(stderr) or first_line(stdout)
        if said and not reason:
            msg += ": " + said
        if error_id and error_id not in msg:
            msg += " (%s)" % error_id
        self.module.fail_json(msg=msg, error_id=error_id, rc=rc, stdout=stdout, stderr=stderr)

    def _run(self, args):
        rc, stdout, stderr = self.module.run_command(self._command(args))
        if rc != 0:
            self.fail(args, rc, stdout, stderr)
        return stdout, stderr

    def read(self, args, version_key="format"):
        """Runs a command that only reads, with --json, and returns its document.

        A document names the version of its format in version_key: "format",
        except that service list prints Spark's own document, whose key is
        "show_version", and dukovo-check's is "version".
        """
        stdout, stderr = self._run(args)
        try:
            document = json.loads(stdout)
        except ValueError:
            return self.fail(args, 0, stdout, stderr, "%s printed no JSON" % words(args[:3]))
        found = document.get(version_key) if isinstance(document, dict) else None
        if found != FORMAT:
            reason = "%s printed %s %s, and this collection reads %d" % (
                words(args[:3]),
                version_key,
                found,
                FORMAT,
            )
            return self.fail(args, 0, stdout, stderr, reason)
        return document

    def read_optional(self, args, version_key="format"):
        """Like read, but a command that is not there, fails or prints another format gives None."""
        name = args[0]
        path = self._paths.get(name) or self.module.get_bin_path(name, opt_dirs=BIN_DIRS)
        if not path:
            return None
        rc, stdout, dummy = self.module.run_command([path] + list(args[1:]))
        if rc != 0:
            return None
        try:
            document = json.loads(stdout)
        except ValueError:
            return None
        if isinstance(document, dict) and document.get(version_key) == FORMAT:
            return document
        return None

    def apply(self, commands):
        """Runs each of commands, which change the machine, unless the module is in check mode."""
        if not self.module.check_mode:
            for args in commands:
                self._run(args)

    def finish(self, changed, before, after, commands, **result):
        """Ends the module: changed or not, with the commands, and --diff's before and after."""
        result.update(changed=changed, commands=[words(args) for args in commands])
        if self.module._diff and (before is not None or after is not None):
            result["diff"] = {"before": before, "after": after}
        self.module.exit_json(**result)
