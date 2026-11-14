# -*- coding: utf-8 -*-
# SPDX-FileCopyrightText: 2026 The Dukovo contributors
# GNU General Public License v3.0+ (see LICENSES/GPL-3.0-or-later.txt or https://www.gnu.org/licenses/gpl-3.0.txt)
# SPDX-License-Identifier: GPL-3.0-or-later

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import pytest

from ansible_collections.dukovo.system.plugins.module_utils import dukovo


@pytest.mark.parametrize(
    "text, found",
    [
        ("update: the update could not be staged (UPD-101)", "UPD-101"),
        ("error SVC-102: nginx did not start", "SVC-102"),
        ("see https://dukovo.org/support/0.15.2/errors/BOOT-102.html", "BOOT-102"),
        ("two IDs, HW-111 and HW-112", "HW-111"),
        ("no ID here", None),
        ("a lowercase upd-101 and a short U-1 are not IDs", None),
        ("a too long UPDATE-101 and ABCDEF-101 are not IDs", None),
        ("a number of four digits UPD-1011 is not an ID", None),
        ("", None),
        (None, None),
    ],
)
def test_an_error_id_is_an_area_a_dash_and_three_digits(text, found):
    assert dukovo.error_id_in(text) == found


def test_the_first_text_that_holds_an_id_names_it():
    assert dukovo.error_id_in("", None, "x NET-132", "y NET-133") == "NET-132"


def test_the_first_line_that_says_something():
    assert dukovo.first_line("\n  \nbundle: gone\nmore\n") == "bundle: gone"
    assert dukovo.first_line("") == ""
    assert dukovo.first_line(None) == ""
