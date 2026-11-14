# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import json

import pytest

from ansible_collections.dukovo.system.plugins.modules import bundle

from .conftest import document, fixture

LIST = "bundle list --json"


def listing(*extra):
    """The recorded bundle list, with rows more."""
    recorded = document("bundle-list")
    recorded["bundles"].extend(extra)
    return json.dumps(recorded)


def row(bundle_id, version="2.0.0", everyone=True, held=False, update=None, catalog="dukovo"):
    return {
        "id": bundle_id,
        "name": bundle_id.split(".")[-1],
        "version": version,
        "for_everyone": everyone,
        "catalog": catalog,
        "held": held,
        "update": update,
        "flaws": {"state": "none", "count": 0, "worst": None},
    }


NGINX = "org.nginx.nginx"
WEB = "org.example.web"


def test_a_bundle_that_is_installed_is_present_without_a_command(machine):
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id=NGINX)
    assert not outcome.failed
    assert outcome.result["changed"] is False
    assert outcome.changing == []
    assert outcome.result["bundle"]["version"] == "1.2.0"
    assert outcome.result["bundle"]["installed"] is True


def test_a_bundle_that_is_not_installed_is_installed_for_everyone_from_its_catalog(machine):
    machine.says(LIST, fixture("bundle-list")).says(LIST, listing(row(WEB)))
    outcome = machine.run(bundle.main, id=WEB, catalog="dukovo")
    assert not outcome.failed
    assert outcome.result["changed"] is True
    assert outcome.changing == ["bundle install org.example.web --from dukovo --for-everyone --yes"]
    assert outcome.result["bundle"]["version"] == "2.0.0"


def test_a_bundle_for_the_account_alone_is_installed_without_for_everyone(machine):
    machine.says(LIST, fixture("bundle-list")).says(LIST, listing(row(WEB, everyone=False)))
    outcome = machine.run(bundle.main, id=WEB, for_everyone=False)
    assert outcome.changing == ["bundle install org.example.web --yes"]
    assert outcome.result["bundle"]["for_everyone"] is False


def test_the_place_is_part_of_the_bundle(machine):
    # nginx is installed for everyone and, held, for the account; notes for the account alone.
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id="org.example.notes")
    assert outcome.result["bundle"]["installed"] is False
    assert outcome.changing == ["bundle install org.example.notes --for-everyone --yes"]


def test_check_mode_says_it_would_install_and_runs_nothing_that_changes(machine):
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id=WEB, catalog="dukovo", check=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.ran == [LIST]
    assert outcome.result["bundle"]["installed"] is True
    assert outcome.result["bundle"]["version"] is None
    assert outcome.result["commands"] == [
        "bundle install org.example.web --from dukovo --for-everyone --yes"
    ]


def test_diff_mode_gives_the_bundle_before_and_after(machine):
    machine.says(LIST, fixture("bundle-list")).says(LIST, listing(row(WEB)))
    outcome = machine.run(bundle.main, id=WEB, diff=True)
    before, after = outcome.result["diff"]["before"], outcome.result["diff"]["after"]
    assert before["installed"] is False and before["version"] is None
    assert after["installed"] is True and after["version"] == "2.0.0"


def test_no_diff_without_diff_mode(machine):
    machine.says(LIST, fixture("bundle-list"))
    assert "diff" not in machine.run(bundle.main, id=NGINX).result


def test_diff_mode_of_an_unchanged_bundle_has_equal_sides(machine):
    machine.says(LIST, fixture("bundle-list"))
    diff = machine.run(bundle.main, id=NGINX, diff=True).result["diff"]
    assert diff["before"] == diff["after"]


def test_latest_updates_a_bundle_whose_catalog_lists_a_newer_version(machine):
    updated = json.loads(listing())
    updated["bundles"][1].update(version="1.3.0", update=None)
    machine.says(LIST, fixture("bundle-list")).says(LIST, json.dumps(updated))
    outcome = machine.run(bundle.main, id=NGINX, state="latest")
    assert outcome.changing == ["bundle update org.nginx.nginx --for-everyone --yes"]
    assert outcome.result["bundle"]["version"] == "1.3.0"


def test_latest_leaves_a_bundle_that_is_up_to_date(machine):
    machine.says(LIST, listing(row(WEB)))
    outcome = machine.run(bundle.main, id=WEB, state="latest")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_latest_does_not_update_a_held_bundle(machine):
    machine.says(LIST, listing(row(WEB, version="1.0.0", held=True, update="1.1.0")))
    outcome = machine.run(bundle.main, id=WEB, state="latest")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_check_mode_of_latest_predicts_the_newer_version(machine):
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id=NGINX, state="latest", check=True, diff=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.result["diff"]["after"]["version"] == "1.3.0"
    assert outcome.result["diff"]["before"]["version"] == "1.2.0"


