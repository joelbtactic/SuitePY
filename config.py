#######################################################################
# Suite PY is a simple Python client for SuiteCRM API.

# Copyright (C) 2017-2018 BTACTIC, SCCL
# Copyright (C) 2017-2018 Marc Sanchez Fauste

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#######################################################################

import configparser
import os.path
import logging

class Config:
    """
    This class is used to read from a file the access credentials of a SuiteCRM API.

    This avoids the need of hard-code the credentials in the code.
    """

    _logger = logging.getLogger('bPortal')

    def __init__(self, config_file="suitepy.ini"):
        """
        Creates a Config instance loading settings from specified file.

        :param str config_file: file from which the configuration will be read.
        """
        if os.path.isabs(config_file):
            abs_path = config_file
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            abs_path = os.path.join(base_dir, config_file)
        if os.path.isfile(abs_path):
            self._logger.info("Loading config from file: " + abs_path)
            self._load_config_file(abs_path)
        else:
            self._logger.info("Creating new config file on: " + abs_path)
            self._logger.info("Please edit config file and rerun the application.")
            self._create_config_file(abs_path)
            exit(0)

    def _load_config_file(self, config_file):
        config = configparser.ConfigParser()
        config.read(config_file)
        self._url = config.get("SuiteCRM API Credentials", "url")
        self._client_id = config.get("SuiteCRM API Credentials", "client_id")
        self._client_secret = config.get("SuiteCRM API Credentials", "client_secret")
        self._application_name = config.get(
            "SuiteCRM API Credentials", "application_name"
        )
        self._verify_ssl = (
            config.get("SuiteCRM API Credentials", "verify_ssl").lower() != "false"
        )

    @staticmethod
    def _create_config_file(config_file):
        config_file = open(config_file, "w")
        config = configparser.ConfigParser()
        config.add_section("SuiteCRM API Credentials")
        config.set("SuiteCRM API Credentials", "url", "https://crm.example.org")
        config.set("SuiteCRM API Credentials", "client_id", "client_id")
        config.set("SuiteCRM API Credentials", "client_secret", "client_secret")
        config.set("SuiteCRM API Credentials", "application_name", "SuitePY")
        config.set("SuiteCRM API Credentials", "verify_ssl", True)
        config.write(config_file)
        config_file.close()

    @property
    def url(self):
        """
        Get SuiteCRM API URL.

        :return: SuiteCRM API URL
        :rtype: str
        """
        return self._url

    @property
    def client_id(self):
        """
        Get client id.

        :return: client id.
        :rtype: str
        """
        return self._client_id

    @property
    def client_secret(self):
        """
        Get client secret.

        :return: client secret.
        :rtype: str
        """
        return self._client_secret

    @property
    def application_name(self):
        """
        Get application name used when login to SuiteCRM API.

        :return: application name.
        :rtype: str
        """
        return self._application_name

    @property
    def verify_ssl(self):
        """
        Specifies whether the SSL certificate should be verified.

        :return: True if SSL certificate must be verified, False otherwise.
        :rtype: bool
        """
        return self._verify_ssl
