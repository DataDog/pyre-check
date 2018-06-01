# Copyright (c) 2016-present, Facebook, Inc.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import os
import unittest
from unittest.mock import call, patch

from .. import CONFIGURATION_FILE, number_of_workers
from ..configuration import Configuration  # noqa


class ConfigurationTest(unittest.TestCase):
    @patch("builtins.open")
    @patch("json.load")
    @patch.object(os, "getenv", return_value=None)
    def test_init(self, os_environ, json_load, builtins_open) -> None:
        json_load.side_effect = [
            {
                "source_directories": ["a"],
                "logger": "/usr/logger",
                "do_not_check": ["buck-out/dev/gen"],
            },
            {},
        ]

        configuration = Configuration()
        self.assertEqual(configuration.source_directories, ["a"])
        self.assertEqual(configuration.targets, [])
        self.assertEqual(configuration.logger, "/usr/logger")
        self.assertEqual(configuration.do_not_check, ["buck-out/dev/gen"])

        json_load.side_effect = [{"targets": ["//a/b/c"], "disabled": 1}, {}]
        configuration = Configuration()
        self.assertEqual(configuration.targets, ["//a/b/c"])
        self.assertEqual(configuration.source_directories, ["."])
        self.assertEqual(configuration.get_version_hash(), None)
        self.assertEqual(configuration.logger, None)
        self.assertEqual(configuration.do_not_check, [])
        self.assertTrue(configuration.disabled())
        self.assertTrue(configuration._disabled)

        json_load.side_effect = [{"typeshed": "TYPESHED/"}, {}]
        configuration = Configuration()
        self.assertEqual(configuration.get_search_path(), ["TYPESHED/"])
        self.assertEqual(configuration.number_of_workers, number_of_workers())

        json_load.side_effect = [
            {
                "search_path": ["additional/"],
                "version": "VERSION",
                "typeshed": "TYPE/%V/SHED/",
                "workers": 20,
            },
            {},
        ]
        configuration = Configuration()
        self.assertEqual(
            configuration.get_search_path(), ["additional/", "TYPE/VERSION/SHED/"]
        )
        self.assertEqual(configuration.number_of_workers, 20)

        # Test loading of additional directories in the search path
        # via environment.
        json_load.side_effect = [
            {"search_path": ["json/", "file/"], "typeshed": "TYPESHED/"},
            {},
        ]
        with patch.object(os, "getenv", return_value="additional/:directories/"):
            with patch.object(os.path, "isdir", return_value=True):
                configuration = Configuration(
                    search_path=["command/", "line/"], preserve_pythonpath=True
                )
                self.assertEqual(
                    configuration.get_search_path(),
                    [
                        "additional/",
                        "directories/",
                        "command/",
                        "line/",
                        "json/",
                        "file/",
                        "TYPESHED/",
                    ],
                )

        # Test case where we ignore the PYTHONPATH environment variable.
        json_load.side_effect = [
            {"search_path": ["json/", "file/"], "typeshed": "TYPESHED/"},
            {},
        ]
        with patch.object(os, "getenv", return_value="additional/:directories/"):
            with patch.object(os.path, "isdir", return_value=True):
                configuration = Configuration(
                    search_path=["command/", "line/"], preserve_pythonpath=False
                )
                self.assertEqual(
                    configuration.get_search_path(),
                    ["command/", "line/", "json/", "file/", "TYPESHED/"],
                )

        # Test manual loading of typeshed directory.
        json_load.side_effect = [{}, {}]
        configuration = Configuration(typeshed="some/directory/path/")
        self.assertEqual(configuration.get_search_path(), ["some/directory/path/"])

        json_load.side_effect = [{"binary": "/binary"}, {}]
        configuration = Configuration()
        self.assertEqual(configuration.get_binary(), "/binary")

        json_load.side_effect = [{"version": "VERSION", "binary": "/%V/binary"}, {}]
        configuration = Configuration()
        self.assertEqual(configuration.get_binary(), "/VERSION/binary")

        with patch.object(os, "getenv", return_value="VERSION_HASH"):
            json_load.side_effect = [{}, {}]
            configuration = Configuration()
            self.assertEqual(configuration.get_version_hash(), "VERSION_HASH")

        # Test multiple definitions of the do_not_check files.
        json_load.side_effect = [
            {"do_not_check": ["buck-out/dev/gen"]},
            {"do_not_check": ["buck-out/dev/gen2"]},
        ]
        configuration = Configuration()
        self.assertEqual(
            configuration.do_not_check, ["buck-out/dev/gen", "buck-out/dev/gen2"]
        )

        # Temporarily support former name 'autogenerated'.
        json_load.side_effect = [
            {"autogenerated": ["buck-out/dev/gen"]},
            {"autogenerated": ["buck-out/dev/gen2"]},
        ]
        configuration = Configuration()
        self.assertEqual(
            configuration.do_not_check, ["buck-out/dev/gen", "buck-out/dev/gen2"]
        )

        # Normalize number of workers if zero.
        json_load.side_effect = [{"typeshed": "TYPESHED/", "workers": 0}, {}]
        configuration = Configuration()
        self.assertEqual(configuration.get_search_path(), ["TYPESHED/"])
        self.assertEqual(configuration.number_of_workers, number_of_workers())

    @patch("os.path.isfile")
    def test_configurations(self, os_path_isfile) -> None:
        os_path_isfile.return_value = False

        with patch.object(Configuration, "_read") as Configuration_read:
            Configuration()
            Configuration_read.assert_has_calls(
                [
                    call(CONFIGURATION_FILE + ".local", path_from_root=""),
                    call(CONFIGURATION_FILE, path_from_root=""),
                ]
            )

        with patch.object(Configuration, "_read") as Configuration_read:
            Configuration(original_directory="original")
            Configuration_read.assert_has_calls(
                [
                    call(
                        "original/" + CONFIGURATION_FILE + ".local",
                        path_from_root="original",
                    ),
                    call(CONFIGURATION_FILE + ".local", path_from_root=""),
                    call(CONFIGURATION_FILE, path_from_root=""),
                ]
            )
        with patch.object(Configuration, "_read") as Configuration_read:
            Configuration(local_configuration="local")
            Configuration_read.assert_has_calls(
                [
                    call(
                        "local/" + CONFIGURATION_FILE + ".local", path_from_root="local"
                    ),
                    call(CONFIGURATION_FILE + ".local", path_from_root=""),
                    call(CONFIGURATION_FILE, path_from_root=""),
                ]
            )
        with patch.object(Configuration, "_read") as Configuration_read:
            Configuration(original_directory="original", local_configuration="local")
            Configuration_read.assert_has_calls(
                [
                    call(
                        "local/" + CONFIGURATION_FILE + ".local", path_from_root="local"
                    ),
                    call(CONFIGURATION_FILE + ".local", path_from_root=""),
                    call(CONFIGURATION_FILE, path_from_root=""),
                ]
            )

        os_path_isfile.return_value = True
        with patch.object(Configuration, "_read") as Configuration_read:
            Configuration(local_configuration="local/.some_configuration")
            Configuration_read.assert_has_calls(
                [
                    call("local/.some_configuration", path_from_root="local"),
                    call(CONFIGURATION_FILE + ".local", path_from_root=""),
                    call(CONFIGURATION_FILE, path_from_root=""),
                ]
            )

    @patch("os.path.isdir")
    def test_empty_configuration(self, os_path_isdir) -> None:
        os_path_isdir.return_value = False

        with patch.object(Configuration, "_read"):
            # __init__.py is in the parent directory.
            directory = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
            bundled_typeshed_calls = []
            environment_typeshed_calls = []
            while True:
                bundled_typeshed_calls.append(
                    call(os.path.join(directory, "pyre_check/typeshed/stdlib/"))
                )
                environment_typeshed_calls.append(
                    call(os.path.join(directory, "typeshed/stdlib/"))
                )
                parent_directory = os.path.dirname(directory)
                if parent_directory == directory:
                    break
                directory = parent_directory
            calls = bundled_typeshed_calls + environment_typeshed_calls

            configuration = Configuration()
            os_path_isdir.assert_has_calls(calls)
            self.assertEqual(configuration.source_directories, ["."])
            self.assertEqual(configuration.targets, [])
            self.assertEqual(configuration.get_version_hash(), None)
            self.assertEqual(configuration.logger, None)
            self.assertEqual(configuration.do_not_check, [])
            self.assertFalse(configuration.disabled())
            self.assertFalse(configuration._disabled)
            self.assertEqual(configuration._typeshed, None)