def test_absent_removes_an_installed_bundle_and_keeps_its_data_unless_purged(machine):
    machine.says(LIST, fixture("bundle-list")).says(LIST, json.dumps({"format": 1, "bundles": []}))
    outcome = machine.run(bundle.main, id=NGINX, state="absent")
    assert outcome.changing == ["bundle remove org.nginx.nginx --for-everyone"]
    assert outcome.result["bundle"]["installed"] is False


def test_absent_with_purge_deletes_its_data_too(machine):
    machine.says(LIST, fixture("bundle-list")).says(LIST, json.dumps({"format": 1, "bundles": []}))
    outcome = machine.run(bundle.main, id=NGINX, state="absent", purge=True)
    assert outcome.changing == ["bundle remove org.nginx.nginx --for-everyone --purge"]


def test_absent_of_a_bundle_that_is_not_installed_changes_nothing(machine):
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id=WEB, state="absent")
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_check_mode_of_absent_says_it_would_remove(machine):
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id=NGINX, state="absent", check=True, diff=True)
    assert outcome.result["changed"] is True
    assert outcome.changing == []
    assert outcome.result["diff"]["before"]["installed"] is True
    assert outcome.result["diff"]["after"]["installed"] is False


def test_held_holds_a_bundle_that_is_not_held(machine):
    held = json.loads(fixture("bundle-list"))
    held["bundles"][1]["held"] = True
    machine.says(LIST, fixture("bundle-list")).says(LIST, json.dumps(held))
    outcome = machine.run(bundle.main, id=NGINX, state="held")
    assert outcome.changing == ["bundle hold org.nginx.nginx --for-everyone"]
    assert outcome.result["bundle"]["held"] is True


def test_held_is_unchanged_for_a_bundle_that_is_held(machine):
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id=NGINX, state="held", for_everyone=False)
    assert outcome.result["changed"] is False
    assert outcome.changing == []


def test_held_installs_a_bundle_first_and_then_holds_it(machine):
    machine.says(LIST, fixture("bundle-list")).says(LIST, listing(row(WEB, held=True)))
    outcome = machine.run(bundle.main, id=WEB, state="held")
    assert outcome.changing == [
        "bundle install org.example.web --for-everyone --yes",
        "bundle hold org.example.web --for-everyone",
    ]


def test_check_mode_of_held_says_it_would_hold(machine):
    machine.says(LIST, fixture("bundle-list"))
    outcome = machine.run(bundle.main, id=NGINX, state="held", check=True, diff=True)
    assert outcome.changing == []
    assert outcome.result["diff"]["after"]["held"] is True


def test_unheld_lets_a_held_bundle_go(machine):
    machine.says(LIST, fixture("bundle-list")).says(LIST, listing(row(WEB)))
    outcome = machine.run(bundle.main, id=NGINX, state="unheld", for_everyone=False)
    assert outcome.changing == ["bundle unhold org.nginx.nginx"]


def test_unheld_is_unchanged_for_a_bundle_that_is_not_held_or_not_installed(machine):
    machine.says(LIST, fixture("bundle-list"))
    assert machine.run(bundle.main, id=NGINX, state="unheld").result["changed"] is False
    assert machine.run(bundle.main, id=WEB, state="unheld").result["changed"] is False
    assert machine.run(bundle.main, id=WEB, state="unheld", check=True).changing == []


def test_a_command_that_fails_fails_the_module_with_its_error_id(machine):
    machine.says(LIST, fixture("bundle-list"))
    machine.says(
        "bundle install org.example.web --from dukovo --for-everyone --yes",
        stdout="",
        rc=1,
        stderr="bundle: the catalog dukovo cannot be reached (NET-141)\n",
    )
    outcome = machine.run(bundle.main, id=WEB, catalog="dukovo")
    assert outcome.failed
    assert outcome.result["error_id"] == "NET-141"
    assert outcome.result["rc"] == 1
    assert "NET-141" in outcome.result["msg"]
    assert "bundle install org.example.web" in outcome.result["msg"]
    assert "cannot be reached" in outcome.result["stderr"]
    assert outcome.result["stdout"] == ""


def test_a_failing_read_fails_the_module(machine):
    machine.says(LIST, rc=1, stderr="bundle: bundled does not answer\n")
    outcome = machine.run(bundle.main, id=NGINX)
    assert outcome.failed
    assert outcome.result["error_id"] is None
    assert "bundled does not answer" in outcome.result["msg"]


@pytest.mark.parametrize("printed", ["not JSON", '{"format": 2, "bundles": []}', "[]"])
def test_a_document_that_is_not_format_1_is_refused(machine, printed):
    machine.says(LIST, printed)
    outcome = machine.run(bundle.main, id=NGINX)
    assert outcome.failed
    assert "bundle list --json" in outcome.result["msg"]
